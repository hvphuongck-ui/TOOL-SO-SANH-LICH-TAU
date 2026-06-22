import json
import os

CONFIG_FILE = "config.json"

DEFAULT_CONFIG = {
    "service_rules": {
        "FYA": "AFRICA EXPRESS",
        "GUW": "AMERICA",
        "QBW": "BRITANNIA",
        "UKA": "CHINOOK",
        "GNE": "LONE STAR EXPRESS",
        "FVN": "SENTOSA"
    },
    "service_colors": {
        "AFRICA EXPRESS": "#99FF99",
        "AMERICA": "#C00000",
        "BRITANNIA": "#FBD5B5",
        "CHINOOK": "#6BA5DA",
        "LONE STAR EXPRESS": "#E6E0CB",
        "SENTOSA": "#9BBB59",
        "EMERALD": "#FF9999",
        "SAMBAR": "#4F81BD",
        "ADHOC": "#7030A0"
    },
    "vessels_loa": {
        "MSC MAPUTO": 272,
        "MSC MIA": 400,
        "MSC HAMBURG": 399,
        "MSC LORENZA": 366,
        "ZIM MOUNT DENALI": 366,
        "ZIM MOUNT BLANC": 366,
        "HAIAN BETA": 172
    },
    "default_color": "#D3D3D3",
    "default_loa": 300
}

def load_config():
    if not os.path.exists(CONFIG_FILE):
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            config = json.load(f)
            # Merge defaults for any missing keys
            for key, val in DEFAULT_CONFIG.items():
                if key not in config:
                    config[key] = val
            return config
    except Exception as e:
        print(f"Error loading config: {e}")
        return DEFAULT_CONFIG

def save_config(config):
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4)
    except Exception as e:
        print(f"Error saving config: {e}")
