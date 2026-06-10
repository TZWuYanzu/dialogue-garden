"""
XHS profile fetcher — uses Playwright persistent context + stealth.js.
Cookies are loaded from .env, no QR-code login needed.

Usage:
    python3 xhs/scripts/fetch_profiles.py --domain hiking           # fetch all
    python3 xhs/scripts/fetch_profiles.py --domain hiking --test 5   # test with 5
    python3 xhs/scripts/fetch_profiles.py --domain hiking --resume   # resume
"""

import argparse
import json
import os
import random
import re
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, BrowserContext

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
BROWSER_DATA_DIR = ROOT / "browser_data"
STEALTH_JS = ROOT / "MediaCrawler" / "libs" / "stealth.min.js"
ENV_FILE = ROOT / ".env"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

load_dotenv(ENV_FILE)


def _env_cookies() -> list[dict]:
    cookie_str = os.getenv("XHS_COOKIES", "")
    if not cookie_str:
        return []
    cookies = []
    for pair in cookie_str.split(";"):
        pair = pair.strip()
        if "=" in pair:
            k, v = pair.split("=", 1)
            cookies.append({
                "name": k.strip(),
                "value": v.strip(),
                "domain": ".xiaohongshu.com",
                "path": "/",
            })
    return cookies


def _launch_context(p, headless: bool) -> BrowserContext:
    context = p.chromium.launch_persistent_context(
        user_data_dir=str(BROWSER_DATA_DIR),
        headless=headless,
        user_agent=USER_AGENT,
        viewport={"width": 1920, "height": 1080},
        locale="zh-CN",
        args=["--disable-blink-features=AutomationControlled"],
    )
    if STEALTH_JS.exists():
        context.add_init_script(path=str(STEALTH_JS))
    context.add_cookies(_env_cookies())
    return context


def parse_creator_from_html(html: str) -> dict | None:
    match = re.search(r"<script>window\.__INITIAL_STATE__=(.+?)</script>", html, re.M)
    if match is None:
        return None

    raw = match.group(1).replace(":undefined", ":null")
    try:
        info = json.loads(raw, strict=False)
    except json.JSONDecodeError:
        return None

    user_page = info.get("user", {}).get("userPageData")
    if not user_page:
        return None

    basic = user_page.get("basicInfo", {})
    interactions = user_page.get("interactions", [])
    tags = user_page.get("tags", [])

    follows = fans = interaction = 0
    for item in interactions:
        t = item.get("type")
        count = _parse_count(item.get("count", "0"))
        if t == "follows":
            follows = count
        elif t == "fans":
            fans = count
        elif t == "interaction":
            interaction = count

    gender_val = basic.get("gender")
    if gender_val == 0:
        gender = "male"
    elif gender_val == 1:
        gender = "female"
    else:
        gender = "unknown"

    return {
        "nickname": basic.get("nickname", ""),
        "gender": gender,
        "avatar": basic.get("images", ""),
        "desc": basic.get("desc", ""),
        "ip_location": basic.get("ipLocation", ""),
        "follows": follows,
        "fans": fans,
        "interaction": interaction,
        "tag_list": {tag.get("tagType", ""): tag.get("name", "") for tag in tags},
    }


def _parse_count(val) -> int:
    if isinstance(val, int):
        return val
    s = str(val).strip()
    if s.endswith("万"):
        return int(float(s[:-1]) * 10000)
    try:
        return int(s)
    except ValueError:
        return 0


def load_checkpoint(domain: str) -> dict[str, dict]:
    cp_file = DATA_DIR / "bloggers" / f"{domain}_checkpoint.json"
    if cp_file.exists():
        return json.loads(cp_file.read_text(encoding="utf-8"))
    return {}


def save_checkpoint(domain: str, results: dict[str, dict]):
    bloggers_dir = DATA_DIR / "bloggers"
    bloggers_dir.mkdir(parents=True, exist_ok=True)
    cp_file = bloggers_dir / f"{domain}_checkpoint.json"
    cp_file.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")


def save_final(domain: str, fetched: dict[str, dict]):
    save_checkpoint(domain, fetched)
    bloggers_dir = DATA_DIR / "bloggers"
    bloggers_dir.mkdir(parents=True, exist_ok=True)
    output_file = bloggers_dir / f"{domain}_profiles.json"
    profiles = list(fetched.values())
    output_file.write_text(json.dumps(profiles, ensure_ascii=False, indent=2), encoding="utf-8")
    return output_file, len(profiles)


