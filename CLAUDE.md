# XHS Data Project

## 项目概述

小红书数据采集和博主筛选项目。通过关键词搜索采集帖子数据，提取用户列表，抓取用户 profile，按粉丝量分层分类。

## 工具调用

所有采集和清洗工具在 `xhs/scripts/` 下，详细接口见 `AGENT_GUIDE.md`。

**推荐入口 — 一条命令跑完整流水线：**
```bash
python3 xhs/scripts/pipeline.py "关键词" 数量 --comments
```

**单步调用：**
```bash
python3 xhs/scripts/collect.py "关键词" 数量    # 采集帖子
python3 xhs/scripts/extract_users.py             # 提取用户
python3 xhs/scripts/fetch_profiles.py --domain X  # 抓取 profile
python3 xhs/scripts/classify_bloggers.py          # 分类统计
python3 xhs/scripts/pipeline.py --status          # 查看数据状态
```

## 运行前提

- Chrome 浏览器中已登录 xiaohongshu.com（采集通过 CDP 复用登录态）
- 如遇滑块验证码，在弹出的浏览器窗口中手动完成

## 数据目录

- `xhs/data/posts/` — 帖子和评论 JSON
- `xhs/data/users_*.json` — 去重用户列表
- `xhs/data/bloggers/` — 用户 profile 和分类结果

## 代码约定

- 脚本都在 `xhs/scripts/` 下，互相独立，可单独运行
- MediaCrawler 是 git 子模块/外部依赖，在 `xhs/MediaCrawler/`，已被 .gitignore 排除
- 环境变量配置在 `xhs/.env`（已被 .gitignore 排除）
