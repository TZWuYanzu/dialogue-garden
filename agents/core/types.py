from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


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


class AgentRole(str, Enum):
    TEAM_LEADER = "team_leader"
    DATA_ANALYST = "data_analyst"
    CONTENT_EXPERT = "content_expert"
    REVIEW_EXPERT = "review_expert"
    TOPIC_SCHEDULER = "topic_scheduler"


ROLE_DISPLAY_NAMES: dict[AgentRole, str] = {
    AgentRole.TEAM_LEADER: "Team Leader",
    AgentRole.DATA_ANALYST: "数据分析专家",
    AgentRole.CONTENT_EXPERT: "内容产出专家",
    AgentRole.REVIEW_EXPERT: "复盘专家",
    AgentRole.TOPIC_SCHEDULER: "选题排期专家",
}

ROLE_PROMPT_FILES: dict[AgentRole, str] = {
    AgentRole.TEAM_LEADER: "01-team-leader.md",
    AgentRole.DATA_ANALYST: "02-data-analyst.md",
    AgentRole.CONTENT_EXPERT: "03-content-expert.md",
    AgentRole.REVIEW_EXPERT: "04-review-expert.md",
    AgentRole.TOPIC_SCHEDULER: "05-topic-scheduler.md",
}


class Message(BaseModel):
    role: str
    content: str


class Post(BaseModel):
    note_id: str
    title: str
    desc: str = ""
    liked_count: int = 0
    collected_count: int = 0
    comment_count: int = 0
    share_count: int = 0
    nickname: str = ""
    user_id: str = ""
    ip_location: str = ""
    tag_list: list[str] = Field(default_factory=list)
    source_keyword: str = ""
    note_url: str = ""
    time: int = 0

    @classmethod
    def from_raw(cls, raw: dict) -> Post:
        tags = raw.get("tag_list", "")
        if isinstance(tags, str):
            tag_list = [t.strip() for t in tags.split(",") if t.strip()]
        else:
            tag_list = list(tags)

        return cls(
            note_id=raw.get("note_id", ""),
            title=raw.get("title", ""),
            desc=raw.get("desc", ""),
            liked_count=parse_count(raw.get("liked_count")),
            collected_count=parse_count(raw.get("collected_count")),
            comment_count=parse_count(raw.get("comment_count")),
            share_count=parse_count(raw.get("share_count")),
            nickname=raw.get("nickname", ""),
            user_id=raw.get("user_id", ""),
            ip_location=raw.get("ip_location", ""),
            tag_list=tag_list,
            source_keyword=raw.get("source_keyword", ""),
            note_url=raw.get("note_url", ""),
            time=raw.get("time", 0),
        )

    @property
    def total_engagement(self) -> int:
        return self.liked_count + self.collected_count + self.comment_count + self.share_count

    @property
    def collect_like_ratio(self) -> float:
        if self.liked_count == 0:
            return 0.0
        return self.collected_count / self.liked_count


class Blogger(BaseModel):
    user_id: str
    nickname: str
    ip_location: str = ""
    post_count: int = 0
    total_likes: int = 0
    total_collects: int = 0
    total_comments: int = 0
    source_keywords: list[str] = Field(default_factory=list)


class TopicCard(BaseModel):
    name: str
    topic_type: str
    content_type: str
    scores: dict[str, float] = Field(default_factory=dict)
    weighted_score: float = 0.0
    time_window: str = "不限"
    status: str = "灵感"
    created_at: str = ""
    scheduled_date: str | None = None
    review_result: str | None = None
    notes: str = ""

    def compute_weighted_score(self) -> float:
        s = self.scores
        self.weighted_score = round(
            s.get("search", 0) * 0.25
            + s.get("persona", 0) * 0.30
            + s.get("feasibility", 0) * 0.20
            + s.get("hit_potential", 0) * 0.25,
            2,
        )
        return self.weighted_score


class ReviewRecord(BaseModel):
    title: str
    publish_date: str
    metrics: dict = Field(default_factory=dict)
    traffic_sources: dict = Field(default_factory=dict)
    conclusions: list[str] = Field(default_factory=list)
    action_items: list[str] = Field(default_factory=list)
    created_at: str = ""


class FormulaEntry(BaseModel):
    category: str
    formula: str
    verified_count: int = 0
    last_verified: str = ""
    confidence: str = "low"
    notes: str = ""
