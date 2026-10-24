"""Official API adapters; SDK results remain observations, never synthetic metrics."""
from datetime import datetime, timedelta, timezone
import re
import httpx
import tweepy
from .base import Observation


def x_client(settings):
    from packages.core.x_auth import access_token
    return tweepy.Client(bearer_token=access_token(settings) or None,
                         consumer_key=settings.x_api_key or None,
                         consumer_secret=settings.x_api_secret or None,
                         access_token=settings.x_access_token or None,
                         access_token_secret=settings.x_access_token_secret or None,
                         wait_on_rate_limit=False, return_type=dict)


class X:
    fields = ['created_at', 'author_id', 'public_metrics', 'lang']

    def __init__(self, settings):
        self.settings = settings

    @staticmethod
    def parse(d):
        fields = {'likes': 'like_count', 'comments': 'reply_count', 'shares': 'retweet_count', 'views': 'impression_count'}
        metrics = d.get('public_metrics', {})
        return Observation(platform='x', platform_post_id=str(d['id']),
                           canonical_url='https://x.com/i/web/status/' + str(d['id']),
                           author_id=d.get('author_id'), text=d.get('text'),
                           published_at=d.get('created_at'), language=d.get('lang'),
                           metrics={k: metrics.get(v) for k, v in fields.items()},
                           definitions=fields, source='x_api_v2')

    def client(self):
        if not (self.settings.x_bearer_token or self.settings.x_oauth_token):
            raise ValueError('X bearer token required for collection')
        return x_client(self.settings)

    def discover(self, query, limit, days):
        if days > 7:
            raise ValueError('X recent search supports at most 7 days')
        since = datetime.now(timezone.utc) - timedelta(days=days) + timedelta(seconds=30)
        result = self.client().search_recent_tweets(query=query, max_results=max(10, min(limit, 100)),
                                                   start_time=since, tweet_fields=self.fields)
        if result.get('errors'):
            raise RuntimeError('X search returned errors')
        return [self.parse(d) for d in result.get('data', [])][:limit]

    def observe(self, post_id, url):
        result = self.client().get_tweet(post_id, tweet_fields=self.fields)
        if not result.get('data'):
            raise RuntimeError('X post unavailable')
        return self.parse(result['data'])


class Instagram:
    """Facebook Login Graph API: configured professional account only."""
    fields = 'id,caption,media_type,permalink,timestamp,like_count,comments_count,username'

    def __init__(self, settings):
        self.settings = settings

    def request(self, method, path, **params):
        s = self.settings
        if not s.instagram_token or not s.instagram_user_id:
            raise ValueError('Instagram professional account ID and access token required')
        if not re.fullmatch(r'v\d+\.\d+', s.instagram_api_version):
            raise ValueError('Invalid Graph API version')
        if not re.fullmatch(r'\d+(?:/(?:media|media_publish))?', path):
            raise ValueError('Invalid Instagram API path')
        with httpx.Client(timeout=30) as client:
            response = client.request(method, f'{"https://graph.instagram.com" if s.instagram_auth_mode == "instagram" else "https://graph.facebook.com"}/{s.instagram_api_version}/{path}',
                                      headers={'Authorization': 'Bearer ' + s.instagram_token},
                                      **({'params': params} if method == 'GET' else {'data': params}))
            response.raise_for_status()
            result = response.json()
            if result.get('error'):
                raise RuntimeError('Instagram rejected request')
            return result

    @staticmethod
    def parse(d):
        return Observation(platform='instagram', platform_post_id=d['id'], canonical_url=d['permalink'],
                           text=d.get('caption'), author_name=d.get('username'), published_at=d.get('timestamp'),
                           content_type={'VIDEO': 'video', 'CAROUSEL_ALBUM': 'carousel'}.get(d.get('media_type'), 'image'),
                           metrics={'likes': d.get('like_count'), 'comments': d.get('comments_count')},
                           definitions={'likes': 'like_count', 'comments': 'comments_count'}, source='instagram_graph')

    def discover(self, query, limit, days):
        result = self.request('GET', self.settings.instagram_user_id + '/media', fields=self.fields, limit=50)
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        rows = [self.parse(d) for d in result.get('data', [])]
        return [p for p in rows if p.published_at and p.published_at >= cutoff
                and (query == '*' or query.casefold() in (p.text or '').casefold())][:limit]

    def observe(self, post_id, url):
        return self.parse(self.request('GET', post_id, fields=self.fields))
