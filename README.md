aw-watcher-toggl
==================

This extension both gets the past and current timers in Toggl and also checks for live timers.

This watcher is currently in a early stage of development, please submit PRs if you find bugs!


## Usage

### Step 0: Create Toggl Web API token

Go to [Toggl profile page](https://track.toggl.com/profile) and find the api token.

### Step 1: Install package

Install with [uv](https://github.com/astral-sh/uv):

```sh
uv sync # optional
uv tool install .
```

On Linux and macOS, the `aw-watcher-toggl` command is installed to `~/.local/bin`. On Windows, it is installed to `C:\Users\<your-user>\.local\bin`. Ensure the relevant directory is on your `PATH` so the binary can be resolved.

First run (generates empty config that you need to fill out):
```sh
aw-watcher-toggl # Linux/macOS
# or
aw-watcher-toggl.exe # Windows
```

### Step 2: Enter config

Add your api token to the config. You can also enable backfilling of toggl tasks if you want to start with a full toggl bucket. You don't need to worry about duplicate entries being added since it only adds Toggl events if they have not been added before by checking against the uid. Make sure to add the `backfill_since` option to define when you want to start the backfill. 

I recently also added the option to update entries from toggl. Sometimes you update the entries in toggl, but they are not updated in AW since it does not update same ids. This will update all identical id events by deleting the old event and adding the new event. This will also delete duplicate toggl events in AW. It will delete all toggl events with the same toggl id then write one clean toggl event.

**RATE LIMITING FOR API**

Toggl Track is introducing API usage limits on 5 September 2025. To stay within the Free plan quota (30 requests per hour, per user, per organization) you should ensure that $2 * N + 2 * (3600/\text{pollTime}) \le 30$. 

- `N` - number of months that the backfill spans (rounded up; include the current month when backfill is enabled).
- `pollTime` - polling interval in seconds from the watcher configuration.

The `2 * N` term accounts for one `/time_entries` request and one `/projects` request per backfilled month. The `2 * (3600/pollTime)` term covers the `/time_entries/current` and `/projects` requests issued each poll cycle (two requests per poll, evaluated over an hour). If you are on the Starter or Premium plans, replace `30` on the right-hand side with `240` or `600`, respectively. I will perhaps add checking into the watcher to make sure that it gives a warning if the limits will get violated.  


### Step 3: Restart the server and enable the watcher

Don't forget to add it to the aw-qt.toml file so that it gets started automatically when AW starts. 
