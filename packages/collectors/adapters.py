from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse
import httpx
from .base import Observation


class CollectorUnavailable(RuntimeError):
    pass


def utc(epoch):
    return datetime.fromtimestamp(epoch, timezone.utc) if epoch is not None else None


class Reddit:
    def __init__(self, settings):
        self.settings = settings

    def get(self, path, params):
        if not self.settings.reddit_token:
            raise CollectorUnavailable("Reddit OAuth token required")
        with httpx.Client(timeout=30, headers={"Authorization": f"Bearer {self.settings.reddit_token}", "User-Agent": self.settings.reddit_user_agent}) as client:
            r = client.get("https://oauth.reddit.com" + path, params=params)
            r.raise_for_status()
            return r.json()

    @staticmethod
    def parse(d):
        return Observation(platform="reddit", platform_post_id=d["id"], canonical_url="https://www.reddit.com" + d["permalink"], author_id=d.get("author_fullname"), author_name=d.get("author"), text=d.get("title", "") + "\n" + d.get("selftext", ""), published_at=utc(d.get("created_utc")), content_type="video" if d.get("is_video") else "text", metrics={"score": d.get("score"), "comments": d.get("num_comments")}, definitions={"score": "Reddit net score, not like count; may be fuzzed", "comments": "num_comments"}, source="reddit_oauth")

    def discover(self, query, limit, days):
        data = self.get("/search", {"q": query, "sort": "top", "t": "all", "limit": limit, "raw_json": 1})
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        return [p for x in data["data"]["children"] if (p := self.parse(x["data"])).published_at and p.published_at >= cutoff]

    def observe(self, post_id, url):
        data = self.get("/api/info", {"id": "t3_" + post_id, "raw_json": 1})
        rows = data["data"]["children"]
        if not rows:
            raise CollectorUnavailable("Post deleted, private, or unavailable")
        return self.parse(rows[0]["data"])


class YouTube:
    def __init__(self, settings):
        self.settings = settings

    def get(self, path, params):
        if not self.settings.youtube_api_key:
            raise CollectorUnavailable("YouTube Data API key required")
        with httpx.Client(timeout=30) as client:
            r = client.get("https://www.googleapis.com/youtube/v3/" + path, params={**params, "key": self.settings.youtube_api_key})
            r.raise_for_status()
            return r.json()

    @staticmethod
    def parse(d):
        s, m = d["snippet"], d.get("statistics", {})
        fields = {"views": "viewCount", "likes": "likeCount", "comments": "commentCount"}
        return Observation(platform="youtube", platform_post_id=d["id"], canonical_url="https://www.youtube.com/watch?v=" + d["id"], author_id=s.get("channelId"), author_name=s.get("channelTitle"), text=s.get("title", "") + "\n" + s.get("description", ""), published_at=s.get("publishedAt"), language=s.get("defaultLanguage"), content_type="video", metrics={k: int(m[v]) if v in m else None for k, v in fields.items()}, definitions=fields, source="youtube_data_api")

    def discover(self, query, limit, days):
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        found = self.get("search", {"part": "snippet", "type": "video", "q": query, "maxResults": min(limit, 50), "order": "viewCount", "publishedAfter": since})
        ids = ",".join(x["id"]["videoId"] for x in found.get("items", []))
        if not ids:
            return []
        return [self.parse(x) for x in self.get("videos", {"part": "snippet,statistics", "id": ids})["items"]]

    def observe(self, post_id, url):
        rows = self.get("videos", {"part": "snippet,statistics", "id": post_id})["items"]
        if not rows:
            raise CollectorUnavailable("Video unavailable")
        return self.parse(rows[0])


class PublicVideo:
    """Explicit URL metadata only; no browser sessions, cookies, or media downloads."""
    def __init__(self, settings):
        self.settings = settings

    def discover(self, query, limit, days):
        raise CollectorUnavailable("Keyword discovery not supported; use a permitted public video URL")

    def observe(self, post_id, url):
        if not self.settings.allow_public_urls:
            raise CollectorUnavailable("Public URL collection disabled; confirm permitted use in configuration")
        parsed = urlparse(url)
        hosts = {"www.tiktok.com": "tiktok", "www.youtube.com": "youtube", "youtu.be": "youtube"}
        if parsed.scheme != "https" or parsed.hostname not in hosts or parsed.username or parsed.port:
            raise ValueError("Only canonical HTTPS TikTok/YouTube video URLs are supported")
        from yt_dlp import YoutubeDL
        with YoutubeDL({"skip_download": True, "noplaylist": True, "quiet": True, "no_warnings": True, "socket_timeout": 20, "retries": 0, "extractor_retries": 0}) as ydl:
            d = ydl.extract_info(url, download=False)
        if not d or d.get("_type") in ("playlist", "multi_video"):
            raise ValueError("A single video is required")
        fields = {"views": "view_count", "likes": "like_count", "comments": "comment_count", "shares": "repost_count", "author_followers": "channel_follower_count"}
        return Observation(platform=hosts[parsed.hostname], platform_post_id=str(d["id"]), canonical_url=d.get("webpage_url", url), author_id=d.get("channel_id") or d.get("uploader_id"), author_name=d.get("uploader"), text=d.get("description") or d.get("title"), published_at=utc(d.get("timestamp")), content_type="video", language=d.get("language"), metrics={k: d.get(v) for k, v in fields.items()}, definitions=fields, source="yt_dlp_public_metadata")


def collectors(settings):
    from .social import X, Instagram
    return {"x": X(settings), "instagram": Instagram(settings), "reddit": Reddit(settings), "youtube": YouTube(settings), "public_video": PublicVideo(settings)}
