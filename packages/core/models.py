from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import JSON, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def uid() -> str:
    return uuid4().hex


class Base(DeclarativeBase):
    pass


class Post(Base):
    __tablename__ = "posts"
    __table_args__ = (UniqueConstraint("platform", "platform_post_id"),)
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    platform: Mapped[str]
    platform_post_id: Mapped[str]
    canonical_url: Mapped[str] = mapped_column(unique=True)
    author_id: Mapped[str | None]
    author_name: Mapped[str | None]
    text: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[str | None]
    collected_at: Mapped[str] = mapped_column(default=now)
    language: Mapped[str | None]
    content_type: Mapped[str] = mapped_column(default="text")
    media_urls: Mapped[list] = mapped_column(JSON, default=list)
    paid_promotion: Mapped[bool | None]


class Snapshot(Base):
    __tablename__ = "snapshots"
    __table_args__ = (UniqueConstraint("post_id", "observed_at", "source"),)
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    post_id: Mapped[str] = mapped_column(ForeignKey("posts.id"))
    observed_at: Mapped[str]
    source: Mapped[str]
    metrics: Mapped[dict] = mapped_column(JSON)
    definitions: Mapped[dict] = mapped_column(JSON)


class Job(Base):
    __tablename__ = "jobs"
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    dedupe_key: Mapped[str] = mapped_column(unique=True)
    kind: Mapped[str]
    payload: Mapped[dict] = mapped_column(JSON)
    state: Mapped[str] = mapped_column(default="queued")
    attempts: Mapped[int] = mapped_column(default=0)
    run_at: Mapped[str] = mapped_column(default=now)
    lease_until: Mapped[str | None]
    error: Mapped[str | None]
    result: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[str] = mapped_column(default=now)


class Schedule(Base):
    __tablename__ = "schedules"
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    payload: Mapped[dict] = mapped_column(JSON)
    interval_minutes: Mapped[int]
    enabled: Mapped[bool] = mapped_column(default=True)
    next_run_at: Mapped[str] = mapped_column(default=now)


class Event(Base):
    __tablename__ = "events"
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    job_id: Mapped[str | None]
    action: Mapped[str]
    detail: Mapped[dict] = mapped_column(JSON)
    at: Mapped[str] = mapped_column(default=now)


class Analysis(Base):
    __tablename__ = "analyses"
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    post_id: Mapped[str] = mapped_column(ForeignKey("posts.id"))
    model: Mapped[str]
    result: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[str] = mapped_column(default=now)


class Pattern(Base):
    __tablename__ = "patterns"
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    analysis_id: Mapped[str] = mapped_column(ForeignKey("analyses.id"))
    platform: Mapped[str]
    content_type: Mapped[str]
    language: Mapped[str | None]
    name: Mapped[str]
    structure: Mapped[list] = mapped_column(JSON)
    example_post_ids: Mapped[list] = mapped_column(JSON)


class Draft(Base):
    __tablename__ = "drafts"
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    pattern_id: Mapped[str] = mapped_column(ForeignKey("patterns.id"))
    platform: Mapped[str]
    brief: Mapped[dict] = mapped_column(JSON)
    text: Mapped[str] = mapped_column(Text)
    title: Mapped[str]
    version: Mapped[int] = mapped_column(default=1)
    state: Mapped[str] = mapped_column(default="review")
    approved_hash: Mapped[str | None]
    approved_at: Mapped[str | None]
    destination: Mapped[str]
    remote_url: Mapped[str | None]
    published_post_id: Mapped[str | None] = mapped_column(ForeignKey("posts.id"))
    created_at: Mapped[str] = mapped_column(default=now)
