from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from .models import Post, Snapshot, Job, Event, Analysis, Pattern, Draft, now
from packages.collectors.base import METRIC_KEYS, Observation
from packages.collectors.adapters import collectors
from packages.analytics.ranking import rank
from packages.intelligence.llm import Intelligence
from packages.publishing.base import approval_hash, RedditPublisher


def enqueue(session, kind, payload, dedupe_key, run_at=None):
    existing = session.scalar(select(Job).where(Job.dedupe_key == dedupe_key))
    if existing:
        return existing
    job = Job(kind=kind, payload=payload, dedupe_key=dedupe_key, run_at=run_at or now())
    session.add(job)
    session.flush()
    return job


def persist(session, observation: Observation):
    d = observation.model_dump(mode="json")
    d["observed_at"] = observation.observed_at.astimezone(timezone.utc).isoformat()
    if observation.published_at:
        d["published_at"] = observation.published_at.astimezone(timezone.utc).isoformat()
    post = session.scalar(select(Post).where(Post.platform == d["platform"], Post.platform_post_id == d["platform_post_id"]))
    if post is None:
        post = Post(**{k: d[k] for k in ("platform", "platform_post_id", "canonical_url", "author_id", "author_name", "text", "published_at", "language", "content_type", "media_urls")})
        session.add(post)
        session.flush()
    else:
        for key in ("author_id", "author_name", "text", "published_at", "language"):
            if d[key] is not None:
                setattr(post, key, d[key])
    snapshot = session.scalar(select(Snapshot).where(Snapshot.post_id == post.id, Snapshot.observed_at == d["observed_at"], Snapshot.source == d["source"]))
    if snapshot is None:
        metrics = {k: d["metrics"].get(k) for k in METRIC_KEYS}
        if any(v is not None and v < 0 for k, v in metrics.items() if k != "score"):
            raise ValueError("Negative counter from collector")
        snapshot = Snapshot(post_id=post.id, observed_at=d["observed_at"], source=d["source"], metrics=metrics, definitions=d["definitions"])
        session.add(snapshot)
    return post


