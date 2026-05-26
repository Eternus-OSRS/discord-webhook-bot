import os
import datetime as dt
import requests
import pandas as pd
import tempfile


WOM_GROUP_ID = os.getenv("WOM_GROUP_ID")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_DEV_WH")


def fetch_group_members():
    url = f"https://api.wiseoldman.net/v2/groups/{WOM_GROUP_ID}"
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    data = r.json()

    memberships = data.get("memberships", [])
    rows = []

    for m in memberships:
        player = m.get("player", {}) or {}
        rows.append({
            "Display Name": player.get("displayName") or player.get("username"),
            "Username": player.get("username"),
            "Role": m.get("role"),
            "Status": player.get("status"),
        })

    group_name = data.get("name", f"group_{WOM_GROUP_ID}")
    return group_name, rows


# CHANGED: create_excel_file -> create_txt_file (same pattern: returns filename, temp_path, count)
def create_txt_file(group_name, rows):
    ts = dt.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filename = f"{group_name}_members_{ts}.txt".replace(" ", "_")

