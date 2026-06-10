"""
Classify collected blogger profiles by follower tier and gender.
Reports progress toward the 120-blogger target.

Usage:
    python3 xhs/scripts/classify_bloggers.py                       # full report
    python3 xhs/scripts/classify_bloggers.py --domain hiking       # hiking only
    python3 xhs/scripts/classify_bloggers.py --export result.csv   # export CSV
"""

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

TIERS = [
    ("1k-5k", 1000, 5000),
    ("5k-10k", 5000, 10000),
    ("10k+", 10000, float("inf")),
]

TARGET_PER_TIER = 20
MIN_MALE_PER_TIER = 8


def load_profiles(domain: str) -> list[dict]:
    profiles_file = DATA_DIR / "bloggers" / f"{domain}_profiles.json"
    if not profiles_file.exists():
        return []
    data = json.loads(profiles_file.read_text(encoding="utf-8"))
    return data if isinstance(data, list) else []


def load_users(domain: str) -> list[dict]:
    users_file = DATA_DIR / f"users_{domain}.json"
    if not users_file.exists():
        return []
    data = json.loads(users_file.read_text(encoding="utf-8"))
    return data if isinstance(data, list) else []


def estimate_tier_from_engagement(user: dict) -> str | None:
    posts = max(user.get("post_count", 1), 1)
    avg_likes = user.get("total_likes", 0) / posts
    avg_engagement = (user.get("total_likes", 0) + user.get("total_collects", 0)) / posts

    if avg_engagement >= 5000:
        return "10k+"
    elif avg_engagement >= 500:
        return "5k-10k"
    elif avg_engagement >= 50:
        return "1k-5k"
    return None


def classify_tier(fans: int) -> str | None:
    for label, lo, hi in TIERS:
        if lo <= fans < hi:
            return label
    return None


def gender_label(g) -> str:
    if isinstance(g, int):
        if g == 0:
            return "male"
        if g == 1:
            return "female"
        return "unknown"
    g = (str(g) if g else "").lower()
    if g in ("male", "男"):
        return "male"
    if g in ("female", "女"):
        return "female"
    return "unknown"


def nickname_gender_hint(nickname: str) -> str:
    male_hints = ["哥", "叔", "兄", "先生", "爸", "大叔", "boy", "男"]
    female_hints = ["姐", "妹", "姑娘", "小姐", "妈", "girl", "女", "太太"]
    for h in male_hints:
        if h in nickname:
            return "male"
    for h in female_hints:
        if h in nickname:
            return "female"
    return "unknown"


def resolve_gender(profile: dict) -> str:
    g = gender_label(profile.get("gender", ""))
    if g != "unknown":
        return g
    return nickname_gender_hint(profile.get("nickname", ""))


