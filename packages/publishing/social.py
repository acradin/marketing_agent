from urllib.parse import urlparse
from packages.collectors.social import x_client, Instagram


def validate_publication(settings, draft):
    if not settings.enable_publishing:
        raise ValueError('Publishing is disabled')
    if draft.platform == 'reddit':
        if not settings.reddit_token or not draft.destination or draft.destination != settings.reddit_subreddit:
            raise ValueError('Configure Reddit token and matching subreddit first')
    elif draft.platform == 'x':
        if not all((settings.x_api_key, settings.x_api_secret, settings.x_access_token, settings.x_access_token_secret, settings.x_user_id)):
            raise ValueError('Configure X OAuth 1.0a credentials and user ID first')
        if draft.destination != settings.x_user_id:
            raise ValueError('Destination must match configured X user ID')
        # Conservative weighted count: non-Latin characters count twice. Server is authoritative.
        if not draft.text.strip() or sum(1 if ord(c) <= 0x10ff or 0x2000 <= ord(c) <= 0x200d or 0x2010 <= ord(c) <= 0x201f or 0x2032 <= ord(c) <= 0x2037 else 2 for c in draft.text) > 280:
            raise ValueError('X text exceeds conservative 280 weighted-character limit')
    elif draft.platform == 'instagram':
        if not settings.instagram_token or not settings.instagram_user_id or draft.destination != settings.instagram_user_id:
            raise ValueError('Configure Instagram token and matching professional account ID')
        image = urlparse((draft.brief or {}).get('image_url', ''))
        if image.scheme != 'https' or not image.hostname or image.username or image.password:
            raise ValueError('Instagram needs a publicly accessible HTTPS JPEG image URL')
        if len(draft.text) > 2200:
            raise ValueError('Instagram caption exceeds 2200 characters')
    else:
        raise ValueError('Direct publishing unsupported; export this draft for manual publication')


class XPublisher:
    def __init__(self, settings):
        self.settings = settings

    def publish(self, draft):
        validate_publication(self.settings, draft)
        client = x_client(self.settings)
        me = client.get_me(user_auth=True)
        if str(me.get('data', {}).get('id', '')) != draft.destination:
            raise ValueError('Authenticated X account differs from approved destination')
        result = client.create_tweet(text=draft.text, user_auth=True)
        remote_id = str(result['data']['id'])
        return remote_id, 'https://x.com/i/web/status/' + remote_id


class InstagramPublisher:
    def __init__(self, settings):
        self.settings = settings

    def publish(self, draft):
        validate_publication(self.settings, draft)
        api = Instagram(self.settings)
        container = api.request('POST', draft.destination + '/media',
                                image_url=draft.brief['image_url'], caption=draft.text)
        # Bounded polling; no automatic recreation or re-publication on failure.
        import time
        for attempt in range(5):
            status = api.request('GET', container['id'], fields='status_code')['status_code']
            if status == 'FINISHED':
                break
            if status in ('ERROR', 'EXPIRED'):
                raise RuntimeError('Instagram image processing failed')
            time.sleep(2)
        else:
            raise RuntimeError('Instagram image processing not finished')
        result = api.request('POST', draft.destination + '/media_publish', creation_id=container['id'])
        media = api.request('GET', result['id'], fields='permalink')
        return result['id'], media['permalink']
