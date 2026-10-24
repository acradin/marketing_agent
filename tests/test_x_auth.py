from pathlib import Path
from urllib.parse import urlsplit, parse_qs, urlencode
import base64
import hashlib
import time
from types import SimpleNamespace
import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from dotenv import dotenv_values
from packages.core.config import Settings
from packages.core.x_auth import x_router, access_token, SCOPES
from packages.publishing.social import XPublisher


def setup(tmp_path):
    settings = Settings(_env_file=None, x_client_id='client', x_client_secret='secret',
                        x_redirect_uri='http://testserver/api/connections/x/callback')
    path = tmp_path / '.env'
    path.write_text('# keep\nOTHER=value\n', encoding='utf-8')
    app = FastAPI()
    app.include_router(x_router(settings, path))
    return TestClient(app), settings, path


def begin(client):
    response = client.post('/api/connections/x/start')
    assert response.status_code == 200
    assert 'HttpOnly' in response.headers['set-cookie']
    assert 'SameSite=lax' in response.headers['set-cookie']
    return parse_qs(urlsplit(response.json()['authorization_url']).query)


def mock_provider(monkeypatch, query=None, fail=False, scope=SCOPES):
    calls = []
    real = httpx.Client
    def respond(request):
        calls.append(request)
        if fail:
            return httpx.Response(400, json={'error': 'secret-provider-token'})
        if request.url.path == '/2/oauth2/token':
            data = parse_qs(request.content.decode())
            assert request.headers['Authorization'].startswith('Basic ')
            if data['grant_type'] == ['authorization_code']:
                digest = base64.urlsafe_b64encode(hashlib.sha256(data['code_verifier'][0].encode()).digest()).rstrip(b'=').decode()
                assert query['code_challenge'] == [digest]
                assert query['code_challenge_method'] == ['S256']
            return httpx.Response(200, json={'access_token': 'new-token', 'refresh_token': 'new-refresh',
                'token_type': 'bearer', 'scope': scope, 'expires_in': 7200})
        assert request.url.path == '/2/users/me'
        assert request.headers['Authorization'] == 'Bearer new-token'
        return httpx.Response(200, json={'data': {'id': '123'}})
    monkeypatch.setattr('packages.core.x_auth.httpx.Client', lambda **kw: real(transport=httpx.MockTransport(respond), **kw))
    return calls


def callback(client, query, **extra):
    return client.get('/api/connections/x/callback?' + urlencode({'state': query['state'][0], 'code': 'code', **extra}), follow_redirects=False)


def test_success_persistence_and_replay(tmp_path, monkeypatch):
    client, settings, path = setup(tmp_path)
    query = begin(client)
    calls = mock_provider(monkeypatch, query)
    response = callback(client, query)
    assert response.headers['location'] == '/?x_connection=connected'
    assert response.headers['Referrer-Policy'] == 'no-referrer'
    assert len(calls) == 2
    saved = dotenv_values(path)
    assert saved['OTHER'] == 'value'
    assert saved['VE_X_OAUTH_TOKEN'] == settings.x_oauth_token == 'new-token'
    assert saved['VE_X_USER_ID'] == settings.x_user_id == '123'
    assert Settings(_env_file=path).x_refresh_token == 'new-refresh'
    status = client.get('/api/connections/x').json()
    assert status['connected'] is True and 'new-token' not in str(status)
    assert callback(client, query).headers['location'] == '/?x_connection=failed'
    assert len(calls) == 2


@pytest.mark.parametrize('case', ['state', 'browser', 'expired', 'denied', 'missing_code'])
def test_rejected_callbacks(tmp_path, monkeypatch, case):
    client, settings, path = setup(tmp_path)
    query = begin(client)
    calls = mock_provider(monkeypatch, query)
    extra = {}
    if case == 'state': query['state'] = ['wrong']
    if case == 'browser': client.cookies.clear()
    if case == 'expired': monkeypatch.setattr('packages.core.x_auth.time.time', lambda: 9999999999)
    if case == 'denied': extra['error'] = 'access_denied'
    if case == 'missing_code': extra['code'] = ''
    response = callback(client, query, **extra)
    assert response.headers['location'] == '/?x_connection=' + ('denied' if case == 'denied' else 'failed')
    assert not calls and not settings.x_oauth_token
    assert path.read_text() == '# keep\nOTHER=value\n'


@pytest.mark.parametrize('fail,scope', [(True, SCOPES), (False, 'tweet.read users.read')])
def test_provider_failure_preserves_credentials(tmp_path, monkeypatch, fail, scope):
    client, settings, path = setup(tmp_path)
    query = begin(client)
    mock_provider(monkeypatch, query, fail=fail, scope=scope)
    response = callback(client, query)
    assert response.headers['location'] == '/?x_connection=failed'
    assert 'secret-provider-token' not in response.text
    assert not settings.x_oauth_token


def test_refresh_and_failure(tmp_path, monkeypatch):
    client, settings, path = setup(tmp_path)
    settings.x_oauth_token = 'expired'
    settings.x_refresh_token = 'old-refresh'
    settings.x_user_id = '123'
    calls = mock_provider(monkeypatch)
    assert access_token(settings, path) == 'new-token'
    assert len(calls) == 1
    assert parse_qs(calls[0].content.decode())['refresh_token'] == ['old-refresh']
    assert dotenv_values(path)['VE_X_REFRESH_TOKEN'] == 'new-refresh'
    assert access_token(settings, path) == 'new-token' and len(calls) == 1
    settings.x_token_expires_at = 0
    mock_provider(monkeypatch, fail=True)
    with pytest.raises(ValueError, match='X'):
        access_token(settings, path)
    assert settings.x_oauth_token == 'new-token'


def test_configuration_and_origin(tmp_path):
    client, settings, _ = setup(tmp_path)
    settings.x_client_id = ''
    assert client.post('/api/connections/x/start').status_code == 409
    settings.x_client_id = 'client'
    settings.x_redirect_uri = 'http://localhost/api/connections/x/callback'
    assert client.post('/api/connections/x/start').status_code == 409


def test_oauth_publish_and_collector(monkeypatch):
    settings = Settings(_env_file=None, x_oauth_token='user-token', x_user_id='123',
                        x_token_expires_at=time.time()+7200, enable_publishing=True)
    from packages.collectors.social import X
    assert X(settings).client().bearer_token == 'user-token'
    calls = []
    def me(**kw):
        assert kw == {'user_auth': False}
        return {'data': {'id': '123'}}
    def post(**kw):
        calls.append(kw)
        return {'data': {'id': '789'}}
    monkeypatch.setattr('packages.publishing.social.x_client', lambda _: SimpleNamespace(get_me=me, create_tweet=post))
    assert XPublisher(settings).publish(SimpleNamespace(platform='x', destination='123', text='test'))[0] == '789'
    assert calls == [{'text': 'test', 'user_auth': False}]


def test_app_write_protection(tmp_path):
    from apps.api.main import create_app
    settings = Settings(_env_file=None, database_url='sqlite:///' + str(tmp_path/'test.db'), x_client_id='client',
                        x_redirect_uri='http://testserver/api/connections/x/callback')
    with TestClient(create_app(settings, scheduling=False)) as client:
        assert client.post('/api/connections/x/start').status_code == 403
        assert client.post('/api/connections/x/start', headers={'X-Viral-Local':'1', 'Origin':'https://evil.example'}).status_code == 403
        assert client.post('/api/connections/x/start', headers={'X-Viral-Local':'1'}).status_code == 200
