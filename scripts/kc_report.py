import os
import requests

WEBHOOK_URL = os.getenv("DISCORD_DEV_WH")

COMP1_ID = 138139
COMP2_ID = 138140


def get_standings(comp_id):
    url = f"https://api.wiseoldman.net/v2/competitions/{comp_id}/standings"

    r = requests.get(url)

    if r.status_code != 200:
        raise Exception(f"Failed to fetch standings {comp_id}: {r.text}")

    return r.json()


def extract_scores(standings):
    scores = {}

    for p in standings:
        # ✅ standings includes player object
        name = p["player"]["displayName"]

        gained = p.get("gained", 0)
        if gained is None:
            gained = 0

        scores[name] = gained

    return scores


def build_report(comp1_data, comp2_data):
    scores1 = extract_scores(comp1_data)
    scores2 = extract_scores(comp2_data)

    players = set(scores1) | set(scores2)

    results = []

    for name in players:
        kc1 = scores1.get(name, 0)
        kc2 = scores2.get(name, 0)
        total = kc1 + kc2

        results.append((name, kc1, kc2, total))

    # ✅ sort by total
    results.sort(key=lambda x: x[3], reverse=True)

    filename = "kc_report.txt"

    with open(filename, "w") as f:
        f.write("BOTW Combined KC Report\n\n")

        f.write(f"{'Rank':<6}{'Name':<22}{'Boss1':<12}{'Boss2':<12}{'Total'}\n")
        f.write("-" * 60 + "\n")

        for i, (name, kc1, kc2, total) in enumerate(results, 1):
            f.write(f"{i:<6}{name:<22}{kc1:<12}{kc2:<12}{total}\n")

    return filename, results


def send_to_discord(file, results):
    if results:
        top = results[0]
        message = f"🏆 BOTW Leader: {top[0]} — {top[3]} KC total"
    else:
        message = "BOTW report generated."

    with open(file, "rb") as f:
        r = requests.post(
            WEBHOOK_URL,
            data={"content": message},
            files={"file": (file, f)}
        )

    if r.status_code not in (200, 204):
        raise Exception(f"Discord upload failed: {r.text}")


def main():
    print("Fetching standings (fast mode)...")

    comp1 = get_standings(COMP1_ID)
    comp2 = get_standings(COMP2_ID)

    print("Combining results...")

    filename, results = build_report(comp1, comp2)

    print("Sending to Discord...")

    send_to_discord(filename, results)

    print("✅ Done!")


if __name__ == "__main__":
    main()
