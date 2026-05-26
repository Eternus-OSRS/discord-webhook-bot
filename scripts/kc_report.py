import os
import requests

WEBHOOK_URL = os.getenv("DISCORD_DEV_WH")

COMP1_ID = 138139
COMP2_ID = 138140


def get_comp_data(comp_id):
    url = f"https://api.wiseoldman.net/v2/competitions/{comp_id}"

    r = requests.get(url)

    if r.status_code != 200:
        raise Exception(f"Failed to fetch competition {comp_id}: {r.text}")

    return r.json()


def extract_scores(comp):
    scores = {}

    for p in comp["participations"]:

        # ✅ BEST: use name if present
        if "player" in p and p["player"]:
            name = p["player"]["displayName"]

        # ✅ fallback (rare)
        else:
            name = f"Player_{p['playerId']}"

        gained = p.get("progress", {}).get("gained", 0)

        if gained is None:
            gained = 0

        scores[name] = gained

    return scores


def build_report(comp1, comp2):
    scores1 = extract_scores(comp1)
    scores2 = extract_scores(comp2)

    players = set(scores1) | set(scores2)

    results = []

    for name in players:
        kc1 = scores1.get(name, 0)
        kc2 = scores2.get(name, 0)
        total = kc1 + kc2

        results.append((name, kc1, kc2, total))

    # ✅ sort by total descending
    results.sort(key=lambda x: x[3], reverse=True)

    filename = "kc_report.txt"

    boss1 = comp1.get("metric", "Boss1")
    boss2 = comp2.get("metric", "Boss2")

    with open(filename, "w", encoding="utf-8") as f:
        f.write("BOTW Combined KC Report\n\n")

        f.write(f"{'Rank':<6}{'Name':<22}{boss1:<12}{boss2:<12}{'Total'}\n")
        f.write("-" * 60 + "\n")

        for i, (name, kc1, kc2, total) in enumerate(results, 1):
            f.write(f"{i:<6}{name:<22}{kc1:<12}{kc2:<12}{total}\n")

    return filename, results


def send_to_discord(filename, results):
    if results:
        top = results[0]
        message = f"🏆 BOTW Leader: {top[0]} — {top[3]} KC total"
    else:
        message = "BOTW report generated."

    with open(filename, "rb") as f:
        r = requests.post(
            WEBHOOK_URL,
            data={"content": message},
            files={"file": (filename, f)}
        )

    if r.status_code not in (200, 204):
        raise Exception(f"Discord upload failed: {r.text}")


def main():
    print("Fetching competitions (optimal mode)...")

    comp1 = get_comp_data(COMP1_ID)
    comp2 = get_comp_data(COMP2_ID)

    print("Combining KC...")

    filename, results = build_report(comp1, comp2)

    print("Sending to Discord...")

    send_to_discord(filename, results)

    print("✅ Done!")


if __name__ == "__main__":
    main()
