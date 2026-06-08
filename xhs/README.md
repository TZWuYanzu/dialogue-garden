# XHS Data Collector

Xiaohongshu blogger and post data collection, powered by [MediaCrawler](https://github.com/NanmiCoder/MediaCrawler).

## Quick Start

```bash
# 1. Setup (clone MediaCrawler + install dependencies)
chmod +x xhs/setup.sh && ./xhs/setup.sh

# 2. Open Chrome with remote debugging
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9222

# 3. Log in to xiaohongshu.com in that Chrome window

# 4. Test with a single keyword
python3 xhs/scripts/collect.py --keyword 徒步 --max 5

# 5. Run full collection
python3 xhs/scripts/collect.py

# 6. Analyze results
python3 xhs/scripts/analyze.py
```

## Project Structure

```
xhs/
├── config/search_tasks.yaml   # Search keywords, fan tiers, targets
├── scripts/
│   ├── collect.py             # Batch collection script
│   └── analyze.py             # Data analysis & reporting
├── data/
│   ├── bloggers/              # Blogger profiles (JSON)
│   └── posts/                 # Post data (JSON)
└── MediaCrawler/              # (git-ignored) cloned automatically by setup.sh
```

## Collection Targets

| Domain | Tier | Target | Min Male |
|--------|------|--------|----------|
| Hiking | 1k-5k fans | 20 | 8 (40%) |
| Hiking | 5k-10k fans | 20 | 8 (40%) |
| Hiking | 10k+ fans | 20 | 8 (40%) |
| Trail Running | 1k-5k fans | 20 | 8 (40%) |
| Trail Running | 5k-10k fans | 20 | 8 (40%) |
| Trail Running | 10k+ fans | 20 | 8 (40%) |
| **Total** | | **120** | **48** |

## Data Access (Other Devices)

```bash
git clone https://github.com/TZWuYanzu/dialogue-garden.git
cd dialogue-garden
python3 xhs/scripts/analyze.py
```
