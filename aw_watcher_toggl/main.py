#!/usr/bin/env python3

import sys
import logging
import traceback
from time import sleep
from datetime import datetime, timezone, timedelta
from calendar import monthrange
import json
from collections import defaultdict

import requests
from requests import ConnectionError

from aw_core import dirs
from aw_core.models import Event
from aw_client.client import ActivityWatchClient

logger = logging.getLogger("aw-watcher-toggl")
DEFAULT_CONFIG = """
[aw-watcher-toggl]
api_token = "" # Toggl API token
poll_time = 300.0 # Polling time in seconds
backfill = false # Whether to backfill data missing data
backfill_since = "" # Format: "YYYY-MM-DD" Day is ignored!
update_existing_events = true # Whether to update existing events"""


def get_time_entries(api_token, month: datetime = None):
    month = month or datetime.now()

    # Calculate the first day of the last month
    month_first_day = month.replace(day=1)
    month_last_day = month.replace(day=monthrange(month.year, month.month)[1])
    auth = (api_token, "api_token")
    url = f"https://api.track.toggl.com/api/v9/me/time_entries?start_date={month_first_day.strftime('%Y-%m-%d')}&end_date={month_last_day.strftime('%Y-%m-%d')}"
    headers = {"Content-Type": "application/json"}
    response = requests.get(url=url, auth=auth, headers=headers, timeout=5)

    if response.status_code != 200:
        raise requests.exceptions.HTTPError(response.text)

    return response.json()


def get_current_time_entry(api_token):
    auth = (api_token, "api_token")
    url = "https://api.track.toggl.com/api/v9/me/time_entries/current"
    headers = {"Content-Type": "application/json"}
    response = requests.get(url=url, auth=auth, headers=headers, timeout=5)

    if response.status_code != 200:
        raise requests.exceptions.HTTPError(response.text)

    return response.json()


def get_projects(api_token):
    auth = (api_token, "api_token")
    url = "https://api.track.toggl.com/api/v9/me/projects"
    headers = {"Content-Type": "application/json"}
    response = requests.get(url, auth=auth, headers=headers, timeout=5)

    if response.status_code != 200:
        raise requests.exceptions.HTTPError(response.text)

    return {proj["id"]: proj["name"] for proj in response.json()}


def process_time_entries(aw, bucketname, entries, projects, update_existing_events):
    already_logged_events = defaultdict(list)
    for event in aw.get_events(bucketname):
        already_logged_events[event["data"]["uid"]].append(event["id"])
    added_tasks = 0
    for entry in entries:
        project_name = (
            projects[entry["project_id"]] if entry["project_id"] is not None else ""
        )
        if entry["description"] == "":
            # Needs a title otherwise won't be displayed in the UI
            # Form one from the project name and timestamp
            entry["description"] = f"{project_name}"
        else:
            entry["description"] = f"{project_name} - {entry['description']}"
        if entry["id"] in already_logged_events:
            if not update_existing_events:
                continue
            for aw_event_id in already_logged_events[entry["id"]]:
                aw.delete_event(bucketname, aw_event_id)

        data = {
            "project": project_name,
            "title": entry["description"],
            "tags": str(entry["tags"]),
            "uid": entry["id"],
        }
        timestamp = entry["start"]
        duration = entry["duration"]
        new_event = Event(timestamp=timestamp, duration=duration, data=data)
        # TODO: this could be a bulk insert
        aw.insert_event(bucketname, new_event)
        added_tasks += 1
        print_statusline(
            "Title: {}, Start: {}, Duration: {}".format(
                entry["description"], entry["start"], entry["duration"]
            )
        )
    print_statusline(f"Added {added_tasks} task(s)")


def load_config():
    from aw_core.config import load_config_toml as _load_config

    return _load_config("aw-watcher-toggl", DEFAULT_CONFIG)


def print_statusline(msg):
    last_msg_length = (
        len(print_statusline.last_msg) if hasattr(print_statusline, "last_msg") else 0
    )
    print(" " * last_msg_length, end="\r")
    print(msg, end="\r")
    print_statusline.last_msg = msg


def main():
    logging.basicConfig(level=logging.INFO)

    config_dir = dirs.get_config_dir("aw-watcher-toggl")

    config = load_config()
    poll_time = float(config["aw-watcher-toggl"].get("poll_time"))
    token = config["aw-watcher-toggl"].get("api_token", None)
    backfill = config["aw-watcher-toggl"].get("backfill", False)
    backfill_since = config["aw-watcher-toggl"].get("backfill_since", None)
    backfill_since = (
        datetime.strptime(backfill_since, "%Y-%m-%d") if backfill_since else None
    )
    update_existing_events = config["aw-watcher-toggl"].get(
        "update_existing_events", False
    )
    if not token:
        logger.warning(
            """Toggl API token not specified in config file (in folder {}). 
               Get your API token on the Toggl website """.format(config_dir)
        )
        sys.exit(1)

    # TODO: Fix --testing flag and set testing as appropriate
    aw = ActivityWatchClient("aw-watcher-toggl", testing=False)
    bucketname = "{}_{}".format(aw.client_name, aw.client_hostname)
    if aw.get_buckets().get(bucketname) is None:
        aw.create_bucket(bucketname, event_type="toggl_data", queued=True)
    aw.connect()

    if backfill:
        backfill_since = (
            backfill_since or datetime.now() - timedelta(days=32)
        ).replace(day=1)
        print_statusline("Backfilling toggl data since {}...".format(backfill_since))
        # Start with current month
        current_month = backfill_since

        while current_month < datetime.now():
            print_statusline(
                f"Backfilling toggl data for {current_month.strftime('%B %Y')}..."
            )
            entries = get_time_entries(token, current_month)

            if not entries:
                print_statusline(
                    f"No entries found for {current_month.strftime('%B %Y')}"
                )

            projects = get_projects(token)
            process_time_entries(
                aw, bucketname, entries, projects, update_existing_events
            )

            # Go forward by one month
            current_month = (current_month + timedelta(days=32)).replace(day=1)
        else:
            print_statusline("Backfilling done.")

    entries = None
    projects = None
    while True:
        try:
            entry = get_current_time_entry(token)
            projects = get_projects(token)
        except requests.exceptions.HTTPError:
            print_statusline("\nProblem with toggl api. Try again\n")
            continue
        except ConnectionError:
            logger.error(
                "Connection error while trying to get track, check your internet connection."
            )
            sleep(poll_time)
            continue
        except json.JSONDecodeError:
            logger.error("Error trying to decode")
            sleep(0.1)
            continue
        except Exception:
            logger.error("Unknown Error")
            logger.error(traceback.format_exc())
            sleep(0.1)
            continue

        try:
            if entry:
                data = {
                    "project": projects[entry["project_id"]]
                    if entry["project_id"] is not None
                    else "No project",
                    "title": entry["description"]
                    if entry["description"] != ""
                    else "No Name",
                    "tags": str(entry["tags"]),
                    "uid": entry["id"],
                }
                print_statusline(f"Active Entry: {data['title']}")
                event = Event(timestamp=datetime.now(timezone.utc), data=data)
                aw.heartbeat(bucketname, event, pulsetime=poll_time + 5, queued=True)
            else:
                print_statusline("No current entries.")
        except Exception as e:
            print("An exception occurred: {}".format(e))
            traceback.print_exc()
        sleep(poll_time)


if __name__ == "__main__":
    main()
