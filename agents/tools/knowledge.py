from __future__ import annotations

from datetime import datetime

from . import Tool
from ..core.storage import KnowledgeStore
from ..core.types import FormulaEntry, ReviewRecord, TopicCard


def make_read_formulas_tool(store: KnowledgeStore) -> Tool:

    def handler(params: dict) -> str:
        entries = store.load_formulas()
        if not entries:
            return "爆款公式手册为空，尚无已验证的公式。"
        lines = [f"爆款公式手册（{len(entries)} 条）\n"]
        for e in entries:
            confidence = {"high": "✅高置信", "medium": "⭕中置信", "low": "⚠️低置信"}.get(e.confidence, e.confidence)
            lines.append(
                f"- [{e.category}] {e.formula}\n"
                f"  验证 {e.verified_count} 次 | {confidence} | 最近: {e.last_verified}\n"
                f"  备注: {e.notes}" if e.notes else
                f"- [{e.category}] {e.formula}\n"
                f"  验证 {e.verified_count} 次 | {confidence} | 最近: {e.last_verified}"
            )
        return "\n".join(lines)

    return Tool(
        name="read_formulas",
        description="读取爆款公式手册，查看所有已验证的标题、封面、发布时间等公式。",
        input_schema={"type": "object", "properties": {}},
        handler=handler,
    )


def make_add_formula_tool(store: KnowledgeStore) -> Tool:

    def handler(params: dict) -> str:
        entry = FormulaEntry(
            category=params["category"],
            formula=params["formula"],
            verified_count=params.get("verified_count", 1),
            last_verified=params.get("last_verified", datetime.now().strftime("%Y-%m-%d")),
            confidence=params.get("confidence", "low"),
            notes=params.get("notes", ""),
        )
        store.add_formula(entry)
        return f"已添加公式：[{entry.category}] {entry.formula}"

    return Tool(
        name="add_formula",
        description="向爆款公式手册添加一条新公式。",
        input_schema={
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "enum": ["标题", "封面", "发布时间", "标签", "内容结构", "热点切入"],
                    "description": "公式类别",
                },
                "formula": {"type": "string", "description": "公式描述"},
                "verified_count": {"type": "integer", "description": "验证次数，默认1"},
                "confidence": {"type": "string", "enum": ["high", "medium", "low"], "description": "置信度"},
                "notes": {"type": "string", "description": "备注"},
            },
            "required": ["category", "formula"],
        },
        handler=handler,
    )


def make_read_topics_tool(store: KnowledgeStore) -> Tool:

    def handler(params: dict) -> str:
        topics = store.load_topics()
        if not topics:
            return "选题库为空。"

        status_filter = params.get("status")
        if status_filter:
            topics = [t for t in topics if t.status == status_filter]

        lines = [f"选题库（{len(topics)} 条）\n"]
        for t in topics:
            date_info = f" | 排期: {t.scheduled_date}" if t.scheduled_date else ""
            review_info = f" | 复盘: {t.review_result}" if t.review_result else ""
            lines.append(
                f"- [{t.status}] {t.name} ({t.topic_type}/{t.content_type}) "
                f"评分:{t.weighted_score}{date_info}{review_info}"
            )
        return "\n".join(lines)

    return Tool(
        name="read_topics",
        description="读取选题库，查看所有选题卡片及状态。",
        input_schema={
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["灵感", "待排期", "已排期", "已发布", "已复盘"],
                    "description": "按状态筛选",
                },
            },
        },
        handler=handler,
    )


