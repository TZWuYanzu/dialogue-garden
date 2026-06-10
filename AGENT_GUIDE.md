# XHS 数据采集工具集 — Agent 调用指南

> 本文档描述了小红书数据采集和清洗的全部工具接口。
> 任何能执行 shell 命令的 Agent 都可以根据本文档自主调用这些工具。

## 环境前提

- Python 3.11+
- Chrome 浏览器已登录 xiaohongshu.com（采集通过 CDP 复用 Chrome 登录态）
- 工作目录：仓库根目录（`xhs-data-project/`）

## 数据目录结构

```
xhs/data/
├── posts/                         # 采集的帖子和评论 JSON
│   ├── {label}_contents_{date}.json
│   └── {label}_comments_{date}.json
├── users_{domain}.json            # 提取的去重用户列表
└── bloggers/
    ├── {domain}_profiles.json     # 抓取的用户详细资料
    └── {domain}_checkpoint.json   # 抓取进度检查点
```

---

## 工具一览

| 工具 | 命令 | 用途 | 需要网络 |
|------|------|------|----------|
| pipeline | `python3 xhs/scripts/pipeline.py` | 一键执行完整流水线 | 是 |
| collect | `python3 xhs/scripts/collect.py` | 搜索并采集帖子数据 | 是 |
| extract_users | `python3 xhs/scripts/extract_users.py` | 从帖子提取用户列表 | 否 |
| fetch_profiles | `python3 xhs/scripts/fetch_profiles.py` | 抓取用户详细资料 | 是 |
| classify | `python3 xhs/scripts/classify_bloggers.py` | 按粉丝量/性别分类 | 否 |
| analyze | `python3 xhs/scripts/analyze.py` | 生成统计报告 | 否 |

---

## tool: pipeline（推荐入口）

一条命令执行完整的采集清洗流水线。

**命令格式：**
```bash
python3 xhs/scripts/pipeline.py <keywords> <max_count> [options]
```

**参数：**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| keywords | string | 是* | 搜索关键词，多个用逗号分隔 |
| max_count | int | 否 | 采集数量，默认 20 |
| --comments | flag | 否 | 同时采集评论 |
| --label | string | 否 | 输出文件标签，默认从关键词生成 |
| --domain | string | 否 | hiking 或 trail_running，用于 extract/fetch/classify |
| --steps | string | 否 | 指定步骤，逗号分隔：collect,extract,fetch,classify |
| --status | flag | 否 | 仅查看数据状态，不执行操作 |

*仅当 steps 包含 collect 时必填

**示例：**
```bash
# 完整流水线：采集100条徒步帖子 → 提取用户 → 抓取profile → 分类
python3 xhs/scripts/pipeline.py "徒步,登山" 100 --comments

# 只采集和提取用户
python3 xhs/scripts/pipeline.py "越野跑" 50 --steps collect,extract

# 在已有数据上只跑分类
python3 xhs/scripts/pipeline.py --steps classify --domain hiking

# 查看当前数据状态
python3 xhs/scripts/pipeline.py --status
```

**输出：** 执行完成后输出 JSON 格式的报告，包含每步状态和当前数据概况。

---

## tool: collect

搜索小红书关键词并采集帖子数据。使用 CDP 模式连接本机 Chrome。

**命令格式：**
```bash
python3 xhs/scripts/collect.py <keywords> <max_count> [options]
```

**参数：**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| keywords | string | 是 | 搜索关键词，多个用逗号分隔 |
| max_count | int | 否 | 采集数量，默认 20 |
| --comments | flag | 否 | 同时采集评论 |
| --label | string | 否 | 输出文件标签 |
| --extract-users | flag | 否 | 采集完自动提取用户列表 |
| --batch | flag | 否 | 按 YAML 配置批量采集 |
| --domain | string | 否 | 批量模式下指定领域 |

**示例：**
```bash
python3 xhs/scripts/collect.py "徒步" 50
python3 xhs/scripts/collect.py "徒步,登山,户外" 100 --comments --extract-users
```

**输出文件：** `xhs/data/posts/{label}_contents_{date}.json`

**注意：** 如果浏览器弹出滑块验证码，需要人工在浏览器窗口中手动通过。

---

## tool: extract_users

从已采集的帖子数据中提取去重用户列表，按互动量排序。

**命令格式：**
```bash
python3 xhs/scripts/extract_users.py [--domain <domain>]
```

**参数：**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| --domain | string | 否 | hiking 或 trail_running，默认处理全部 |

**输出文件：** `xhs/data/users_{domain}.json`

---

## tool: fetch_profiles

逐个访问用户主页，抓取粉丝数、性别、简介等详细信息。

**命令格式：**
```bash
python3 xhs/scripts/fetch_profiles.py --domain <domain> [options]
```

**参数：**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| --domain | string | 是 | hiking 或 trail_running |
| --test | int | 否 | 仅抓取 N 个用户（测试用） |
| --resume | flag | 否 | 从上次检查点恢复 |
| --delay | float | 否 | 请求间隔秒数，默认 6.0 |

**输出文件：** `xhs/data/bloggers/{domain}_profiles.json`

**注意：** 该步骤耗时较长，建议加 --resume 防止中断丢失进度。

---

## tool: classify

按粉丝量分层（1k-5k / 5k-10k / 10k+），统计各层级的数量和性别分布。

**命令格式：**
```bash
python3 xhs/scripts/classify_bloggers.py [--domain <domain>] [--export <file.csv>]
```

**参数：**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| --domain | string | 否 | hiking 或 trail_running，默认全部 |
| --export | string | 否 | 导出 CSV 文件路径 |

**输出：** 打印分层统计报告。如果没有 profile 数据，会基于互动量进行估算。

---

## tool: analyze

生成数据统计报告（用户数、帖子数、互动量分布等）。

**命令格式：**
```bash
python3 xhs/scripts/analyze.py [--export csv]
```

---

## 常见工作流

### 1. 新领域数据采集（端到端）
```bash
python3 xhs/scripts/pipeline.py "露营,野营,帐篷" 100 --comments
```

### 2. 补充某个领域的数据
```bash
python3 xhs/scripts/collect.py "徒步装备,徒步攻略" 50 --label hiking
python3 xhs/scripts/extract_users.py --domain hiking
```

### 3. 查看当前进度
```bash
python3 xhs/scripts/pipeline.py --status
python3 xhs/scripts/classify_bloggers.py
```

### 4. 抓取 profile 并分类（已有帖子数据时）
```bash
python3 xhs/scripts/pipeline.py --steps fetch,classify --domain hiking
```

## 错误处理

| 错误信息 | 原因 | 解决方式 |
|----------|------|----------|
| Chrome 中小红书未登录 | CDP 找不到登录态 | 在 Chrome 中打开 xiaohongshu.com 登录 |
| 登录态过期 | 会话失效 | 在 Chrome 中刷新小红书页面 |
| 滑块/验证码 | 反爬检测 | 在弹出的浏览器窗口中手动完成 |
| CAPTCHA 连续出现 | 请求过于频繁 | 等待 10-30 分钟后重试 |
