"""Local, browser-bound Instagram OAuth. Credentials never leave the backend."""
import secrets
import time
import os
from pathlib import Path
from threading import Lock
from urllib.parse import urlencode, urlsplit, parse_qs

import httpx
from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field


class Completion(BaseModel):
    callback_url: str = Field(max_length=8192)


def instagram_router(settings, env_path=Path('.env')):
    router = APIRouter(prefix='/api/connections/instagram')
    pending = {}
    lock = Lock()
    scopes = 'instagram_business_basic,instagram_business_content_publish'

    @router.get('')
    def status():
        return {'app_configured': bool(settings.instagram_app_id and settings.instagram_app_secret),
                'connected': bool(settings.instagram_token and settings.instagram_user_id),
                'user_id': settings.instagram_user_id, 'auth_mode': settings.instagram_auth_mode,
                'redirect_uri': settings.instagram_redirect_uri}

    @router.post('/start')
    def start(request: Request, response: Response):
        if not settings.instagram_app_id or not settings.instagram_app_secret:
            raise HTTPException(409, 'INSTAGRAM_APP_ID / INSTAGRAM_APP_SECRET 설정이 필요합니다.')
        redirect = urlsplit(settings.instagram_redirect_uri)
        if redirect.scheme != 'https' or not redirect.netloc or redirect.query or redirect.fragment:
            raise HTTPException(409, 'Instagram redirect URI는 쿼리 없는 HTTPS 주소여야 합니다.')
        state, browser = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        with lock:
            for key in list(pending):
                if pending[key][1] < time.time() or pending[key][0] == request.cookies.get('ig_oauth'):
                    pending.pop(key)
            if len(pending) >= 100:
                raise HTTPException(429, '잠시 후 다시 시도하세요.')
            pending[state] = (browser, time.time() + 600)
        response.set_cookie('ig_oauth', browser, httponly=True, samesite='strict', max_age=600,
                            secure=request.url.scheme == 'https', path='/api/connections/instagram')
        response.headers['Cache-Control'] = 'no-store'
        return {'authorization_url': 'https://www.instagram.com/oauth/authorize?' + urlencode({
            'client_id': settings.instagram_app_id, 'redirect_uri': settings.instagram_redirect_uri,
            'response_type': 'code', 'scope': scopes, 'state': state,
            'enable_fb_login': '0', 'force_authentication': '1'})}

    @router.post('/complete')
    def complete(body: Completion, request: Request, response: Response):
        url, expected = urlsplit(body.callback_url), urlsplit(settings.instagram_redirect_uri)
        if (url.scheme, url.netloc, url.path) != (expected.scheme, expected.netloc, expected.path):
            raise HTTPException(400, '등록된 리디렉션 주소 전체를 붙여 넣으세요.')
        query = parse_qs(url.query)
        state = query.get('state', [''])[0]
        with lock:
            item = pending.get(state)
            if not item or item[1] < time.time() or not secrets.compare_digest(item[0], request.cookies.get('ig_oauth', '')):
                raise HTTPException(400, '인증 요청이 만료되었거나 브라우저가 다릅니다. 연결을 다시 시작하세요.')
            pending.pop(state)
        if 'error' in query:
            raise HTTPException(400, 'Instagram 권한 승인이 취소되었습니다. 다시 연결하세요.')
        code = query.get('code', [''])[0]
        if not code:
            raise HTTPException(400, '인증 코드가 없습니다. 다시 연결하세요.')
        try:
            with httpx.Client(timeout=30) as client:
                short = client.post('https://api.instagram.com/oauth/access_token', data={
                    'client_id': settings.instagram_app_id, 'client_secret': settings.instagram_app_secret,
                    'grant_type': 'authorization_code', 'redirect_uri': settings.instagram_redirect_uri, 'code': code})
                short.raise_for_status()
                short_data = short.json()
                if 'data' in short_data:
                    if len(short_data['data']) != 1:
                        raise ValueError('Ambiguous identity')
                    short_data = short_data['data'][0]
                long = client.get('https://graph.instagram.com/access_token', params={
                    'grant_type': 'ig_exchange_token', 'client_secret': settings.instagram_app_secret,
                    'access_token': short_data['access_token']})
                long.raise_for_status()
                token = long.json()['access_token']
                profile = client.get(f'https://graph.instagram.com/{settings.instagram_api_version}/me',
                                     params={'fields': 'user_id,username'}, headers={'Authorization': 'Bearer ' + token})
                profile.raise_for_status()
                account = profile.json()
                user_id = str(account['user_id'])
                if not user_id.isdigit() or not token:
                    raise ValueError('Invalid identity')
            # Atomic replacement preserves all unrelated keys and comments.
            with lock:
                text = env_path.read_text(encoding='utf-8') if env_path.exists() else ''
                updates = {'VE_INSTAGRAM_TOKEN': token, 'VE_INSTAGRAM_USER_ID': user_id,
                           'VE_INSTAGRAM_AUTH_MODE': 'instagram'}
                lines = [line for line in text.splitlines() if line.split('=', 1)[0].strip().removeprefix('export ') not in updates]
                lines += [key + "='" + value.replace('\\', '\\\\').replace("'", "\\'") + "'" for key, value in updates.items()]
                temp = env_path.with_name('.env.oauth-' + secrets.token_hex(8))
                try:
                    with open(temp, 'x', encoding='utf-8') as handle:
                        os.chmod(temp, 0o600)
                        handle.write('\n'.join(lines) + '\n')
                    os.replace(temp, env_path)
                finally:
                    temp.unlink(missing_ok=True)
                settings.instagram_token, settings.instagram_user_id = token, user_id
                settings.instagram_auth_mode = 'instagram'
        except (httpx.HTTPError, ValueError, KeyError, TypeError, OSError):
            # Provider URLs/errors can contain credentials. Never return or log them.
            raise HTTPException(502, 'Instagram 연결에 실패했습니다. 앱 키·리디렉션 URI·프로 계정·앱 역할을 확인하고 다시 연결하세요.') from None
        response.delete_cookie('ig_oauth', path='/api/connections/instagram')
        response.headers['Cache-Control'] = 'no-store'
        return {'connected': True, 'user_id': user_id, 'username': account.get('username', ''),
                'expires_in': long.json().get('expires_in')}

    return router
