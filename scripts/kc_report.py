import requests

# ===== CONFIG =====
GROUP_ID = 123456   # <-- your WOM group ID
BOSS1 = "zulrah"    # change to your boss keys
BOSS2 = "vorkath"

WEBHOOK_URL = "YOUR_DISCORD_WEBHOOK"

# ==================

def get_group_members():
    url = f"https://api.wiseoldman.net/v2/groups/{GROUP_ID}"
    data = requests.get(url).json()
    return [m["player"]["username"] for m in data["memberships"]]

def get_player_kc(username):
    url = f"https://api.wiseoldman.net/v2/players/{username}"
    player = requests.post(url).json()

    bosses = player["latestSnapshot"]["data"]["bosses"]

    kc1 = bosses.get(BOSS1, {}).get("kills", 0)
    kc2 = bosses.get(BOSS2, {}).get("kills", 0)

    return kc1, kc2

def build_report():
    members = get_group_members()

    results = []

    for name in members:
        kc1, kc2 = get_player_kc(name)
        total = kc1 + kc2
        results.append((name, kc1, kc2, total))

    # sort by total descending
    results.sort(key=lambda x: x[3], reverse=True)

    # write file
    with open("kc_report.txt", "w") as f:
        f.write("Clan BOTW KC Report\n\n")
        f.write(f"{'Name':<20}{'Boss1':<10}{'Boss2':<10}{'Total'}\n")
        f.write("-" * 50 + "\n")

        for name, kc1, kc2, total in results:
            f.write(f"{name:<20}{kc1:<10}{kc2:<10}{total}\n")

def send_to_discord():
    with open("kc_report.txt", "rb") as f:
        files = {
            "file": ("kc_report.txt", f)
        }
        requests.post(WEBHOOK_URL, files=files)

if __name__ == "__main__":
    build_report()
    send_to_discord()
