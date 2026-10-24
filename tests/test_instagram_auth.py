from urllib.parse import urlsplit, parse_qs
import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient
from dotenv import dotenv_values
from packages.core.config import Settings
from packages.core.instagram_auth import instagram_router
from packages.collectors.social import Instagram


def setup(tmp_path):
    settings = Settings(_env_file=None, INSTAGRAM_APP_ID='app', INSTAGRAM_APP_SECRET='secret')
    env = tmp_path / '.env'
    env.write_text('# preserve\nOTHER=keep\nVE_INSTAGRAM_TOKEN=old\n')
    app = FastAPI()
    app.include_router(instagram_router(settings, env))
    return TestClient(app), settings, env


def callback(client):
    response = client.post('/api/connections/instagram/start')
    assert response.status_code == 200
    url = response.json()['authorization_url']
    assert 'secret' not in url
    query = parse_qs(urlsplit(url).query)
    assert query['scope'] == ['instagram_business_basic,instagram_business_content_publish']
    return query['redirect_uri'][0] + '?code=code&state=' + query['state'][0]


def test_success_persists_and_routes(tmp_path, monkeypatch):
    client, settings, env = setup(tmp_path)
    url = callback(client)
    real_client = httpx.Client
    seen = []
    def handler(request):
        seen.append(str(request.url).split('?')[0])
        if request.url.host == 'api.instagram.com':
            return httpx.Response(200, json={'access_token': 'short'})
        if request.url.path == '/access_token':
            return httpx.Response(200, json={'access_token': 'long', 'expires_in': 5184000})
        if request.url.path.endswith('/me'):
            return httpx.Response(200, json={'user_id': '123', 'username': 'tester'})
        assert request.url.host == 'graph.instagram.com'
        assert request.headers['Authorization'] == 'Bearer long'
        return httpx.Response(200, json={'data': []})
    monkeypatch.setattr(httpx, 'Client', lambda **kwargs: real_client(transport=httpx.MockTransport(handler), **kwargs))
    response = client.post('/api/connections/instagram/complete', json={'callback_url': url})
    assert response.status_code == 200
    assert response.json()['user_id'] == '123'
    assert 'long' not in response.text and 'secret' not in response.text
    assert dotenv_values(env)['OTHER'] == 'keep'
    restored = Settings(_env_file=env)
    assert restored.instagram_token == 'long' and restored.instagram_auth_mode == 'instagram'
    assert Instagram(settings).discover('*', 10, 7) == []
    assert client.post('/api/connections/instagram/complete', json={'callback_url': url}).status_code == 400
    assert len(seen) == 4


def test_state_browser_expiry_and_redirect(tmp_path, monkeypatch):
    client, _, env = setup(tmp_path)
    original = env.read_text()
    url = callback(client)
    assert client.post('/api/connections/instagram/complete', json={'callback_url': url.replace('localhost', 'evil.example')}).status_code == 400
    cookie = client.cookies.get('ig_oauth')
    client.cookies.clear()
    assert client.post('/api/connections/instagram/complete', json={'callback_url': url}).status_code == 400
    client.cookies.set('ig_oauth', cookie)
    monkeypatch.setattr('packages.core.instagram_auth.time.time', lambda: 99999999999)
    assert client.post('/api/connections/instagram/complete', json={'callback_url': url}).status_code == 400
    assert env.read_text() == original


def test_denial_and_failure_preserve_settings(tmp_path, monkeypatch):
    client, settings, env = setup(tmp_path)
    original = env.read_text()
    url = callback(client)
    assert client.post('/api/connections/instagram/complete', json={'callback_url': url.replace('code=code', 'error=access_denied')}).status_code == 400
    url = callback(client)
    real_client = httpx.Client
    monkeypatch.setattr(httpx, 'Client', lambda **kwargs: real_client(transport=httpx.MockTransport(lambda r: httpx.Response(400, json={'error': 'secret'})), **kwargs))
    response = client.post('/api/connections/instagram/complete', json={'callback_url': url})
    assert response.status_code == 502 and 'secret' not in response.text
    assert env.read_text() == original and not settings.instagram_token


def test_missing_keys(tmp_path):
    app = FastAPI()
    app.include_router(instagram_router(Settings(_env_file=None), tmp_path / '.env'))
    assert TestClient(app).post('/api/connections/instagram/start').status_code == 409