def do_fetch(args):
    users_file = DATA_DIR / f"users_{args.domain}.json"
    if not users_file.exists():
        print(f"Error: {users_file} not found. Run extract_users.py first.")
        sys.exit(1)

    users = json.loads(users_file.read_text(encoding="utf-8"))
    print(f"Loaded {len(users)} users for {args.domain}")

    fetched = load_checkpoint(args.domain) if args.resume else {}
    if fetched:
        print(f"Resuming from checkpoint: {len(fetched)} already fetched")

    with sync_playwright() as p:
        context = _launch_context(p, headless=True)
        page = context.new_page()

        # ── Warm up: visit homepage first ──
        print("Warming up browser session...")
        page.goto("https://www.xiaohongshu.com", wait_until="domcontentloaded", timeout=30000)
        time.sleep(3 + random.uniform(0, 2))

        # ── Validate session with retry ──
        print("Validating login session...")
        first_user = next((u for u in users if u["user_id"] not in fetched), None)
        if first_user is None:
            print("All users already fetched!")
            context.close()
            return

        result = None
        for attempt in range(3):
            page.goto(f"https://www.xiaohongshu.com/user/profile/{first_user['user_id']}",
                      wait_until="domcontentloaded", timeout=30000)
            time.sleep(3 + random.uniform(0, 2))

            if "captcha" in page.url or "login" in page.url:
                if attempt < 2:
                    wait = 60 * (attempt + 1)
                    print(f"  Captcha/login redirect (attempt {attempt+1}/3). Waiting {wait}s...")
                    time.sleep(wait)
                    continue
                else:
                    print("Session invalid after 3 attempts. Cookies may have expired.")
                    print("Please update XHS_COOKIES in xhs/.env and retry.")
                    context.close()
                    sys.exit(1)

            result = parse_creator_from_html(page.content())
            if result:
                break

            if attempt < 2:
                print(f"  Parse failed (attempt {attempt+1}/3), retrying...")
                time.sleep(10)

        if result is None:
            print("Could not parse profile data. Please check cookies.")
            context.close()
            sys.exit(1)

        fetched[first_user["user_id"]] = {"user_id": first_user["user_id"], **result, "domain": args.domain}
        print(f"  Session OK: {result['nickname']} (fans={result['fans']}, gender={result['gender']})")

        # ── Build fetch list ──
        to_fetch = [u for u in users if u["user_id"] not in fetched]
        if args.test:
            to_fetch = to_fetch[:args.test - 1]

        total = len(to_fetch)
        print(f"Fetching {total} remaining profiles (delay={args.delay}s)...\n")

        failures = []
        consecutive_captcha = 0

        for i, user in enumerate(to_fetch):
            uid = user["user_id"]
            delay = args.delay + random.uniform(0, 3)
            time.sleep(delay)

            try:
                page.goto(f"https://www.xiaohongshu.com/user/profile/{uid}",
                          wait_until="domcontentloaded", timeout=30000)
                time.sleep(2 + random.uniform(0, 1.5))

                # ── Captcha handling ──
                if "captcha" in page.url:
                    consecutive_captcha += 1
                    print(f"  [{i+1}/{total}] CAPTCHA for {user['nickname']}")

                    if consecutive_captcha >= 3:
                        save_final(args.domain, fetched)
                        print(f"\n  Stopped: 3 consecutive CAPTCHAs. {len(fetched)} profiles saved.")
                        print("  Please re-run with --login, then --resume to continue.")
                        context.close()
                        sys.exit(1)

                    wait = 60 + random.randint(0, 30)
                    print(f"  Waiting {wait}s before retry...")
                    time.sleep(wait)

                    page.goto(f"https://www.xiaohongshu.com/user/profile/{uid}",
                              wait_until="domcontentloaded", timeout=30000)
                    time.sleep(3)
                    if "captcha" in page.url:
                        failures.append(uid)
                        continue

                result = parse_creator_from_html(page.content())
                if result is None:
                    failures.append(uid)
                    print(f"  [{i+1}/{total}] SKIP: {user['nickname']} (parse failed)")
                    continue

                consecutive_captcha = 0
                fetched[uid] = {"user_id": uid, **result, "domain": args.domain}
                print(f"  [{i+1}/{total}] {result['nickname']}  fans={result['fans']}  gender={result['gender']}")

            except Exception as e:
                failures.append(uid)
                print(f"  [{i+1}/{total}] ERROR: {user['nickname']} — {e}")
                continue

            if (i + 1) % 10 == 0:
                save_checkpoint(args.domain, fetched)
                print(f"  ── checkpoint: {len(fetched)} profiles saved ──")

        context.close()

    # ── Final save ──
    output_file, count = save_final(args.domain, fetched)
    print(f"\nDone: {count} profiles -> {output_file}")
    if failures:
        fail_file = DATA_DIR / "bloggers" / f"{args.domain}_failures.json"
        fail_file.write_text(json.dumps(failures, ensure_ascii=False), encoding="utf-8")
        print(f"Failures ({len(failures)}): {fail_file}")


def main():
    parser = argparse.ArgumentParser(description="XHS profile fetcher")
    parser.add_argument("--domain", required=True, choices=["hiking", "trail_running"],
                        help="Domain to fetch profiles for")
    parser.add_argument("--test", type=int, default=0,
                        help="Only fetch N profiles for testing")
    parser.add_argument("--resume", action="store_true",
                        help="Resume from last checkpoint")
    parser.add_argument("--delay", type=float, default=6.0,
                        help="Base delay between requests in seconds")
    args = parser.parse_args()
    do_fetch(args)


if __name__ == "__main__":
    main()
