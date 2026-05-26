import json
import requests

def send_to_discord(filename, filepath, count, group_name):
    # Plain text only. No markdown, no links, no backticks.
    payload = {
        "content": "Clan members export attached."
    }

    with open(filepath, "rb") as f:
        files = {
            "file1": (filename, f, "text/plain; charset=utf-8")
        }

        # Use proper JSON for payload_json in multipart form-data [1](https://birdie0.github.io/discord-webhooks-guide/structure/file.html)[2](https://docs.discord.com/developers/resources/webhook)
        resp = requests.post(
            DISCORD_WEBHOOK_URL,
            data={"payload_json": json.dumps(payload)},
            files=files,
            timeout=60
        )

    # Make the workflow fail if Discord rejects it
    print(f"[DISCORD] status={resp.status_code}")
    print(f"[DISCORD] body(first200)={resp.text[:200]!r}")
    resp.raise_for_status()
