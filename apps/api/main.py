from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from apscheduler.schedulers.background import BackgroundScheduler
from packages.core.config import Settings
from packages.core.database import database, lock_write
from packages.core.models import Base, Post, Snapshot, Job, Event, Analysis, Pattern, Draft, Schedule, now
from packages.core.service import Service, enqueue
from packages.core.jobs import Worker
from packages.publishing.base import approval_hash


class DiscoveryRequest(BaseModel):
    platform: str = Field(pattern="^(reddit|youtube|x|instagram)$")
    query: str = Field(min_length=1, max_length=500)
    limit: int = Field(default=25, ge=1, le=50)
    days: int = Field(default=7, ge=1, le=365)


class URLRequest(BaseModel):
    url: str = Field(min_length=10, max_length=2000)


class ScheduleRequest(DiscoveryRequest):
    interval_minutes: int = Field(default=360, ge=60, le=10080)


class GenerateRequest(BaseModel):
    pattern_id: str
    platform: str = Field(pattern="^(reddit|youtube|tiktok|x|instagram|manual)$")
    product: str = Field(min_length=1, max_length=3000)
    audience: str = Field(min_length=1, max_length=1000)
    facts: str = Field(min_length=1, max_length=4000)
    language: str = "ko"
    image_url: str = Field(default="", max_length=2000)
    destination: str = Field(default="", max_length=100)


class EditRequest(BaseModel):
    image_url: str = Field(default="", max_length=2000)
    title: str = Field(min_length=1, max_length=300)
    text: str = Field(min_length=1, max_length=20000)
    destination: str = Field(max_length=100)
    version: int


class ApprovalRequest(BaseModel):
    version: int


def serialize(row):
    return {column.name: getattr(row, column.name) for column in row.__table__.columns}


