from datetime import datetime, timezone
from typing import Protocol
from pydantic import BaseModel, Field, AwareDatetime, HttpUrl


METRIC_KEYS = ("views", "likes", "comments", "shares", "saves", "author_followers", "score")


class Observation(BaseModel):
    platform: str
    platform_post_id: str
    canonical_url: HttpUrl
    author_id: str | None = None
    author_name: str | None = None
    text: str | None = None
    published_at: AwareDatetime | None = None
    observed_at: AwareDatetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    language: str | None = None
    content_type: str = "text"
    media_urls: list[str] = Field(default_factory=list)
    metrics: dict[str, int | None] = Field(default_factory=dict)
    definitions: dict[str, str] = Field(default_factory=dict)
    source: str


class Collector(Protocol):
    def discover(self, query: str, limit: int, days: int) -> list[Observation]: ...
    def observe(self, post_id: str, url: str) -> Observation: ...
