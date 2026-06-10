"""
XHS data collector — one command to search, collect, and organize.

Uses CDP mode to connect to your local Chrome browser's Xiaohongshu session.
No manual cookie management needed — just stay logged in via Chrome.

Usage:
    python3 xhs/scripts/collect.py "徒步" 50
    python3 xhs/scripts/collect.py "徒步,登山" 100 --comments
    python3 xhs/scripts/collect.py "越野跑" 50 --comments --extract-users
    python3 xhs/scripts/collect.py "徒步" 50 --label hiking_round2
    python3 xhs/scripts/collect.py --batch --domain hiking          # YAML batch mode
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MC_DIR = ROOT / "MediaCrawler"
DATA_DIR = ROOT / "data"
POSTS_DIR = DATA_DIR / "posts"
CACHE_DIR = ROOT / "cache" / "raw_output"
CONFIG_FILE = ROOT / "config" / "search_tasks.yaml"


def build_mc_command(keyword: str, max_notes: int,
                     output_dir: Path, comments: bool = False) -> list[str]:
    main_py = MC_DIR / "main.py"
    if not main_py.exists():
        print(f"Error: MediaCrawler not found at {MC_DIR}")
        sys.exit(1)

    args = [
        "--platform", "xhs",
        "--type", "search",
        "--keywords", keyword,
        "--crawler_max_notes_count", str(max_notes),
        "--save_data_option", "json",
        "--save_data_path", str(output_dir),
        "--get_comment", str(comments),
    ]

    uv_path = shutil.which("uv")
    if uv_path and (MC_DIR / "uv.lock").exists():
        return [uv_path, "run", "--project", str(MC_DIR), "python", str(main_py)] + args
    venv_python = MC_DIR / ".venv" / "bin" / "python3"
    python_cmd = str(venv_python) if venv_python.exists() else "python3"
    return [python_cmd, str(main_py)] + args


def run_crawl(keyword: str, max_notes: int,
              output_dir: Path, comments: bool = False) -> bool:
    cmd = build_mc_command(keyword, max_notes, output_dir, comments)
    print(f"\n{'='*50}")
    print(f"  关键词: {keyword}")
    print(f"  数量:   {max_notes}")
    print(f"  评论:   {'是' if comments else '否'}")
    print(f"{'='*50}")
    print()
    print("登录方式: CDP (复用本机 Chrome 登录态)")
    print("前提条件: Chrome 中已登录 xiaohongshu.com")
    print()
    print("提示: 如果浏览器弹出滑块/验证码，请手动完成验证")
    print("      采集过程中请勿关闭浏览器窗口")
    print()
    sys.stdout.flush()

    try:
        subprocess.run(cmd, cwd=str(MC_DIR), check=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"\n采集异常 (exit code {e.returncode})")
        print("可能原因:")
        print("  1. Chrome 中小红书未登录 → 请先在 Chrome 打开 xiaohongshu.com 登录")
        print("  2. 登录态过期 → 请在 Chrome 刷新小红书页面确认仍在登录状态")
        print("  3. 被平台限制 → 等待一段时间后重试")
        return False
    except KeyboardInterrupt:
        print("\n手动中断采集")
        return False


def make_label(keywords: str) -> str:
    first = keywords.split(",")[0].strip()
    safe = re.sub(r'[^\w一-鿿]', '_', first).strip('_')
    return safe or "collect"


def organize_results(raw_dir: Path, label: str) -> list[Path]:
    POSTS_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    organized = []

    for json_file in sorted(raw_dir.glob("**/*.json")):
        content = json_file.read_text(encoding="utf-8").strip()
        if not content:
            continue

        stem = json_file.stem.lower()
        if "comment" in stem:
            dest_name = f"{label}_comments_{today}_{timestamp}.json"
        else:
            dest_name = f"{label}_contents_{today}_{timestamp}.json"

        dest = POSTS_DIR / dest_name
        if dest.exists():
            dest_name = f"{label}_{stem}_{today}_{timestamp}.json"
            dest = POSTS_DIR / dest_name

        shutil.copy2(json_file, dest)
        organized.append(dest)

    return organized


def extract_users_from_files(content_files: list[Path], label: str) -> Path | None:
    from extract_users import parse_count

    users: dict[str, dict] = {}
    for f in content_files:
        if "comment" in f.name:
            continue
        try:
            records = json.loads(f.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
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

    if not users:
        return None

    result = []
    for u in users.values():
        u["source_keywords"] = sorted(u["source_keywords"] - {""})
        result.append(u)
    result.sort(key=lambda x: x["total_likes"], reverse=True)

    output = DATA_DIR / f"users_{label}.json"
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return output


def print_summary(organized: list[Path], users_file: Path | None = None):
    print()
    print("=" * 50)
    print("  采集完成!")
    print("=" * 50)

    total_records = 0
    for f in organized:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            count = len(data) if isinstance(data, list) else 1
        except Exception:
            count = 0
        total_records += count
        kind = "评论" if "comment" in f.name else "帖子"
        print(f"  {kind}: {count} 条 -> {f.name}")

    if users_file:
        try:
            users = json.loads(users_file.read_text(encoding="utf-8"))
            print(f"  用户: {len(users)} 人 -> {users_file.name}")
        except Exception:
            pass

    print()
    print(f"数据目录: {POSTS_DIR}")
    print("=" * 50)


def run_batch_mode(domain: str | None = None):
    import yaml

    if not CONFIG_FILE.exists():
        print(f"Error: 配置文件不存在: {CONFIG_FILE}")
        sys.exit(1)

    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    settings = config["settings"]
    max_notes = settings["max_notes_per_keyword"]
    comments = settings.get("enable_comments", False)

    for dom in config["domains"]:
        if domain and dom["name"] != domain:
            continue

        print(f"\n{'#'*50}")
        print(f"# 领域: {dom['label']} ({dom['name']})")
        print(f"{'#'*50}")

        for tier in dom["tiers"]:
            tier_label = f"{dom['name']}_{tier['label']}"
            raw_dir = CACHE_DIR / tier_label
            raw_dir.mkdir(parents=True, exist_ok=True)

            for keyword in dom["keywords"]:
                run_crawl(keyword, max_notes, raw_dir, comments)

            organize_results(raw_dir, tier_label)

    print("\n批量采集完成!")


def main():
    parser = argparse.ArgumentParser(
        description="小红书数据采集工具 (CDP 模式，复用 Chrome 登录态)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s "徒步" 50                     搜索"徒步"采集50条帖子
  %(prog)s "徒步,登山" 100 --comments    多关键词 + 采集评论
  %(prog)s "越野跑" 50 --extract-users   采集后自动提取用户列表
  %(prog)s --batch --domain hiking       按YAML配置批量采集

前提: 请先在 Chrome 浏览器中登录 xiaohongshu.com
""",
    )

    parser.add_argument("keywords", nargs="?",
                        help="搜索关键词，多个用逗号分隔 (如 \"徒步,登山\")")
    parser.add_argument("max_count", nargs="?", type=int, default=20,
                        help="采集帖子数量 (默认: 20)")
    parser.add_argument("--comments", action="store_true",
                        help="同时采集评论")
    parser.add_argument("--label",
                        help="输出文件标签 (默认: 自动从关键词生成)")
    parser.add_argument("--extract-users", action="store_true",
                        help="采集完成后自动提取用户列表")
    parser.add_argument("--batch", action="store_true",
                        help="按 YAML 配置批量采集")
    parser.add_argument("--domain", choices=["hiking", "trail_running"],
                        help="批量模式下只采集指定领域")

    args = parser.parse_args()

    if args.batch:
        run_batch_mode(args.domain)
        return

    if not args.keywords:
        parser.print_help()
        print("\n请提供搜索关键词，例如:")
        print('  python3 xhs/scripts/collect.py "徒步" 50')
        sys.exit(1)

    label = args.label or make_label(args.keywords)

    raw_dir = CACHE_DIR / label
    raw_dir.mkdir(parents=True, exist_ok=True)

    success = run_crawl(
        keyword=args.keywords,
        max_notes=args.max_count,
        output_dir=raw_dir,
        comments=args.comments,
    )

    if not success:
        remaining = list(raw_dir.glob("**/*.json"))
        if not remaining:
            print("\n未采集到数据")
            sys.exit(1)
        print("\n采集中断，整理已采集的数据...")

    organized = organize_results(raw_dir, label)

    users_file = None
    if args.extract_users and organized:
        users_file = extract_users_from_files(organized, label)

    if organized:
        print_summary(organized, users_file)
    else:
        print("\n未找到采集结果文件")


if __name__ == "__main__":
    main()
