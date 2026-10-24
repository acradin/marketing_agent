"""Read-only live diagnostics. Never publishes or prints keys/provider error bodies."""
import json
from datetime import datetime, timezone
from pathlib import Path
import httpx
from packages.core.config import Settings
from packages.collectors.adapters import Reddit, YouTube
from packages.collectors.social import X, Instagram
from packages.intelligence.llm import Intelligence


def check(name, operation):
    try:
        return {"name": name, "status": "passed", "result": operation()}
    except httpx.HTTPStatusError as exc:
        return {"name": name, "status": "failed", "http_status": exc.response.status_code}
    except Exception as exc:
        return {"name": name, "status": "failed", "error_type": type(exc).__name__}


def run():
    s = Settings()
    rows = []
    def probe(url):
        with httpx.Client(timeout=10) as client:
            r = client.get(url)
            return {"http_status": r.status_code, "meaning": "HTTP reachability only; not authenticated collection"}
    for name, url in [("local_dashboard", "http://127.0.0.1:8765/api/status"),
                      ("llm_network", s.llm_base_url.rstrip("/") + "/models"),
                      ("reddit_network", "https://oauth.reddit.com/api/info?id=t3_1"),
                      ("youtube_network", "https://www.googleapis.com/youtube/v3/videos?part=id&id=jNQXAC9IVRw")]:
        rows.append(check(name, lambda url=url: probe(url)))
    for name, configured, operation in [
        ("reddit_collection", bool(s.reddit_token), lambda: {"posts": len(Reddit(s).discover("python", 1, 365))}),
        ("youtube_collection", bool(s.youtube_api_key), lambda: {"posts": len(YouTube(s).discover("python", 1, 365))}),
        ("x_collection", bool(s.x_bearer_token), lambda: {"posts": len(X(s).discover("python", 1, 1))}),
        ("instagram_collection", bool(s.instagram_token and s.instagram_user_id), lambda: {"posts": len(Instagram(s).discover("*", 1, 365))}),
        ("llm_schema_analysis", s.llm_configured, lambda: {"schema_valid": bool(Intelligence(s).analyze("A local tool stores notes. Try organizing one note today."))}),
    ]:
        rows.append(check(name, operation) if configured else {"name": name, "status": "skipped", "reason": "configuration_missing"})
    report = {"checked_at": datetime.now(timezone.utc).isoformat(), "checks": rows,
              "publication_attempted": False, "database_modified": False,
              "note": "Zero returned posts is not proof of successful post ingestion. LLM probe uses synthetic text; generation is not tested."}
    Path("docs").mkdir(exist_ok=True)
    Path("docs/live-connections.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    run()
