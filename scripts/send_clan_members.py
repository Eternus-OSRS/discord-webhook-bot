import os
import json
import datetime as dt
import requests
import tempfile

WOM_GROUP_ID = os.getenv("WOM_GROUP_ID")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_DEV_WH")
# Present for future use; not required for GET /groups/:id
WOM_VERIFICATION_CODE = os.getenv("WOM_VERIFICATION_CODE")


def fetch_group_members():
    url = f"https://api.wiseoldman.net/v2/groups/{WOM_GROUP_ID}"
    r = requests.get(url, timeout=30)
    print(f"[WOM] GET {url} -> {r.status_code}")
    if r.status_code != 200:
        print(f"[WOM] body(first300)={r.text[:300]!r}")
    r.raise_for_status()

    data = r.json()
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

    group_name = data.get("name", f"group_{WOM_GROUP_ID}")
    return group_name, rows


def create_txt_file(group_name, rows):
    ts = dt.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filename = f"{group_name}_members_{ts}.txt".replace(" ", "_")

    temp_file = tempfile.NamedTemporaryFile(
        delete=False, suffix=".txt", mode="w", encoding="utf-8", newline="\n"
    )
    temp_path = temp_file.name

    temp_file.write(f"Clan Member Export - {group_name}\n")
    temp_file.write(f"Generated (UTC): {dt.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%SZ')}\n")
    temp_file.write(f"Members: {len(rows)}\n\n")
    temp_file.write("Display Name | Username | Role | Status\n")
    temp_file.write("-" * 80 + "\n")

    for r in rows:
        temp_file.write(
            f"{r.get('Display Name','')} | {r.get('Username','')} | {r.get('Role','')} | {r.get('Status','')}\n"
        )

    temp_file.close()
    return filename, temp_path, len(rows)


def send_to_discord(filename, filepath, count, group_name):
    # Plain text message; no links, no markdown
    payload = {"content": "Clan members export attached."}

    # Use wait=true to get a JSON response (helpful proof in logs)
    webhook_url = DISCORD_WEBHOOK_URL + ("&wait=true" if "?" in DISCORD_WEBHOOK_URL else "?wait=true")

    with open(filepath, "rb") as f:
        files = {"file1": (filename, f, "text/plain; charset=utf-8")}
        resp = requests.post(
            webhook_url,
            data={"payload_json": json.dumps(payload)},
            files=files,
            timeout=60
        )

    print(f"[DISCORD] POST -> {resp.status_code}")
    print(f"[DISCORD] body(first300)={resp.text[:300]!r}")
    resp.raise_for_status()


def main():
    if not WOM_GROUP_ID:
        raise Exception("Missing WOM_GROUP_ID")
    if not DISCORD_WEBHOOK_URL:
        raise Exception("Missing DISCORD_DEV_WH")

    group_name, rows = fetch_group_members()
    filename, filepath, count = create_txt_file(group_name, rows)
    send_to_discord(filename, filepath, count, group_name)

    print(f"✅ Sent TXT to Discord ({count} members)")


if __name__ == "__main__":
    main()
