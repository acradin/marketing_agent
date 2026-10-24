"""Local browser flow with mocked X only; no live authorization or publishing."""
import socket
import threading
import time
from urllib.parse import parse_qs, urlsplit, urlencode

import uvicorn
from dotenv import dotenv_values
from playwright.sync_api import sync_playwright, expect

from apps.api.main import create_app
from packages.core.config import Settings
from test_x_auth import mock_provider


def test_browser_approval_return(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    origin = f'http://127.0.0.1:{port}'
    settings = Settings(_env_file=None, database_url='sqlite:///' + str(tmp_path/'test.db'),
                        x_client_id='fixture', x_client_secret='fixture',
                        x_redirect_uri=origin+'/api/connections/x/callback')
    app = create_app(settings, scheduling=False)
    server = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=port,
                                         log_level='error', access_log=False))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    try:
        for _ in range(100):
            if server.started:
                break
            time.sleep(.05)
        assert server.started
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            query = {}
            calls = mock_provider(monkeypatch, query)
            def authorize(route):
                query.update(parse_qs(urlsplit(route.request.url).query))
                # Fulfill the provider page, then simulate its top-level redirect.
                route.fulfill(content_type='text/html', body='<p>Mock X consent</p>')
            page.route('https://x.com/i/oauth2/authorize?*', authorize)
            page.goto(origin)
            card = page.locator('article').filter(has=page.locator('#x-connect'))
            card.locator('summary').click()
            page.locator('#x-connect').click()
            expect(page.locator('#x-start')).to_have_text('X에서 로그인·권한 승인')
            expect(page.locator('#x-start')).to_be_enabled()
            page.locator('#x-start').click()
            page.wait_for_url('https://x.com/i/oauth2/authorize?*')
            page.goto(settings.x_redirect_uri+'?'+urlencode({'code':'fixture', 'state':query['state'][0]}))
            expect(page.locator('#message')).to_contain_text('X 연결 완료')
            assert page.url == origin+'/'
            card = page.locator('article').filter(has=page.locator('#x-connect'))
            card.locator('summary').click()
            page.locator('#x-connect').click()
            expect(page.locator('#x-flow')).to_contain_text('연결된 X 계정 ID: 123')
            assert dotenv_values(tmp_path/'.env')['VE_X_OAUTH_TOKEN'] == 'new-token'
            assert len(calls) == 2 and not errors
            assert 'new-token' not in page.content()
            browser.close()
    finally:
        server.should_exit = True
        thread.join(timeout=5)
