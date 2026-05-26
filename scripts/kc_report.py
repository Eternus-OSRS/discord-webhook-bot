import os
import json
import time
import datetime as dt
from typing import List, Tuple
import requests

# ========= ENV CONFIG =========
WOM_GROUP_ID = os.getenv("WOM_GROUP_ID")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_DEV_WH")

# WOM boss metric keys (snake_case), e.g. zulrah, vorkath, alchemical_hydra, etc.
BOSS1 = os.getenv("BOSS1", "zulrah")
BOSS2 = os.getenv("BOSS2", "vorkath")

# Batch & pacing
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "10"))

# WOM default rate limit is tight; pace requests with headroom
# 20 req / 60s => 1 req every 3.0s. Use 3.3s for safety.
PER_REQUEST_DELAY_SECONDS = float(os.getenv("PER_REQUEST_DELAY_SECONDS", "3.3"))

# Retry behavior for 429s
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "10"))
BACKOFF_BASE_SECONDS = float(os.getenv("BACKOFF_BASE_SECONDS", "5"))
BACKOFF_MAX_SECONDS = float(os.getenv("BACKOFF_MAX_SECONDS", "60"))
# ==============================


def wom_request(method: str, url: str, **kwargs) -> requests.Response:
    """
    Makes a WOM request with 429 retry/backoff.
    """
    for attempt in range(1, MAX_RETRIES + 1):
        resp = requests.request(method, url, timeout=30, **kwargs)

        if resp.status_code == 429:
            retry_after = resp.headers.get("Retry-After")
            if retry_after and retry_after.isdigit():
                sleep_s = min(int(retry_after), BACKOFF_MAX_SECONDS)
            else:
                # exponential-ish backoff with a cap
                sleep_s = min(BACKOFF_BASE_SECONDS * (2 ** (attempt - 1)), BACKOFF_MAX_SECONDS)

            print(f"[WOM] 429 rate limited on {url}. Sleeping {sleep_s}s (attempt {attempt}/{MAX_RETRIES})...")
            time.sleep(sleep_s)
            continue

        # For other errors, raise with body context
        if resp.status_code >= 400:
            print(f"[WOM] Error {resp.status_code} on {url}. Body(first300)={resp.text[:300]!r}")
            resp.raise_for_status()

        return resp

    raise RuntimeError(f"WOM rate limit persisted after {MAX_RETRIES} retries for {url}")


def chunked(items: List[Tuple[str, str]], size: int):
    for i in range(0, len(items), size):
        yield items[i:i + size]


def get_group_members(group_id: str) -> Tuple[str, List[Tuple[str, str]]]:
    """
    GET /v2/groups/:id returns memberships with nested player objects (username/displayName). [1](https://codepal.ai/code-generator/query/cPnObwMa/discord-bot-say-hello)
    """
    url = f"https://api.wiseoldman.net/v2/groups/{group_id}"
    resp = wom_request("GET", url)
    data = resp.json()

    group_name = data.get("name", f"group_{group_id}")
    members = []
    for m in data.get("memberships", []):
        p = m.get("player") or {}
        username = p.get("username") or ""
        display = p.get("displayName") or username
        if username:
            members.append((display, username))

    # stable ordering
    members.sort(key=lambda x: x[0].lower())
    return group_name, members


def extract_kills(bosses: dict, boss_key: str) -> int:
    """
    WOM returns bosses.<metric>.kills; sometimes -1 if not present. Treat missing/-1 as 0. 
    """
    val = (bosses.get(boss_key) or {}).get("kills", 0)
    if val is None or val < 0:
        return 0
    return int(val)


def get_player_boss_kcs(username: str) -> Tuple[int, int]:
    """
    POST /v2/players/:username returns PlayerDetails with latestSnapshot.data.bosses. 
    We fetch ONCE and extract both bosses from the same payload.
    """
    url = f"https://api.wiseoldman.net/v2/players/{username}"
    resp = wom_request("POST", url)
    data = resp.json()

    bosses = (((data.get("latestSnapshot") or {}).get("data") or {}).get("bosses") or {})
    kc1 = extract_kills(bosses, BOSS1)
    kc2 = extract_kills(bosses, BOSS2)
    return kc1, kc2


def build_report(group_name: str, members: List[Tuple[str, str]]) -> Tuple[str, List[Tuple[str, str, int, int, int]]]:
    """
    Builds txt report and returns filename + rows.
    """
    rows = []
    total_members = len(members)

    for batch_num, batch in enumerate(chunked(members, BATCH_SIZE), start=1):
        start_ix = (batch_num - 1) * BATCH_SIZE + 1
        end_ix = min(batch_num * BATCH_SIZE, total_members)
        print(f"[REPORT] Processing batch {batch_num} ({start_ix}-{end_ix} of {total_members})...")

        for display, username in batch:
            kc1, kc2 = get_player_boss_kcs(username)
            total = kc1 + kc2
            rows.append((display, username, kc1, kc2, total))

            # pacing to stay under WOM rate limits
            time.sleep(PER_REQUEST_DELAY_SECONDS)

    # sort by total desc then name
    rows.sort(key=lambda x: (-x[4], x[0].lower()))

    ts_iso = dt.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%SZ")
    ts_file = dt.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filename = f"kc_report_{BOSS1}_{BOSS2}_{ts_file}.txt".replace(" ", "_")

    with open(filename, "w", encoding="utf-8", newline="\n") as f:
        f.write("Clan BOTW KC Report (Combined)\n")
        f.write(f"Group: {group_name}\n")
        f.write(f"Boss 1 (WOM key): {BOSS1}\n")
        f.write(f"Boss 2 (WOM key): {BOSS2}\n")
        f.write(f"Generated (UTC): {ts_iso}\n\n")

        header = f"{'Name':<22}{BOSS1:<12}{BOSS2:<12}{'Total':<8}"
        f.write(header + "\n")
        f.write("-" * max(54, len(header)) + "\n")

        for display, username, kc1, kc2, total in rows:
            name = (display[:21] + "…") if len(display) > 22 else display
            f.write(f"{name:<22}{kc1:<12}{kc2:<12}{total:<8}\n")

    return filename, rows


def send_file_to_discord(webhook_url: str, filename: str, top_row):
    """
    Upload file to Discord webhook using multipart/form-data with payload_json + file part. [2](https://joniii.dev/docs/discord-bot-template)[3](https://www.techbloat.com/how-to-make-a-discord-bot-with-codes-easiest-guide.html)
    """
    content = "BOTW combined KC report attached."
    if top_row:
        content += f" Leader: {top_row[0]} ({top_row[4]} total)"

    payload = {"content": content}

    with open(filename, "rb") as f:
        files = {"file1": (filename, f, "text/plain; charset=utf-8")}
        resp = requests.post(
            webhook_url,
            data={"payload_json": json.dumps(payload)},
            files=files,
            timeout=60
        )

    if resp.status_code >= 400:
        print(f"[DISCORD] Error {resp.status_code}. Body(first300)={resp.text[:300]!r}")
        resp.raise_for_status()

    print(f"✅ Sent {filename} to Discord (status={resp.status_code}).")


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