def create_app(settings=None, scheduling=True):
    settings = settings or Settings()
    engine, sessions = database(settings.database_url)
    service = Service(settings, sessions)
    worker = Worker(sessions, service)
    scheduler = BackgroundScheduler()

    @asynccontextmanager
    async def lifespan(app):
        Base.metadata.create_all(engine)
        if scheduling:
            scheduler.add_job(worker.tick, "interval", seconds=3, max_instances=1, coalesce=True)
            scheduler.start()
        yield
        if scheduling:
            scheduler.shutdown(wait=True)
        engine.dispose()

    app = FastAPI(title="Viral Engine", version="0.1.0", lifespan=lifespan)
    app.state.service, app.state.worker, app.state.sessions = service, worker, sessions

    @app.middleware("http")
    async def local_only(request: Request, call_next):
        # Reject DNS rebinding and cross-origin browser writes; server binds loopback by default.
        host = request.url.hostname
        if host not in ("localhost", "127.0.0.1", "testserver", "::1"):
            return JSONResponse({"detail": "Local access only"}, status_code=403)
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            origin = request.headers.get("origin")
            if origin and origin != str(request.base_url).rstrip("/"):
                return JSONResponse({"detail": "Cross-origin writes denied"}, status_code=403)
            if request.headers.get("x-viral-local") != "1":
                return JSONResponse({"detail": "X-Viral-Local: 1 header required"}, status_code=403)
        return await call_next(request)

    @app.get("/")
    def home():
        return FileResponse(Path(__file__).parents[1] / "web" / "index.html")

    @app.get("/api/status")
    def status():
        with sessions() as session:
            jobs = session.scalars(select(Job)).all()
            successes = session.scalars(select(Event).where(Event.action == "succeeded")).all()
            def health(platform):
                subset = [j for j in jobs if j.payload.get("platform") == platform or j.payload.get("backend") == platform]
                ended = [j for j in subset if j.state in ("succeeded", "failed")]
                good = [j for j in ended if j.state == "succeeded"]
                good_ids = {j.id for j in good}
                return {"success_rate": len(good) / len(ended) if ended else None, "last_success": max((e.at for e in successes if e.job_id in good_ids), default=None), "last_failure": next((j.error for j in reversed(subset) if j.error), None)}
            return {"llm_configured": settings.llm_configured, "publishing_enabled": settings.enable_publishing, "adapters": [
                {"platform": "reddit", "configured": bool(settings.reddit_token), "search": ["keyword"], "metrics": ["score", "comments"], "auth": "OAuth token", "constraints": "API access and subreddit permissions required; rate limits enforced by provider", **health("reddit")},
                {"platform": "youtube", "configured": bool(settings.youtube_api_key), "search": ["keyword"], "metrics": ["views", "likes", "comments"], "auth": "API key", "constraints": "Provider quota applies; video search does not guarantee Shorts", **health("youtube")},
                {"platform": "x", "configured": bool(settings.x_bearer_token), "search": ["keyword: last 7 days"], "metrics": ["likes", "comments", "shares", "views"], "auth": "Bearer read; OAuth 1.0a write", "constraints": "X API access/quota required; text publishing via Tweepy", **health("x")},
                {"platform": "instagram", "configured": bool(settings.instagram_token and settings.instagram_user_id), "search": ["own account caption filter"], "metrics": ["likes", "comments"], "auth": "Facebook Login token + professional account", "constraints": "Own latest 50 posts only; query * lists all; single JPEG publishing", **health("instagram")},
                {"platform": "public_video", "configured": settings.allow_public_urls, "search": ["explicit TikTok/YouTube URL"], "metrics": ["views", "likes", "comments", "shares", "author_followers"], "auth": "none; public permitted URLs only", "constraints": "Best effort; unavailable fields remain null; no access bypass", **health("public_video")}]}

    @app.get("/api/posts")
    def posts():
        with sessions() as session:
            ranking = service.ranking(session)
            result = []
            for post in session.scalars(select(Post).order_by(Post.collected_at.desc())).all():
                snapshots = session.scalars(select(Snapshot).where(Snapshot.post_id == post.id).order_by(Snapshot.observed_at)).all()
                result.append({**serialize(post), "snapshots": [serialize(s) for s in snapshots], "ranking": ranking[post.id]})
            return result

    @app.get("/api/{resource}")
    def resources(resource: str):
        model = {"jobs": Job, "events": Event, "patterns": Pattern, "analyses": Analysis, "drafts": Draft, "schedules": Schedule}.get(resource)
        if model is None:
            raise HTTPException(404)
        with sessions() as session:
            return [serialize(x) for x in session.scalars(select(model)).all()]

    def submit(kind, payload, key=None):
        with sessions.begin() as session:
            job = enqueue(session, kind, payload, key or f"{kind}:{uuid4().hex}")
            return {"job_id": job.id, "state": job.state}

    @app.post("/api/discover")
    def discover(body: DiscoveryRequest):
        return submit("discover", body.model_dump())

    @app.post("/api/collect-url")
    def collect_url(body: URLRequest):
        return submit("collect_url", body.model_dump())

    @app.post("/api/schedules")
    def schedule(body: ScheduleRequest):
        data = body.model_dump()
        interval = data.pop("interval_minutes")
        with sessions.begin() as session:
            row = Schedule(payload=data, interval_minutes=interval)
            session.add(row)
            session.flush()
            return serialize(row)

    @app.delete("/api/schedules/{schedule_id}")
    def stop_schedule(schedule_id: str):
        with sessions.begin() as session:
            row = session.get(Schedule, schedule_id)
            if row is None:
                raise HTTPException(404)
            row.enabled = False
            return {"enabled": False}

    @app.post("/api/posts/{post_id}/observe")
    def observe(post_id: str):
        with sessions() as session:
            post = session.get(Post, post_id)
            if post is None:
                raise HTTPException(404)
            last = session.scalar(select(Snapshot).where(Snapshot.post_id == post_id).order_by(Snapshot.observed_at.desc()))
            backend = "public_video" if last and last.source == "yt_dlp_public_metadata" else post.platform
        return submit("observe", {"post_id": post_id, "backend": backend})

    @app.post("/api/posts/{post_id}/analyze")
    def analyze(post_id: str):
        with sessions() as session:
            if session.get(Post, post_id) is None:
                raise HTTPException(404)
        return submit("analyze", {"post_id": post_id})

    @app.post("/api/generate")
    def generate(body: GenerateRequest):
        data = body.model_dump()
        return submit("generate", {"pattern_id": data.pop("pattern_id"), "platform": data.pop("platform"), "destination": data.pop("destination"), "brief": data})

    @app.put("/api/drafts/{draft_id}")
    def edit(draft_id: str, body: EditRequest):
        with sessions.begin() as session:
            lock_write(session)
            draft = session.get(Draft, draft_id)
            if draft is None:
                raise HTTPException(404)
            if draft.version != body.version or draft.state in ("publishing", "published", "publication_unknown"):
                raise HTTPException(409, "Version conflict or publication already started")
            draft.title, draft.text, draft.destination = body.title, body.text, body.destination
            draft.brief = {**draft.brief, "image_url": body.image_url}
            draft.version += 1
            draft.state, draft.approved_hash, draft.approved_at = "review", None, None
            session.add(Event(action="draft_edited", detail={"draft_id": draft_id, "version": draft.version}))
            return serialize(draft)

    @app.get("/api/drafts/{draft_id}/export")
    def export_draft(draft_id: str):
        with sessions() as session:
            draft = session.get(Draft, draft_id)
            if draft is None:
                raise HTTPException(404)
            return JSONResponse({"platform": draft.platform, "title": draft.title, "text": draft.text,
                                 "destination": draft.destination, "image_url": draft.brief.get("image_url", ""),
                                 "state": draft.state, "version": draft.version, "published": False},
                                headers={"Content-Disposition": f'attachment; filename="draft-{draft.id}.json"'})

    @app.post("/api/drafts/{draft_id}/approve")
    def approve(draft_id: str, body: ApprovalRequest):
        with sessions.begin() as session:
            lock_write(session)
            draft = session.get(Draft, draft_id)
            if draft is None:
                raise HTTPException(404)
            if draft.version != body.version or draft.state not in ("review", "approved"):
                raise HTTPException(409, "Draft changed or already published")
            draft.state, draft.approved_hash, draft.approved_at = "approved", approval_hash(draft), now()
            session.add(Event(action="approved", detail={"draft_id": draft_id, "version": draft.version, "hash": draft.approved_hash}))
            return serialize(draft)

    @app.post("/api/drafts/{draft_id}/publish")
    def publish(draft_id: str):
        try:
            return service.publish(draft_id)
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from None
        except RuntimeError as exc:
            raise HTTPException(502, str(exc)) from None

    @app.get("/api/feedback/results")
    def feedback():
        with sessions() as session:
            scores = service.ranking(session)
            return [{"draft_id": d.id, "pattern_id": d.pattern_id, "post_id": d.published_post_id, "url": d.remote_url, "ranking": scores.get(d.published_post_id), "interpretation": "observational_experiment_not_causal", "state": d.state} for d in session.scalars(select(Draft)).all() if d.published_post_id]

    @app.get("/api/feedback/learning")
    def learning():
        from packages.feedback.learning import recommendations
        with sessions() as session:
            return recommendations(session, service.ranking(session))

    return app


app = create_app()