def make_add_topic_tool(store: KnowledgeStore) -> Tool:

    def handler(params: dict) -> str:
        scores = params.get("scores", {})
        topic = TopicCard(
            name=params["name"],
            topic_type=params["topic_type"],
            content_type=params["content_type"],
            scores=scores,
            time_window=params.get("time_window", "不限"),
            status=params.get("status", "灵感"),
            created_at=datetime.now().strftime("%Y-%m-%d"),
            notes=params.get("notes", ""),
        )
        topic.compute_weighted_score()
        store.add_topic(topic)

        priority = "优先排期" if topic.weighted_score >= 4.0 else "本月备选" if topic.weighted_score >= 3.0 else "暂不排期"
        return f"已添加选题：{topic.name} | 评分: {topic.weighted_score} | 建议: {priority}"

    return Tool(
        name="add_topic",
        description="向选题库添加新选题卡片，自动计算加权评分。",
        input_schema={
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "选题名称"},
                "topic_type": {
                    "type": "string",
                    "enum": ["常青", "季节", "热点", "系列", "互动"],
                    "description": "选题类型",
                },
                "content_type": {
                    "type": "string",
                    "enum": ["干货", "情绪", "种草"],
                    "description": "内容类型",
                },
                "scores": {
                    "type": "object",
                    "description": "四维评分 {search, persona, feasibility, hit_potential}，各0-5分",
                    "properties": {
                        "search": {"type": "number"},
                        "persona": {"type": "number"},
                        "feasibility": {"type": "number"},
                        "hit_potential": {"type": "number"},
                    },
                },
                "time_window": {"type": "string", "description": "时效窗口，如'不限'、'本周'、'2026/07/01前'"},
                "notes": {"type": "string", "description": "创意简述"},
            },
            "required": ["name", "topic_type", "content_type"],
        },
        handler=handler,
    )


def make_update_topic_tool(store: KnowledgeStore) -> Tool:

    def handler(params: dict) -> str:
        name = params["name"]
        updates = {k: v for k, v in params.items() if k != "name" and v is not None}
        if store.update_topic(name, **updates):
            return f"已更新选题「{name}」：{updates}"
        return f"未找到选题「{name}」"

    return Tool(
        name="update_topic",
        description="更新选题库中已有选题的状态或信息。",
        input_schema={
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "选题名称（精确匹配）"},
                "status": {
                    "type": "string",
                    "enum": ["灵感", "待排期", "已排期", "已发布", "已复盘"],
                    "description": "新状态",
                },
                "scheduled_date": {"type": "string", "description": "排期日期 YYYY-MM-DD"},
                "review_result": {
                    "type": "string",
                    "enum": ["✅已验证爆款", "⭕表现正常", "❌表现不佳"],
                    "description": "复盘结果",
                },
            },
            "required": ["name"],
        },
        handler=handler,
    )


def make_save_review_tool(store: KnowledgeStore) -> Tool:

    def handler(params: dict) -> str:
        record = ReviewRecord(
            title=params["title"],
            publish_date=params["publish_date"],
            metrics=params.get("metrics", {}),
            traffic_sources=params.get("traffic_sources", {}),
            conclusions=params.get("conclusions", []),
            action_items=params.get("action_items", []),
            created_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
        )
        path = store.save_review(record)
        return f"复盘记录已保存：{path.name}"

    return Tool(
        name="save_review",
        description="保存一条笔记复盘记录。",
        input_schema={
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "笔记标题"},
                "publish_date": {"type": "string", "description": "发布日期 YYYY-MM-DD"},
                "metrics": {
                    "type": "object",
                    "description": "互动数据 {impressions, reads, ctr, likes, collects, comments, shares, new_followers}",
                },
                "traffic_sources": {
                    "type": "object",
                    "description": "流量结构 {recommend, search, follow, homepage, other} 百分比",
                },
                "conclusions": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "关键结论列表",
                },
                "action_items": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "行动建议列表",
                },
            },
            "required": ["title", "publish_date"],
        },
        handler=handler,
    )


def make_read_reviews_tool(store: KnowledgeStore) -> Tool:

    def handler(params: dict) -> str:
        reviews = store.load_reviews()
        if not reviews:
            return "暂无复盘记录。"
        lines = [f"复盘记录（{len(reviews)} 条）\n"]
        for r in reviews:
            m = r.metrics
            likes = m.get("likes", "?")
            collects = m.get("collects", "?")
            lines.append(f"- [{r.publish_date}] {r.title} | 赞:{likes} 藏:{collects} | 结论: {len(r.conclusions)} 条")
        return "\n".join(lines)

    return Tool(
        name="read_reviews",
        description="读取所有复盘记录摘要。",
        input_schema={"type": "object", "properties": {}},
        handler=handler,
    )
