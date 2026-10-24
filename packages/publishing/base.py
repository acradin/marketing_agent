import hashlib
import json
from typing import Protocol


def approval_hash(draft):
    return hashlib.sha256(json.dumps({"text": draft.text, "title": draft.title, "platform": draft.platform, "destination": draft.destination, "version": draft.version, "image_url": (draft.brief or {}).get("image_url", "")}, sort_keys=True).encode()).hexdigest()


class Publisher(Protocol):
    def publish(self, draft) -> tuple[str, str]: ...


class RedditPublisher:
    def __init__(self, settings):
        self.settings = settings

    def publish(self, draft):
        import httpx
        if not self.settings.enable_publishing or not self.settings.reddit_token:
            raise RuntimeError("Publishing disabled or Reddit token absent")
        if draft.destination != self.settings.reddit_subreddit or not draft.destination:
            raise ValueError("Destination must match configured subreddit")
        with httpx.Client(timeout=30) as client:
            response = client.post("https://oauth.reddit.com/api/submit", headers={"Authorization": "Bearer " + self.settings.reddit_token, "User-Agent": self.settings.reddit_user_agent}, data={"api_type": "json", "kind": "self", "sr": draft.destination, "title": draft.title, "text": draft.text, "resubmit": "false"})
            response.raise_for_status()
            data = response.json()["json"]
            if data.get("errors"):
                raise RuntimeError("Reddit rejected publication; inspect account and subreddit permissions")
            return data["data"]["id"], data["data"]["url"]
