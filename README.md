aw-watcher-toggl
==================

This extension both gets the past and current timers in Toggl and also checks for live timers.

This watcher is currently in a early stage of development, please submit PRs if you find bugs!


## Usage

### Step 0: Create Toggl Web API token

Go to [Toggl profile page](https://track.toggl.com/profile) and find the api token.

### Step 1: Install package

Install the requirements:

```sh
pip install .
```

First run (generates empty config that you need to fill out):
```sh
python aw-watcher-toggl/main.py
```

### Step 2: Enter config

Add your api token to the config. You can also enable backfilling of toggl tasks if you want to start with a full toggl bucket. You don't need to worry about duplicate entries being added since it only adds Toggl events if they have not been added before by checking against the uid. Make sure to add the `backfill_since` option to define when you want to start the backfill. 

I recently also added the option to update entries from toggl. Sometimes you update the entries in toggl, but they are not updated in AW since it does not update same ids. This will update all identical id events by deleting the old event and adding the new event. This will also delete duplicate toggl events in AW. It will delete all toggl events with the same toggl id then write one clean toggl event.

### Step 3: Restart the server and enable the watcher

Don't forget to add it to the aw-qt.toml file so that it gets started automatically when AW starts. 


