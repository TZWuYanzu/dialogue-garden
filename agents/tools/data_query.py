from __future__ import annotations

import json
from pathlib import Path

from . import Tool
from ..core.types import Post, parse_count


def _load_all_posts(data_dir: Path, domain: str = "all") -> list[Post]:
    posts_dir = data_dir / "posts"
    results = []
    for f in sorted(posts_dir.glob("*_search_contents_*.json")):
        if domain != "all" and not f.name.startswith(domain):
            continue
        raw_list = json.loads(f.read_text(encoding="utf-8"))
        for raw in raw_list:
            results.append(Post.from_raw(raw))
    return results


def _load_bloggers(data_dir: Path, domain: str = "all") -> list[dict]:
    results = []
    if domain == "all":
        patterns = ["users_*.json"]
    else:
        patterns = [f"users_{domain}.json"]

    for pattern in patterns:
        for f in sorted(data_dir.glob(pattern)):
            raw_list = json.loads(f.read_text(encoding="utf-8"))
            results.extend(raw_list)

    seen = set()
    deduped = []
    for b in results:
        uid = b.get("user_id")
        if uid and uid not in seen:
            seen.add(uid)
            deduped.append(b)
    return deduped


def _format_post(i: int, p: Post) -> str:
    ratio = f"{p.collect_like_ratio:.2f}" if p.liked_count > 0 else "N/A"
    tags = " ".join(f"#{t}" for t in p.tag_list[:5]) if p.tag_list else ""
    return (
        f"{i}. [{p.liked_count}赞 {p.collected_count}藏 {p.comment_count}评] {p.title}\n"
        f"   博主: {p.nickname} | 地点: {p.ip_location} | 收藏/赞比: {ratio}\n"
        f"   关键词: {p.source_keyword} | {tags}"
    )


def _format_blogger(i: int, b: dict) -> str:
    keywords = ", ".join(b.get("source_keywords", []))
    return (
        f"{i}. {b.get('nickname', '?')} | "
        f"赞:{b.get('total_likes', 0)} 藏:{b.get('total_collects', 0)} 评:{b.get('total_comments', 0)} | "
        f"帖子数:{b.get('post_count', 0)} | "
        f"地点:{b.get('ip_location', '?')} | 关键词:{keywords}"
    )


def make_query_posts_tool(data_dir: Path) -> Tool:

    def handler(params: dict) -> str:
        domain = params.get("domain", "all")
        posts = _load_all_posts(data_dir, domain)

        keyword = params.get("keyword", "")
        if keyword:
            keyword_lower = keyword.lower()
            posts = [p for p in posts if keyword_lower in p.title.lower() or keyword_lower in p.desc.lower()]

        min_likes = params.get("min_likes", 0)
        if min_likes:
            posts = [p for p in posts if p.liked_count >= min_likes]

        sort_by = params.get("sort_by", "total_engagement")
        if sort_by == "total_engagement":
            posts.sort(key=lambda p: p.total_engagement, reverse=True)
        elif sort_by == "collect_like_ratio":
            posts.sort(key=lambda p: p.collect_like_ratio, reverse=True)
        else:
            posts.sort(key=lambda p: getattr(p, sort_by, 0), reverse=True)

        limit = params.get("limit", 10)
        selected = posts[:limit]

        lines = [f"查询结果：{len(selected)} 条（共 {len(posts)} 条匹配，总数据量 {len(_load_all_posts(data_dir))} 条）\n"]
        for i, p in enumerate(selected, 1):
            lines.append(_format_post(i, p))
        return "\n".join(lines)

    return Tool(
        name="query_posts",
        description="查询已采集的小红书帖子数据。可按互动量排序、按关键词搜索、按域名筛选。",
        input_schema={
            "type": "object",
            "properties": {
                "sort_by": {
                    "type": "string",
                    "enum": ["liked_count", "collected_count", "comment_count", "share_count", "total_engagement", "collect_like_ratio"],
                    "description": "排序字段，默认 total_engagement（总互动量）",
                },
                "limit": {
                    "type": "integer",
                    "description": "返回数量上限，默认 10",
                },
                "keyword": {
                    "type": "string",
                    "description": "在标题和正文中搜索的关键词",
                },
                "domain": {
                    "type": "string",
                    "enum": ["hiking", "trail_running", "all"],
                    "description": "数据域筛选，默认 all",
                },
                "min_likes": {
                    "type": "integer",
                    "description": "最低点赞数筛选",
                },
            },
        },
        handler=handler,
    )


def make_query_bloggers_tool(data_dir: Path) -> Tool:

    def handler(params: dict) -> str:
        domain = params.get("domain", "all")
        bloggers = _load_bloggers(data_dir, domain)

        keyword = params.get("keyword", "")
        if keyword:
            kw = keyword.lower()
            bloggers = [b for b in bloggers if kw in b.get("nickname", "").lower()]

        min_likes = params.get("min_likes", 0)
        if min_likes:
            bloggers = [b for b in bloggers if b.get("total_likes", 0) >= min_likes]

        sort_by = params.get("sort_by", "total_likes")
        bloggers.sort(key=lambda b: b.get(sort_by, 0), reverse=True)

        limit = params.get("limit", 10)
        selected = bloggers[:limit]

        lines = [f"查询结果：{len(selected)} 位博主（共 {len(bloggers)} 位匹配）\n"]
        for i, b in enumerate(selected, 1):
            lines.append(_format_blogger(i, b))
        return "\n".join(lines)

    return Tool(
        name="query_bloggers",
        description="查询已提取的小红书博主数据。可按互动量排序、按昵称搜索。",
        input_schema={
            "type": "object",
            "properties": {
                "sort_by": {
                    "type": "string",
                    "enum": ["total_likes", "total_collects", "total_comments", "post_count"],
                    "description": "排序字段，默认 total_likes",
                },
                "limit": {
                    "type": "integer",
                    "description": "返回数量上限，默认 10",
                },
                "keyword": {
                    "type": "string",
                    "description": "按博主昵称搜索",
                },
                "domain": {
                    "type": "string",
                    "enum": ["hiking", "trail_running", "all"],
                    "description": "数据域筛选，默认 all",
                },
                "min_likes": {
                    "type": "integer",
                    "description": "最低总点赞数筛选",
                },
            },
        },
        handler=handler,
    )
