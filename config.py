import json
import os

CONFIG_FILE = "config.json"
EVENTS_FILE = "events.json"

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    return {}

def save_config(config_data):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config_data, f, indent=4)

def load_events():
    if os.path.exists(EVENTS_FILE):
        with open(EVENTS_FILE, "r") as f:
            return json.load(f)
    return {"events": {}, "permanent_roles": {}, "boards": {}}

def save_events(events_data):
    with open(EVENTS_FILE, "w") as f:
        json.dump(events_data, f, indent=4)
