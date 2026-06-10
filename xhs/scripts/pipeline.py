"""
XHS data pipeline — unified entry point for collection and cleaning.

Chains: collect → extract_users → fetch_profiles → classify

Usage:
    python3 xhs/scripts/pipeline.py "徒步,登山" 100 --comments
    python3 xhs/scripts/pipeline.py "越野跑" 50 --steps collect,extract
    python3 xhs/scripts/pipeline.py --steps classify --domain hiking
    python3 xhs/scripts/pipeline.py --steps fetch,classify --domain hiking
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
ROOT = SCRIPTS_DIR.parent
DATA_DIR = ROOT / "data"

ALL_STEPS = ["collect", "extract", "fetch", "classify"]


def run_script(script_name: str, args: list[str], label: str) -> dict:
    script = SCRIPTS_DIR / script_name
    if not script.exists():
        return {"step": label, "status": "error", "message": f"{script_name} not found"}

    cmd = [sys.executable, str(script)] + args
    print(f"\n{'='*50}")
    print(f"  步骤: {label}")
    print(f"  命令: python3 xhs/scripts/{script_name} {' '.join(args)}")
    print(f"{'='*50}\n")
    sys.stdout.flush()

    try:
        result = subprocess.run(cmd, cwd=str(ROOT), capture_output=False, text=True)
        if result.returncode == 0:
            return {"step": label, "status": "ok"}
        return {"step": label, "status": "error", "exit_code": result.returncode}
    except KeyboardInterrupt:
        return {"step": label, "status": "interrupted"}
    except Exception as e:
        return {"step": label, "status": "error", "message": str(e)}


def step_collect(keywords: str, max_count: int, comments: bool, label: str) -> dict:
    args = [keywords, str(max_count)]
    if comments:
        args.append("--comments")
    args.extend(["--label", label])
    return run_script("collect.py", args, "collect")


def step_extract(label: str) -> dict:
    domain = label
    args = ["--domain", domain] if domain in ("hiking", "trail_running") else []
    return run_script("extract_users.py", args, "extract")


def step_fetch(domain: str) -> dict:
    if not domain:
        return {"step": "fetch", "status": "skipped", "message": "需要指定 --domain"}
    return run_script("fetch_profiles.py", ["--domain", domain, "--resume"], "fetch")


def step_classify(domain: str | None) -> dict:
    args = []
    if domain:
        args.extend(["--domain", domain])
    return run_script("classify_bloggers.py", args, "classify")


def detect_data_state(domain: str | None) -> dict:
    state = {}
    domains = [domain] if domain else ["hiking", "trail_running"]
    for d in domains:
        users_file = DATA_DIR / f"users_{d}.json"
        profiles_file = DATA_DIR / "bloggers" / f"{d}_profiles.json"
        posts = list((DATA_DIR / "posts").glob(f"{d}_*contents*.json")) if (DATA_DIR / "posts").exists() else []
        state[d] = {
            "posts_files": len(posts),
            "users_extracted": users_file.exists(),
            "users_count": len(json.loads(users_file.read_text())) if users_file.exists() else 0,
            "profiles_fetched": profiles_file.exists(),
        }
    return state


def main():
    parser = argparse.ArgumentParser(
        description="小红书数据采集清洗流水线",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s "徒步,登山" 100 --comments       完整流水线
  %(prog)s "越野跑" 50 --steps collect,extract  只采集+提取
  %(prog)s --steps classify --domain hiking     只跑分类
  %(prog)s --status                              查看数据状态

步骤说明:
  collect   搜索小红书并采集帖子数据
  extract   从帖子中提取去重用户列表
  fetch     抓取用户详细 profile（粉丝数、性别等）
  classify  按粉丝层级和性别分类统计
""",
    )

    parser.add_argument("keywords", nargs="?",
                        help="搜索关键词，多个用逗号分隔")
    parser.add_argument("max_count", nargs="?", type=int, default=20,
                        help="采集帖子数量 (默认: 20)")
    parser.add_argument("--comments", action="store_true",
                        help="同时采集评论")
    parser.add_argument("--label",
                        help="数据标签 (默认: 从关键词生成)")
    parser.add_argument("--domain", choices=["hiking", "trail_running"],
                        help="指定领域 (用于 extract/fetch/classify)")
    parser.add_argument("--steps",
                        help=f"要执行的步骤，逗号分隔 (可选: {','.join(ALL_STEPS)})")
    parser.add_argument("--status", action="store_true",
                        help="查看当前数据状态，不执行任何操作")

    args = parser.parse_args()

    if args.status:
        state = detect_data_state(args.domain)
        print(json.dumps(state, ensure_ascii=False, indent=2))
        return

    steps = args.steps.split(",") if args.steps else ALL_STEPS[:]
    for s in steps:
        if s not in ALL_STEPS:
            print(f"未知步骤: {s}  (可选: {', '.join(ALL_STEPS)})")
            sys.exit(1)

    needs_keywords = "collect" in steps
    if needs_keywords and not args.keywords:
        parser.print_help()
        print("\n包含 collect 步骤时必须提供关键词，例如:")
        print('  python3 xhs/scripts/pipeline.py "徒步" 50')
        sys.exit(1)

    label = args.label
    if not label and args.keywords:
        import re
        first = args.keywords.split(",")[0].strip()
        label = re.sub(r'[^\w一-鿿]', '_', first).strip('_') or "collect"
    label = label or args.domain or "default"

    results = []
    start_time = datetime.now()

    for step in steps:
        if step == "collect":
            r = step_collect(args.keywords, args.max_count, args.comments, label)
        elif step == "extract":
            r = step_extract(label)
        elif step == "fetch":
            r = step_fetch(args.domain)
        elif step == "classify":
            r = step_classify(args.domain)
        else:
            continue

        results.append(r)

        if r["status"] == "interrupted":
            print("\n流水线被中断")
            break
        if r["status"] == "error" and step == "collect":
            print(f"\n采集失败，后续步骤跳过")
            break

    elapsed = (datetime.now() - start_time).total_seconds()

    report = {
        "pipeline": "xhs-data-pipeline",
        "timestamp": datetime.now().isoformat(),
        "elapsed_seconds": round(elapsed, 1),
        "steps": results,
        "data_state": detect_data_state(args.domain),
    }

    print(f"\n{'='*50}")
    print("  流水线执行报告")
    print(f"{'='*50}")
    for r in results:
        icon = "OK" if r["status"] == "ok" else "FAIL" if r["status"] == "error" else r["status"].upper()
        print(f"  [{icon:>5}] {r['step']}")
    print(f"  耗时: {elapsed:.1f}s")
    print(f"{'='*50}")

    print(f"\n--- JSON Report ---")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