def report(domains: list[str]):
    for domain in domains:
        profiles = load_profiles(domain)
        mode = "profile"

        if not profiles:
            profiles = load_users(domain)
            mode = "engagement"

        if not profiles:
            print(f"\n[{domain}] No data found.")
            continue

        seen = set()
        unique = []
        for p in profiles:
            uid = p.get("user_id")
            if uid and uid not in seen:
                seen.add(uid)
                unique.append(p)

        if mode == "profile":
            below_min = [p for p in unique if p.get("fans", 0) < 1000]
            eligible = [p for p in unique if p.get("fans", 0) >= 1000]
        else:
            below_min = []
            eligible = []
            for p in unique:
                tier = estimate_tier_from_engagement(p)
                if tier:
                    eligible.append(p)
                else:
                    below_min.append(p)

        buckets: dict[str, list[dict]] = defaultdict(list)
        for p in eligible:
            if mode == "profile":
                tier = classify_tier(p["fans"])
            else:
                tier = estimate_tier_from_engagement(p)
            if tier:
                p["_tier"] = tier
                p["_gender"] = resolve_gender(p)
                buckets[tier].append(p)

        domain_label = "徒步" if domain == "hiking" else "越野跑"
        mode_label = "精确（profile）" if mode == "profile" else "估算（engagement-based）"
        print(f"\n{'='*60}")
        print(f"  {domain_label} ({domain})  —  {len(unique)} 个用户")
        print(f"  分类模式: {mode_label}")
        print(f"{'='*60}")
        if mode == "engagement":
            print(f"  互动量过低（排除）: {len(below_min)}")
        else:
            print(f"  粉丝 <1k（排除）:   {len(below_min)}")
        print(f"  入选候选:           {len(eligible)}\n")

        total_have = 0
        total_male = 0
        for tier_label, _, _ in TIERS:
            items = buckets.get(tier_label, [])
            males = [p for p in items if p["_gender"] == "male"]
            females = [p for p in items if p["_gender"] == "female"]
            unknowns = [p for p in items if p["_gender"] == "unknown"]

            have = len(items)
            need = max(0, TARGET_PER_TIER - have)
            male_need = max(0, MIN_MALE_PER_TIER - len(males))

            status = "OK" if have >= TARGET_PER_TIER and len(males) >= MIN_MALE_PER_TIER else "NEED MORE"

            print(f"  {tier_label:>6}  total={have:>3}  male={len(males):>2}  female={len(females):>2}  unknown={len(unknowns):>2}  | {status}")
            if need > 0:
                print(f"          -> need {need} more bloggers")
            if male_need > 0:
                print(f"          -> need {male_need} more males")

            total_have += have
            total_male += len(males)

        male_pct = round(total_male / total_have * 100, 1) if total_have else 0
        print(f"\n  Summary: {total_have} eligible, {total_male} male ({male_pct}%)")
        target_total = TARGET_PER_TIER * len(TIERS)
        if total_have >= target_total:
            print(f"  Target {target_total}: REACHED")
        else:
            print(f"  Target {target_total}: need {target_total - total_have} more")

        if mode == "engagement":
            print(f"\n  ⚠ 注意：粉丝分层基于帖子互动量估算，非精确值")
            print(f"  获取精确数据需运行: fetch_profiles.py --domain {domain}")

    print()


def export_csv(domains: list[str], output_path: str):
    all_bloggers = []
    for domain in domains:
        profiles = load_profiles(domain)
        mode = "profile"
        if not profiles:
            profiles = load_users(domain)
            mode = "engagement"

        seen = set()
        for p in profiles:
            uid = p.get("user_id")
            if uid and uid not in seen:
                if mode == "profile":
                    if p.get("fans", 0) < 1000:
                        continue
                    tier = classify_tier(p["fans"])
                else:
                    tier = estimate_tier_from_engagement(p)
                if not tier:
                    continue
                seen.add(uid)
                p["_tier"] = tier
                p["_gender"] = resolve_gender(p)
                p["_domain"] = domain
                p["_mode"] = mode
                all_bloggers.append(p)

    if not all_bloggers:
        print("No eligible bloggers to export.")
        return

    fields = ["_domain", "_tier", "_mode", "user_id", "nickname", "_gender",
              "fans", "total_likes", "total_collects", "post_count",
              "ip_location", "source_keywords"]

    with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for b in sorted(all_bloggers, key=lambda x: (x["_domain"], x.get("_tier", ""), -x.get("total_likes", x.get("fans", 0)))):
            row = {**b}
            if isinstance(row.get("source_keywords"), list):
                row["source_keywords"] = ", ".join(row["source_keywords"])
            if isinstance(row.get("tag_list"), dict):
                row["tag_list"] = ", ".join(f"{k}:{v}" for k, v in row["tag_list"].items() if v)
            writer.writerow(row)

    print(f"Exported {len(all_bloggers)} bloggers to {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Classify XHS bloggers by tier and gender")
    parser.add_argument("--domain", choices=["hiking", "trail_running"],
                        help="Only report this domain")
    parser.add_argument("--export", type=str, default=None,
                        help="Export to CSV file")
    args = parser.parse_args()

    domains = [args.domain] if args.domain else ["hiking", "trail_running"]

    report(domains)

    if args.export:
        export_csv(domains, args.export)


if __name__ == "__main__":
    main()
