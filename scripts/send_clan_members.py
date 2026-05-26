import os
import json
import datetime as dt
from io import BytesIO
import requests


WOM_GROUP_ID = os.getenv("WOM_GROUP_ID")
WOM_VERIFICATION_CODE = os.getenv("WOM_VERIFICATION_CODE")  # kept for future use; not required for GET
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_DEV_WH")


def fetch_group_members(group_id: str):
    """
    Fetch group details from WOM API. Response includes `memberships` with nested `player` objects. [3](https://birdie0.github.io/discord-webhooks-guide/json.html)
    """
    url = f"https://api.wiseoldman.net/v2/groups/{group_id}"
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    data = r.json()

    group_name = data.get("name", f"group_{group_id}")
    memberships = data.get("memberships", [])

    rows = []
    for m in memberships:
        player = (m.get("player") or {})
        rows.append({
            "displayName": player.get("displayName") or player.get("username") or "",
            "username": player.get("username") or "",
            "role": m.get("role") or "",
            "status": player.get("status") or "",
            "lastImportedAt": player.get("lastImportedAt") or "",
        })

    # Sort output for stability/readability
    rows.sort(key=lambda x: (x["role"], x["displayName"].lower()))
    return group_name, rows


def build_txt_in_memory(group_name: str, rows: list[dict]):
    """
    Build a text file entirely in memory (no disk writes).
    """
    ts = dt.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%SZ")
    header = [
        f"Clan Member Export - {group_name}",
        f"Generated: {ts} (UTC)",
        f"Members: {len(rows)}",
        "",
        "Format: Display Name | Username | Role | Status | Last Imported",
        "-" * 80,
    ]

    lines = []
    for r in rows:
        lines.append(
            f"{r['displayName']} | {r['username']} | {r['role']} | {r['status']} | {r['lastImportedAt']}"
        )

    content = "\n".join(header + lines) + "\n"
    bio = BytesIO(content.encode("utf-8"))

    safe_name = group_name.replace(" ", "_")
    filename = f"{safe_name}_members_{dt.datetime.utcnow().strftime('%Y%m%d_%H%M%SZ')}.txt"
    return filename, bio, len(rows)


def post_file_to_discord(webhook_url: str, filename: str, fileobj: BytesIO, member_count: int, group_name: str):
    """
    Discord webhook file upload requires multipart/form-data with `payload_json`. [1](https://stackoverflow.com/questions/77795882/using-class-to-make-discord-bot-for-simple-hello-function)[2](https://realpython.com/how-to-make-a-discord-bot-python/)
    """
    payload = {
        "content": f"Clan member export for **{group_name}**: {member_count} members.\nAttached: `{filename}`"
    }

    files = {
