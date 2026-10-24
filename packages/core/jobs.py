from datetime import datetime, timedelta, timezone
from sqlalchemy import select, update
from .models import Job, Event, Schedule, now


class Worker:
    def __init__(self, sessions, service):
        self.sessions, self.service = sessions, service

    def tick(self):
        timestamp = now()
        with self.sessions.begin() as session:
            from .service import enqueue
            for schedule in session.scalars(select(Schedule).where(Schedule.enabled == True, Schedule.next_run_at <= timestamp)).all():
                enqueue(session, "discover", schedule.payload, f"schedule:{schedule.id}:{schedule.next_run_at}")
                schedule.next_run_at = (datetime.now(timezone.utc) + timedelta(minutes=schedule.interval_minutes)).isoformat()
            expired = session.scalars(select(Job).where(Job.state == "running", Job.lease_until < timestamp)).all()
            for job in expired:
                job.state = "failed" if job.attempts >= 3 else "queued"
                job.error = "Worker lease expired"
                session.add(Event(job_id=job.id, action="lease_expired", detail={"attempt": job.attempts}))
            job = session.scalar(select(Job).where(Job.state == "queued", Job.run_at <= timestamp).order_by(Job.run_at).limit(1))
            if job is None:
                return
            lease = (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()
            changed = session.execute(update(Job).where(Job.id == job.id, Job.state == "queued").values(state="running", attempts=Job.attempts + 1, lease_until=lease))
            if changed.rowcount != 1:
                return
            job_id, kind, payload = job.id, job.kind, job.payload
            session.add(Event(job_id=job_id, action="started", detail={"kind": kind}))
        try:
            result = self.service.execute(kind, payload, job_id)
            error = None
        except Exception as exc:
            # Exception text can contain API keys in request URLs. Persist only class, never raw URL.
            result, error = None, type(exc).__name__
            from packages.collectors.adapters import CollectorUnavailable
            if isinstance(exc, CollectorUnavailable):
                error += ": " + str(exc)
        with self.sessions.begin() as session:
            job = session.get(Job, job_id)
            if job.state != "running" or job.lease_until != lease:
                return
            job.result, job.error, job.lease_until = result, error, None
            job.state = "succeeded" if error is None else ("failed" if job.attempts >= 3 else "queued")
            if error:
                job.run_at = (datetime.now(timezone.utc) + timedelta(seconds=30 * 2 ** job.attempts)).isoformat()
            session.add(Event(job_id=job_id, action=job.state, detail={"error": error, "attempt": job.attempts}))
