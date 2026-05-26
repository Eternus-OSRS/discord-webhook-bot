import os
import json
import datetime as dt
import requests

WOM_GROUP_ID = os.getenv("WOM_GROUP_ID")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_DEV_WH")

# ✅ Set these to your two BOTW bosses (WOM boss metric keys)
BOSS1 = os.getenv("BOSS1", "zulrah")
BOSS2 = os.getenv("BOSS2", "vorkath")


def get_group_members(group_id: str):
    url = f"https://api.wiseoldman.net/v2/groups/{group_id}"
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    data = r.json()

    # memberships[].player.username + player.displayName exists in group details response [1](https://codepal.ai/code-generator/query/cPnObwMa/discord-bot-say-hello)
    members = []
    for m in data.get("memberships", []):
        p = m.get("player") or {}
        username = p.get("username") or ""
        display = p.get("displayName") or username
        if username:
            members.append((display, username))

    group_name = data.get("name", f"group_{group_id}")
    return group_name, members


def get_player_boss_kc(username: str, boss_key: str) -> int:
    # POST /players/:username returns PlayerDetails including latestSnapshot.data.bosses.{metric}.kills 
    url = f"https://api.wiseoldman.net/v2/players/{username}"
    r = requests.post(url, timeout=30)
    r.raise_for_status()
    data = r.json()

    bosses = (((data.get("latestSnapshot") or {}).get("data") or {}).get("bosses") or {})
    kills = (bosses.get(boss_key) or {}).get("kills", 0)

    # WOM uses -1 when not ranked/absent for some metrics; treat as 0
    if kills is None or kills < 0:
        return 0
    return int(kills)


def build_report(group_name: str, members: list[tuple[str, str]]):
    rows = []
    for display, username in members:
        kc1 = get_player_boss_kc(username, BOSS1)
        kc2 = get_player_boss_kc(username, BOSS2)
        total = kc1 + kc2
        rows.append((display, username, kc1, kc2, total))

    # Sort by total desc, then name
    rows.sort(key=lambda x: (-x[4], x[0].lower()))

    ts = dt.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%SZ")
    filename = f"kc_report_{BOSS1}_{BOSS2}_{dt.datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.txt".replace(" ", "_")

    # Write report
    with open(filename, "w", encoding="utf-8", newline="\n") as f:
        f.write(f"Clan BOTW KC Report\n")
        f.write(f"Group: {group_name}\n")
        f.write(f"Boss 1: {BOSS1}\n")
        f.write(f"Boss 2: {BOSS2}\n")
        f.write(f"Generated (UTC): {ts}\n\n")

        f.write(f"{'Name':<22}{BOSS1:<12}{BOSS2:<12}{'Total':<8}\n")
        f.write("-" * 54 + "\n")

        for display, username, kc1, kc2, total in rows:
            # show display name, but keep width stable
            name = (display[:21] + "…") if len(display) > 22 else display
            f.write(f"{name:<22}{kc1:<12}{kc2:<12}{total:<8}\n")

    return filename, rows


def send_file_to_discord(webhook_url: str, filename: str, top_row):
    # Upload a file to Discord webhook with multipart/form-data and payload_json [2](https://joniii.dev/docs/discord-bot-template)[3](https://www.techbloat.com/how-to-make-a-discord-bot-with-codes-easiest-guide.html)
    content = "BOTW KC totals report attached."
    if top_row:
        content += f"  Leader: {top_row[0]} ({top_row[4]} total)"

    payload = {"content": content}

    with open(filename, "rb") as f:
        files = {
            "file1": (filename, f, "text/plain; charset=utf-8")
        }
        r = requests.post(
            webhook_url,
            data={"payload_json": json.dumps(payload)},
            files=files,
            timeout=60
        )
    r.raise_for_status()
    print(f"✅ Sent {filename} to Discord (status={r.status_code}).")


def main():
    if not WOM_GROUP_ID:
        raise RuntimeError("Missing WOM_GROUP_ID env var.")
    if not DISCORD_WEBHOOK_URL:
        raise RuntimeError("Missing DISCORD_DEV_WH env var.")

    group_name, members = get_group_members(WOM_GROUP_ID)
    filename, rows = build_report(group_name, members)
    top = rows[0] if rows else None
    send_file_to_discord(DISCORD_WEBHOOK_URL, filename, top)


if __name__ == "__main__":
    main()
