"""
XHS data collector — wraps MediaCrawler to run batch search tasks.

Usage:
    python3 xhs/scripts/collect.py                    # run all tasks
    python3 xhs/scripts/collect.py --domain hiking    # only hiking
    python3 xhs/scripts/collect.py --keyword 徒步 --max 10  # single keyword test
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
MC_DIR = ROOT / "MediaCrawler"
CONFIG_FILE = ROOT / "config" / "search_tasks.yaml"
DATA_DIR = ROOT / "data"


def load_config() -> dict:
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def run_mediacrawler(keyword: str, max_notes: int, sort_type: str, output_dir: Path):
    """Run MediaCrawler for a single keyword search."""
    main_py = MC_DIR / "main.py"
    if not main_py.exists():
        print(f"Error: MediaCrawler not found at {MC_DIR}")
        print("Run setup.sh first.")
        sys.exit(1)

    venv_python = MC_DIR / ".venv" / "bin" / "python3"
    python_cmd = str(venv_python) if venv_python.exists() else "python3"

    cmd = [
        python_cmd, str(main_py),
        "--platform", "xhs",
        "--type", "search",
        "--lt", "qrcode",
        "--keywords", keyword,
        "--crawler_max_notes_count", str(max_notes),
        "--save_data_option", "json",
        "--save_data_path", str(output_dir),
    ]

    print(f"\n{'='*60}")
    print(f"Collecting: keyword='{keyword}', max={max_notes}")
    print(f"{'='*60}")

    env = os.environ.copy()
    env["PYTHONPATH"] = str(MC_DIR)

    try:
        uv_path = shutil.which("uv")
        if uv_path and (MC_DIR / "uv.lock").exists():
            cmd = [uv_path, "run", "--project", str(MC_DIR), str(main_py),
                   "--platform", "xhs",
                   "--type", "search",
                   "--lt", "qrcode",
                   "--keywords", keyword,
                   "--crawler_max_notes_count", str(max_notes),
                   "--save_data_option", "json",
                   "--save_data_path", str(output_dir)]

        subprocess.run(cmd, cwd=str(MC_DIR), env=env, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Warning: MediaCrawler exited with code {e.returncode}")
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
        sys.exit(0)


def collect_creator(creator_id: str, output_dir: Path):
    """Crawl a specific creator's profile and notes."""
    main_py = MC_DIR / "main.py"
    python_cmd = str(MC_DIR / ".venv" / "bin" / "python3")
    if not Path(python_cmd).exists():
        python_cmd = "python3"

    cmd = [
        python_cmd, str(main_py),
        "--platform", "xhs",
        "--type", "creator",
        "--lt", "qrcode",
        "--creator_id", creator_id,
        "--save_data_option", "json",
        "--save_data_path", str(output_dir),
    ]

    subprocess.run(cmd, cwd=str(MC_DIR), check=True)


def organize_results(raw_dir: Path, domain: str, tier_label: str):
    """Move and organize raw MediaCrawler output into our data structure."""
    bloggers_dir = DATA_DIR / "bloggers"
    posts_dir = DATA_DIR / "posts"
    bloggers_dir.mkdir(parents=True, exist_ok=True)
    posts_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    for json_file in raw_dir.glob("**/*.json"):
        content = json_file.read_text(encoding="utf-8")
        if not content.strip():
            continue

        dest_name = f"{domain}_{tier_label}_{json_file.stem}_{timestamp}.json"

        if "creator" in json_file.stem.lower() or "user" in json_file.stem.lower():
            shutil.copy2(json_file, bloggers_dir / dest_name)
        else:
            shutil.copy2(json_file, posts_dir / dest_name)

    print(f"Results organized into {DATA_DIR}")


def main():
    parser = argparse.ArgumentParser(description="XHS batch data collector")
    parser.add_argument("--domain", choices=["hiking", "trail_running"],
                        help="Only collect for this domain")
    parser.add_argument("--keyword", help="Run a single keyword (for testing)")
    parser.add_argument("--max", type=int, default=None,
                        help="Override max notes per keyword")
    args = parser.parse_args()

    config = load_config()
    settings = config["settings"]
    max_notes = args.max or settings["max_notes_per_keyword"]

    if args.keyword:
        raw_dir = ROOT / "cache" / "raw_output"
        raw_dir.mkdir(parents=True, exist_ok=True)
        run_mediacrawler(args.keyword, max_notes, settings["sort_type"], raw_dir)
        print(f"\nTest results saved to: {raw_dir}")
        return

    for domain in config["domains"]:
        if args.domain and domain["name"] != args.domain:
            continue

        print(f"\n{'#'*60}")
        print(f"# Domain: {domain['label']} ({domain['name']})")
        print(f"{'#'*60}")

        for tier in domain["tiers"]:
            print(f"\n--- Tier: {tier['label']} (fans {tier['min_followers']}-{tier['max_followers']}) ---")

            raw_dir = ROOT / "cache" / "raw_output" / f"{domain['name']}_{tier['label']}"
            raw_dir.mkdir(parents=True, exist_ok=True)

            for keyword in domain["keywords"]:
                run_mediacrawler(keyword, max_notes, settings["sort_type"], raw_dir)

            organize_results(raw_dir, domain["name"], tier["label"])

    print(f"\n{'='*60}")
    print("Collection complete!")
    print(f"Blogger data: {DATA_DIR / 'bloggers'}")
    print(f"Post data:    {DATA_DIR / 'posts'}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