class Service:
    def __init__(self, settings, sessions):
        self.settings, self.sessions = settings, sessions
        self.collectors = collectors(settings)
        self.intelligence = Intelligence(settings)
        self.publisher = RedditPublisher(settings)
        from packages.publishing.social import XPublisher, InstagramPublisher
        self.publishers = {"reddit": self.publisher, "x": XPublisher(settings), "instagram": InstagramPublisher(settings)}

    def followups(self, session, post, backend):
        # Targets are relative to first collection, not fabricated publication-age snapshots.
        for hours in (1, 6, 24, 72):
            at = (datetime.fromisoformat(post.collected_at) + timedelta(hours=hours)).isoformat()
            enqueue(session, "observe", {"post_id": post.id, "backend": backend}, f"observe:{post.id}:{hours}", at)

    def execute(self, kind, payload, job_id=None):
        with self.sessions.begin() as session:
            if job_id:
                prior = session.scalar(select(Event).where(Event.job_id == job_id, Event.action == "job_effects_committed"))
                if prior:
                    return prior.detail
            def completed(result):
                if job_id:
                    session.add(Event(job_id=job_id, action="job_effects_committed", detail=result))
                return result
            if kind in ("discover", "collect_url"):
                backend = payload.get("platform", "public_video") if kind == "discover" else "public_video"
                collector = self.collectors[backend]
                observations = collector.discover(payload["query"], payload.get("limit", 25), payload.get("days", 7)) if kind == "discover" else [collector.observe("", payload["url"])]
                ids = []
                for observation in observations:
                    post = persist(session, observation)
                    self.followups(session, post, backend)
                    ids.append(post.id)
                return completed({"post_ids": ids, "count": len(ids)})
            if kind == "observe":
                post = session.get(Post, payload["post_id"])
                observation = self.collectors[payload["backend"]].observe(post.platform_post_id, post.canonical_url)
                if observation.platform != post.platform or observation.platform_post_id != post.platform_post_id:
                    raise ValueError("Collector returned a different post")
                persist(session, observation)
                return completed({"post_id": post.id})
            if kind == "analyze":
                post = session.get(Post, payload["post_id"])
                if post is None or not post.text:
                    raise ValueError("Post text required")
                result = self.intelligence.analyze(post.text)
                analysis = Analysis(post_id=post.id, model=self.settings.llm_model, result={**result.model_dump(), "interpretation": "hypotheses_only", "content_length": len(post.text)})
                session.add(analysis)
                session.flush()
                pattern = Pattern(analysis_id=analysis.id, platform=post.platform, content_type=post.content_type, language=post.language, name=result.hook_type, structure=result.narrative, example_post_ids=[post.id])
                session.add(pattern)
                session.flush()
                return completed({"analysis_id": analysis.id, "pattern_id": pattern.id})
            if kind == "generate":
                pattern = session.get(Pattern, payload["pattern_id"])
                if pattern is None:
                    raise ValueError("Pattern not found")
                sources = [session.get(Post, i).text for i in pattern.example_post_ids]
                result = self.intelligence.generate({**payload["brief"], "platform": payload["platform"], "format_hint": "X: maximum 280 weighted characters (Korean counts twice); Instagram: caption at most 2200 characters; other: platform-appropriate draft"}, pattern.structure, sources)
                draft = Draft(pattern_id=pattern.id, platform=payload["platform"], brief=payload["brief"], title=result.title, text=result.text, destination=payload.get("destination", ""))
                session.add(draft)
                session.flush()
                return completed({"draft_id": draft.id})
            raise ValueError("Unknown job kind")

    def publish(self, draft_id):
        # Commit intent before network IO. A crash or ambiguous response is NEVER retried automatically.
        with self.sessions.begin() as session:
            from .database import lock_write
            lock_write(session)
            draft = session.get(Draft, draft_id)
            if draft is None:
                raise ValueError("Draft not found")
            if draft.state == "published":
                return {"url": draft.remote_url, "already_published": True}
            if draft.state != "approved" or draft.approved_hash != approval_hash(draft):
                raise ValueError("Current content and destination require approval")
            from packages.publishing.social import validate_publication
            validate_publication(self.settings, draft)
            from sqlalchemy import update
            claimed = session.execute(update(Draft).where(Draft.id == draft_id, Draft.state == "approved").values(state="publishing"))
            if claimed.rowcount != 1:
                raise ValueError("Publication already claimed")
            session.add(Event(job_id=None, action="publication_intent", detail={"draft_id": draft_id, "hash": draft.approved_hash}))
        try:
            remote_id, url = self.publishers[draft.platform].publish(draft)
        except Exception:
            with self.sessions.begin() as session:
                session.get(Draft, draft_id).state = "publication_unknown"
                session.add(Event(job_id=None, action="publication_unknown", detail={"draft_id": draft_id, "action_required": "Check remote account before any retry"}))
            raise RuntimeError("Publication outcome uncertain; check remote account. Automatic retry disabled.") from None
        with self.sessions.begin() as session:
            draft = session.get(Draft, draft_id)
            # Published timestamps are observed receipt times, not invented platform timestamps.
            post = persist(session, Observation(platform=draft.platform, platform_post_id=remote_id, canonical_url=url, text=draft.title + "\n" + draft.text if draft.platform == "reddit" else draft.text, content_type="image" if draft.platform == "instagram" else "text", source="publication_receipt", definitions={}))
            draft.state, draft.remote_url, draft.published_post_id = "published", url, post.id
            enqueue(session, "observe", {"post_id": post.id, "backend": draft.platform}, "published-observe:" + post.id)
            self.followups(session, post, draft.platform)
            session.add(Event(job_id=None, action="published", detail={"draft_id": draft_id, "url": url}))
        return {"url": url}

    def ranking(self, session):
        posts = session.scalars(select(Post)).all()
        snapshots = session.scalars(select(Snapshot).order_by(Snapshot.observed_at)).all()
        by_post = {}
        for snapshot in snapshots:
            by_post.setdefault(snapshot.post_id, []).append(snapshot)
        cohort = [(p, by_post[p.id][-1]) for p in posts if p.id in by_post]
        results = {p.id: rank(p, by_post.get(p.id, []), cohort) for p in posts}
        from packages.analytics.ranking import age_bucket, signature, follower_bucket, percentile
        for p, latest in cohort:
            comparable = [q for q, other in cohort if q.id != p.id and q.platform == p.platform and q.content_type == p.content_type and q.paid_promotion == p.paid_promotion and latest.source == other.source and signature(latest) == signature(other) and age_bucket(p, latest) is not None and age_bucket(p, latest) == age_bucket(q, other) and follower_bucket(latest) == follower_bucket(other)]
            for value_key, rank_key in (("relative_performance", "relative_performance_percentile"), ("growth_per_hour", "growth_percentile")):
                value = results[p.id][value_key]
                values = [results[q.id][value_key] for q in comparable if results[q.id][value_key] is not None]
                results[p.id][rank_key + "_sample_size"] = len(values)
                if value is not None and len(values) >= 5:
                    results[p.id][rank_key] = percentile(value, values)
        return results
