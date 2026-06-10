"""
Extract unique users from post data and write a deduplicated user list.

Usage:
    python3 xhs/scripts/extract_users.py --domain hiking
    python3 xhs/scripts/extract_users.py --domain trail_running
    python3 xhs/scripts/extract_users.py                          # both domains
"""

import argparse
import json
from collections import defaultdict
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def parse_count(val) -> int:
    if not val:
        return 0
    s = str(val).strip()
    if s.endswith("万"):
        return int(float(s[:-1]) * 10000)
    try:
        return int(s)
    except ValueError:
        return 0


def extract_users(domain: str) -> list[dict]:
    posts_dir = DATA_DIR / "posts"
    users: dict[str, dict] = {}

    for json_file in sorted(posts_dir.glob(f"{domain}_*_search_contents_*.json")):
        records = json.loads(json_file.read_text(encoding="utf-8"))
        if not isinstance(records, list):
            continue

        for r in records:
            uid = r.get("user_id")
            if not uid:
                continue

            if uid not in users:
                users[uid] = {
                    "user_id": uid,
                    "nickname": r.get("nickname", ""),
                    "avatar": r.get("avatar", ""),
                    "ip_location": r.get("ip_location", ""),
                    "post_count": 0,
                    "total_likes": 0,
                    "total_collects": 0,
                    "total_comments": 0,
                    "source_keywords": set(),
                    "note_ids": [],
                    "sample_xsec_token": r.get("xsec_token", ""),
                }

            u = users[uid]
            u["post_count"] += 1
            u["total_likes"] += parse_count(r.get("liked_count"))
            u["total_collects"] += parse_count(r.get("collected_count"))
            u["total_comments"] += parse_count(r.get("comment_count"))
            u["source_keywords"].add(r.get("source_keyword", ""))
            u["note_ids"].append(r.get("note_id", ""))
            if not u["sample_xsec_token"] and r.get("xsec_token"):
                u["sample_xsec_token"] = r["xsec_token"]

    result = []
    for u in users.values():
        u["source_keywords"] = sorted(u["source_keywords"] - {""})
        result.append(u)

    result.sort(key=lambda x: x["total_likes"], reverse=True)
    return result


def main():
    parser = argparse.ArgumentParser(description="Extract unique users from post data")
    parser.add_argument("--domain", choices=["hiking", "trail_running"],
                        help="Domain to extract (default: both)")
    args = parser.parse_args()

    domains = [args.domain] if args.domain else ["hiking", "trail_running"]

    for domain in domains:
        users = extract_users(domain)
        if not users:
            print(f"[{domain}] No post data found.")
            continue

        output = DATA_DIR / f"users_{domain}.json"
        output.write_text(json.dumps(users, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[{domain}] Extracted {len(users)} unique users -> {output}")


if __name__ == "__main__":
    main()
