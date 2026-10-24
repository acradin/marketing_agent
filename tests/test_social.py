from types import SimpleNamespace
from datetime import datetime, timezone
import httpx
import pytest
from test_engine import client, create_draft
from packages.collectors.social import X, Instagram
from packages.core.config import Settings
from packages.core.models import Draft
from packages.publishing.base import approval_hash
from packages.publishing.social import XPublisher, InstagramPublisher


def configured():
    return Settings(_env_file=None, enable_publishing=True, x_bearer_token='test',
                    x_api_key='test', x_api_secret='test', x_access_token='test',
                    x_access_token_secret='test', x_user_id='123',
                    instagram_token='test', instagram_user_id='456')


def test_x_search_contract(monkeypatch):
    calls = []
    def search(**kw):
        calls.append(kw)
        return {'data': [{'id': '1', 'text': 'test', 'public_metrics': {'like_count': 2}}]}
    monkeypatch.setattr('packages.collectors.social.x_client', lambda _: SimpleNamespace(search_recent_tweets=search))
    result = X(configured()).discover('test', 1, 7)
    assert calls[0]['max_results'] == 10
    assert result[0].metrics['likes'] == 2 and result[0].metrics['views'] is None
    with pytest.raises(ValueError):
        X(configured()).discover('test', 1, 8)


def test_instagram_http_contract_and_scope(monkeypatch):
    real_client = httpx.Client
    def respond(request):
        assert request.url.host == 'graph.facebook.com'
        assert request.url.path == '/v24.0/456/media'
        assert request.headers['Authorization'] == 'Bearer test'
        assert 'access_token' not in str(request.url)
        return httpx.Response(200, json={'data': [
            {'id': '1', 'caption': 'MATCH', 'permalink': 'https://www.instagram.com/p/test/',
             'timestamp': datetime.now(timezone.utc).isoformat(), 'like_count': 9},
            {'id': '2', 'caption': 'old match', 'permalink': 'https://www.instagram.com/p/old/',
             'timestamp': '2000-01-01T00:00:00Z'}]})
    monkeypatch.setattr('packages.collectors.social.httpx.Client', lambda **kw: real_client(transport=httpx.MockTransport(respond), **kw))
    rows = Instagram(configured()).discover('match', 10, 7)
    assert len(rows) == 1 and rows[0].metrics['comments'] is None


def test_x_account_mismatch_never_posts(monkeypatch):
    monkeypatch.setattr('packages.publishing.social.x_client', lambda _: SimpleNamespace(get_me=lambda **kw: {'data': {'id': '999'}}))
    with pytest.raises(ValueError, match='differs'):
        XPublisher(configured()).publish(SimpleNamespace(platform='x', destination='123', text='test'))


def test_x_publish_contract(monkeypatch):
    calls = []
    def create(**kw):
        calls.append(kw)
        return {'data': {'id': '789'}}
    monkeypatch.setattr('packages.publishing.social.x_client', lambda _: SimpleNamespace(
        get_me=lambda **kw: {'data': {'id': '123'}}, create_tweet=create))
    result = XPublisher(configured()).publish(SimpleNamespace(platform='x', destination='123', text='test'))
    assert calls == [{'text': 'test', 'user_auth': True}]
    assert result == ('789', 'https://x.com/i/web/status/789')


@pytest.mark.parametrize('fail', [False, True])
def test_instagram_publish_stages(monkeypatch, fail):
    calls = []
    def request(self, method, path, **params):
        calls.append((method, path, params))
        if path == '456/media': return {'id': '777'}
        if path == '777': return {'status_code': 'ERROR' if fail else 'FINISHED'}
        if path == '456/media_publish': return {'id': '888'}
        return {'permalink': 'https://www.instagram.com/p/test/'}
    monkeypatch.setattr(Instagram, 'request', request)
    draft = SimpleNamespace(platform='instagram', destination='456', text='caption', brief={'image_url': 'https://example.com/image.jpg'})
    if fail:
        with pytest.raises(RuntimeError): InstagramPublisher(configured()).publish(draft)
        assert all(path != '456/media_publish' for _, path, _ in calls)
    else:
        assert InstagramPublisher(configured()).publish(draft)[0] == '888'
        assert calls[0][2] == {'image_url': draft.brief['image_url'], 'caption': 'caption'}
        assert calls[2][2] == {'creation_id': '777'}


@pytest.mark.parametrize('platform', ['x', 'instagram'])
def test_multiplatform_receipt_and_observation_jobs(client, platform):
    draft_id = create_draft(client)
    service = client.app.state.service
    service.settings = configured()
    with service.sessions.begin() as session:
        draft = session.get(Draft, draft_id)
        draft.platform = platform
        draft.destination = '123' if platform == 'x' else '456'
        draft.brief = {'image_url': 'https://example.com/image.jpg'}
    client.post(f'/api/drafts/{draft_id}/approve', json={'version': 1})
    calls = []
    def publish(draft):
        calls.append(1)
        return '999', 'https://example.com/published/' + platform
    service.publishers[platform].publish = publish
    assert client.post(f'/api/drafts/{draft_id}/publish').status_code == 200
    assert client.post(f'/api/drafts/{draft_id}/publish').status_code == 200
    assert len(calls) == 1
    assert all(j['payload']['backend'] == platform for j in client.get('/api/jobs').json())
    receipt = next(p for p in client.get('/api/posts').json() if p['platform'] == platform)
    assert receipt['content_type'] == ('image' if platform == 'instagram' else 'text')


def test_image_edit_revokes_approval_and_export_is_not_publish(client):
    draft_id = create_draft(client)
    client.post(f'/api/drafts/{draft_id}/approve', json={'version': 1})
    before = client.get('/api/drafts').json()[0]
    response = client.put(f'/api/drafts/{draft_id}', json={k: before[k] for k in ('title','text','destination','version')} | {'image_url': 'https://example.com/new.jpg'})
    assert response.json()['state'] == 'review'
    assert response.json()['approved_hash'] is None
    export = client.get(f'/api/drafts/{draft_id}/export')
    assert export.json()['image_url'] == 'https://example.com/new.jpg'
    assert export.json()['published'] is False
    assert 'attachment' in export.headers['Content-Disposition']
    assert client.get('/api/drafts').json()[0]['state'] == 'review'


def test_tampered_image_hash_and_unsupported_publish(client):
    draft_id = create_draft(client)
    client.post(f'/api/drafts/{draft_id}/approve', json={'version': 1})
    with client.app.state.sessions.begin() as session:
        draft = session.get(Draft, draft_id)
        draft.brief = {'image_url': 'https://example.com/tampered.jpg'}
        assert approval_hash(draft) != draft.approved_hash
    assert client.post(f'/api/drafts/{draft_id}/publish').status_code == 409
    with client.app.state.sessions.begin() as session:
        draft = session.get(Draft, draft_id)
        draft.platform = 'tiktok'
        draft.approved_hash = approval_hash(draft)
    assert client.post(f'/api/drafts/{draft_id}/publish').status_code == 409
    assert client.get('/api/drafts').json()[0]['state'] == 'approved'
