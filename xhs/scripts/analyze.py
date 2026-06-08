"""
XHS data analyzer — reads collected data and generates statistics.

Usage:
    python3 xhs/scripts/analyze.py              # full report
    python3 xhs/scripts/analyze.py --export csv  # export to CSV
"""

import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def load_all_data(subdir: str) -> list[dict]:
    """Load all JSON files from a data subdirectory."""
    data_path = DATA_DIR / subdir
    if not data_path.exists():
        return []

    records = []
    for json_file in sorted(data_path.glob("*.json")):
        try:
            content = json_file.read_text(encoding="utf-8")
            parsed = json.loads(content)
            if isinstance(parsed, list):
                records.extend(parsed)
            elif isinstance(parsed, dict):
                records.append(parsed)
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            print(f"Warning: skipping {json_file.name}: {e}")
    return records


def deduplicate(records: list[dict], key: str = "user_id") -> list[dict]:
    """Remove duplicate records by key field."""
    seen = set()
    unique = []
    for r in records:
        k = r.get(key) or r.get("note_id") or r.get("id") or id(r)
        if k not in seen:
            seen.add(k)
            unique.append(r)
    return unique


def classify_gender(record: dict) -> str:
    """Guess gender from nickname or gender field."""
    gender = record.get("gender", "")
    if gender in ("男", "male", "m"):
        return "male"
    if gender in ("女", "female", "f"):
        return "female"

    nickname = record.get("nickname", "") or record.get("user_name", "")
    male_hints = ["哥", "叔", "兄", "先生", "爸", "大叔", "boy", "男"]
    female_hints = ["姐", "妹", "姑娘", "小姐", "妈", "girl", "女", "太太"]

    for h in male_hints:
        if h in nickname:
            return "male"
    for h in female_hints:
        if h in nickname:
            return "female"

    return "unknown"


def classify_domain(record: dict) -> str:
    """Guess domain from filename or content."""
    source = record.get("_source_file", "")
    if "hiking" in source or "徒步" in source:
        return "hiking"
    if "trail" in source or "越野" in source:
        return "trail_running"
    return "unknown"


def analyze_bloggers(bloggers: list[dict]) -> dict:
    """Generate blogger statistics."""
    stats = {
        "total": len(bloggers),
        "by_domain": defaultdict(int),
        "by_gender": defaultdict(int),
        "by_domain_gender": defaultdict(lambda: defaultdict(int)),
        "follower_distribution": {"1k-5k": 0, "5k-10k": 0, "10k+": 0, "other": 0},
    }

    for b in bloggers:
        domain = classify_domain(b)
        gender = classify_gender(b)
        followers = b.get("fans", 0) or b.get("follower_count", 0) or 0

        stats["by_domain"][domain] += 1
        stats["by_gender"][gender] += 1
        stats["by_domain_gender"][domain][gender] += 1

        if 1000 <= followers < 5000:
            stats["follower_distribution"]["1k-5k"] += 1
        elif 5000 <= followers < 10000:
            stats["follower_distribution"]["5k-10k"] += 1
        elif followers >= 10000:
            stats["follower_distribution"]["10k+"] += 1
        else:
            stats["follower_distribution"]["other"] += 1

    return stats


def analyze_posts(posts: list[dict]) -> dict:
    """Generate post statistics."""
    stats = {
        "total": len(posts),
        "avg_likes": 0,
        "avg_comments": 0,
        "avg_collects": 0,
        "type_distribution": defaultdict(int),
    }

    if not posts:
        return stats

    total_likes = sum(p.get("liked_count", 0) or 0 for p in posts)
    total_comments = sum(p.get("comment_count", 0) or 0 for p in posts)
    total_collects = sum(p.get("collected_count", 0) or 0 for p in posts)

    stats["avg_likes"] = round(total_likes / len(posts), 1)
    stats["avg_comments"] = round(total_comments / len(posts), 1)
    stats["avg_collects"] = round(total_collects / len(posts), 1)

    for p in posts:
        note_type = p.get("type", "unknown")
        stats["type_distribution"][note_type] += 1

    return stats


def print_report(blogger_stats: dict, post_stats: dict):
    """Print a formatted report to stdout."""
    print("\n" + "=" * 50)
    print("  XHS Data Collection Report")
    print("=" * 50)

    print(f"\n--- Bloggers ({blogger_stats['total']} total) ---")

    if blogger_stats["total"] > 0:
        print("\nBy domain:")
        for domain, count in sorted(blogger_stats["by_domain"].items()):
            print(f"  {domain}: {count}")

        print("\nBy gender:")
        for gender, count in sorted(blogger_stats["by_gender"].items()):
            pct = round(count / blogger_stats["total"] * 100, 1)
            print(f"  {gender}: {count} ({pct}%)")

        male_count = blogger_stats["by_gender"].get("male", 0)
        male_pct = round(male_count / blogger_stats["total"] * 100, 1) if blogger_stats["total"] > 0 else 0
        target_met = male_pct >= 40
        print(f"\nMale ratio: {male_pct}% {'PASS' if target_met else 'BELOW 40% TARGET'}")

        print("\nFollower distribution:")
        for tier, count in blogger_stats["follower_distribution"].items():
            print(f"  {tier}: {count}")

    print(f"\n--- Posts ({post_stats['total']} total) ---")
    if post_stats["total"] > 0:
        print(f"  Avg likes:    {post_stats['avg_likes']}")
        print(f"  Avg comments: {post_stats['avg_comments']}")
        print(f"  Avg collects: {post_stats['avg_collects']}")
        print("\n  Type distribution:")
        for t, count in post_stats["type_distribution"].items():
            print(f"    {t}: {count}")

    print("\n" + "=" * 50)


def export_csv(bloggers: list[dict], output_path: Path):
    """Export blogger data to CSV."""
    if not bloggers:
        print("No blogger data to export.")
        return

    fields = ["nickname", "user_id", "fans", "gender", "desc", "ip_location",
              "liked_count", "collected_count", "note_count"]

    with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for b in bloggers:
            b["gender"] = classify_gender(b)
            writer.writerow(b)

    print(f"Exported {len(bloggers)} bloggers to {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Analyze collected XHS data")
    parser.add_argument("--export", choices=["csv"], help="Export format")
    parser.add_argument("--output", type=str, default=None, help="Export output path")
    args = parser.parse_args()

    bloggers = load_all_data("bloggers")
    posts = load_all_data("posts")

    for b in bloggers:
        if "_source_file" not in b:
            b["_source_file"] = ""

    bloggers = deduplicate(bloggers, "user_id")
    posts = deduplicate(posts, "note_id")

    blogger_stats = analyze_bloggers(bloggers)
    post_stats = analyze_posts(posts)
    print_report(blogger_stats, post_stats)

    if args.export == "csv":
        out = Path(args.output) if args.output else DATA_DIR.parent / "output" / "bloggers_export.csv"
        out.parent.mkdir(parents=True, exist_ok=True)
        export_csv(bloggers, out)


if __name__ == "__main__":
    main()
