import os
import json
import datetime as dt
from io import BytesIO

import requests


WOM_GROUP_ID = os.getenv("WOM_GROUP_ID")
WOM_VERIFICATION_CODE = os.getenv("WOM_VERIFICATION_CODE")  # not required for GET, kept for future use
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_DEV_WH")


def fetch_group_members():
    """
    Calls WOM Get Group Details endpoint:
    GET https://api.wiseoldman.net/v2/groups/:id
    Returns memberships with nested player objects. [3](https://www.youtube.com/watch?v=xh2iabVtw-c)[4](https://envtools.dev/guides/github-actions-secrets)
    """
    url = f"https://api.wiseoldman.net/v2/groups/{WOM_GROUP_ID}"
    print("=== WOM DEBUG ===")
    print(f"Requesting: {url}")
    print(f"WOM_GROUP_ID: {WOM_GROUP_ID}")

    r = requests.get(url, timeout=30)
    print(f"WOM status: {r.status_code}")
    print(f"WOM response (first 200 chars): {r.text[:200]!r}")

    r.raise_for_status()
    data = r.json()

    group_name = data.get("name", f"group_{WOM_GROUP_ID}")
    memberships = data.get("memberships", [])

    rows = []
    for m in memberships:
        player = m.get("player", {}) or {}
        rows.append({
            "Display Name": player.get("displayName") or player.get("username") or "",
            "Username": player.get("username") or "",
            "Role": m.get("role") or "",
            "Status": player.get("status") or "",
        })

    return group_name, rows


def create_txt_in_memory(group_name, rows):
    ts_iso = dt.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%SZ")
    ts_file = dt.datetime.utcnow().strftime("%Y%m%d_%H%M%S")

    filename = f"{group_name}_members_{ts_file}.txt".replace(" ", "_")

    header = [
        f"Clan Member Export - {group_name}",
        f"Generated (UTC): {ts_iso}",
        f"Members: {len(rows)}",
        "",
        "Display Name | Username | Role | Status",
        "-" * 80
    ]

    lines = []
    for r in rows:
        lines.append(
            f"{r.get('Display Name','')} | {r.get('Username','')} | {r.get('Role','')} | {r.get('Status','')}"
        )

    content = "\n".join(header + lines) + "\n"
    bio = BytesIO(content.encode("utf-8"))
    bio.seek(0)

    return filename, bio, len(rows)


def send_to_discord(filename, fileobj, count, group_name):
    """
    Uploads a file to Discord webhook using multipart/form-data + payload_json. [1](https://www.letsupdateskills.com/tutorials/introduction-to-github-concepts/github-creating-a-new-repository)[2](https://docs.github.com/en/pages/quickstart)
    """
    print("=== DISCORD DEBUG ===")
    print(f"Preparing to send file: {filename} ({count} members)")

    payload = {
        "content": f"Clan export for **{group_name}**: {count} members\nAttached: `{filename}`"
    }

    data = {"payload_json": json.dumps(payload)}
    files = {"file1": (filename, fileobj, "text/plain; charset=utf-8")}

    resp = requests.post(DISCORD_WEBHOOK_URL, data=data, files=files, timeout=60)
    print(f"Discord status: {resp.status_code}")
    print(f"Discord response text (first 200 chars): {resp.text[:200]!r}")

    resp.raise_for_status()


def main():
    # Hard fail fast if secrets didn't load
    if not WOM_GROUP_ID:
        raise RuntimeError("Missing WOM_GROUP_ID (env var empty).")
    if not DISCORD_WEBHOOK_URL:
        raise RuntimeError("Missing DISCORD_DEV_WH (env var empty).")

    group_name, rows = fetch_group_members()
    filename, bio, count = create_txt_in_memory(group_name, rows)
    send_to_discord(filename, bio, count, group_name)

    print(f"✅ Done. Sent {count} members to Discord.")


if __name__ == "__main__":
    main()
