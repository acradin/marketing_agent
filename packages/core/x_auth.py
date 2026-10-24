"""Browser-bound X OAuth 2.0 PKCE and rotating refresh tokens."""
import base64
import hashlib
import os
import secrets
import time
from pathlib import Path
from threading import RLock
from urllib.parse import urlencode, urlsplit

import httpx
from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import RedirectResponse

LOCK = RLock()
SCOPES = 'tweet.read tweet.write users.read offline.access'


def token_request(settings, data):
    with httpx.Client(timeout=20) as client:
        response = client.post('https://api.x.com/2/oauth2/token',
                               data={**data, 'client_id': settings.x_client_id},
                               auth=(settings.x_client_id, settings.x_client_secret) if settings.x_client_secret else None)
        response.raise_for_status()
        result = response.json()
    if (not isinstance(result.get('access_token'), str) or not result['access_token']
            or str(result.get('token_type', '')).lower() != 'bearer'
            or not set(SCOPES.split()).issubset(result.get('scope', '').split())
            or float(result.get('expires_in', 0)) <= 0):
        raise ValueError('Invalid token or missing permissions')
    return result


def save_tokens(settings, result, user_id, env_path):
    updates = {'VE_X_OAUTH_TOKEN': result['access_token'],
               'VE_X_REFRESH_TOKEN': result.get('refresh_token') or settings.x_refresh_token,
               'VE_X_TOKEN_EXPIRES_AT': str(time.time() + float(result['expires_in'])),
               'VE_X_USER_ID': user_id}
    if any(not isinstance(v, str) or '\n' in v or '\r' in v for v in updates.values()):
        raise ValueError('Invalid credentials')
    with LOCK:
        text = env_path.read_text(encoding='utf-8') if env_path.exists() else ''
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
        settings.x_oauth_token = updates['VE_X_OAUTH_TOKEN']
        settings.x_refresh_token = updates['VE_X_REFRESH_TOKEN']
        settings.x_token_expires_at = float(updates['VE_X_TOKEN_EXPIRES_AT'])
        settings.x_user_id = user_id


def access_token(settings, env_path=Path('.env')):
    with LOCK:
        if not settings.x_oauth_token:
            return settings.x_bearer_token
        if settings.x_token_expires_at > time.time() + 60:
            return settings.x_oauth_token
        try:
            if not settings.x_refresh_token or not settings.x_client_id:
                raise ValueError('Reconnect required')
            result = token_request(settings, {'grant_type': 'refresh_token', 'refresh_token': settings.x_refresh_token})
            save_tokens(settings, result, settings.x_user_id, env_path)
        except (httpx.HTTPError, ValueError, KeyError, TypeError, OSError):
            raise ValueError('X 인증 갱신에 실패했습니다. X 계정을 다시 연결하세요.') from None
        return settings.x_oauth_token


def x_router(settings, env_path=Path('.env')):
    router = APIRouter(prefix='/api/connections/x')
    pending = {}

    @router.get('')
    def status(response: Response):
        response.headers['Cache-Control'] = 'no-store'
        return {'app_configured': bool(settings.x_client_id),
                'connected': bool(settings.x_oauth_token and settings.x_user_id),
                'user_id': settings.x_user_id, 'redirect_uri': settings.x_redirect_uri,
                'expires_at': settings.x_token_expires_at}

    @router.post('/start')
    def start(request: Request, response: Response):
        if not settings.x_client_id:
            raise HTTPException(409, 'X 앱의 OAuth 2.0 Client ID를 VE_X_CLIENT_ID에 설정하고 서버를 재시작하세요. Meta 키는 사용할 수 없습니다.')
        redirect = urlsplit(settings.x_redirect_uri)
        if (redirect.scheme not in ('http', 'https') or redirect.query or redirect.fragment
                or redirect.path != '/api/connections/x/callback'
                or redirect.netloc != request.url.netloc or redirect.scheme != request.url.scheme):
            raise HTTPException(409, '등록된 X 콜백 주소와 같은 호스트·포트·프로토콜로 앱을 열어 주세요.')
        state, browser, verifier = (secrets.token_urlsafe(32) for _ in range(3))
        with LOCK:
            for key in list(pending):
                if pending[key][1] < time.time() or pending[key][0] == request.cookies.get('x_oauth'):
                    pending.pop(key)
            if len(pending) >= 100:
                raise HTTPException(429, '잠시 후 다시 시도하세요.')
            pending[state] = (browser, time.time() + 600, verifier)
        response.set_cookie('x_oauth', browser, httponly=True, samesite='lax', max_age=600,
                            secure=request.url.scheme == 'https', path='/api/connections/x')
        response.headers['Cache-Control'] = 'no-store'
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()
        return {'authorization_url': 'https://x.com/i/oauth2/authorize?' + urlencode({
            'client_id': settings.x_client_id, 'redirect_uri': settings.x_redirect_uri,
            'response_type': 'code', 'scope': SCOPES, 'state': state,
            'code_challenge': challenge, 'code_challenge_method': 'S256'})}

    @router.get('/callback')
    def callback(request: Request):
        # Never echo provider error text, authorization codes or token responses.
        outcome = 'failed'
        state = request.query_params.get('state', '')
        with LOCK:
            item = pending.get(state)
            valid = (item and item[1] >= time.time()
                     and secrets.compare_digest(item[0], request.cookies.get('x_oauth', '')))
            if valid:
                pending.pop(state)
        if valid:
            if request.query_params.get('error'):
                outcome = 'denied'
            elif request.query_params.get('code'):
                try:
                    with LOCK:
                        result = token_request(settings, {'grant_type': 'authorization_code',
                            'code': request.query_params['code'], 'redirect_uri': settings.x_redirect_uri,
                            'code_verifier': item[2]})
                        if not result.get('refresh_token'):
                            raise ValueError('Missing refresh token')
                        with httpx.Client(timeout=20) as client:
                            profile = client.get('https://api.x.com/2/users/me',
                                headers={'Authorization': 'Bearer ' + result['access_token']})
                            profile.raise_for_status()
                            user_id = str(profile.json()['data']['id'])
                        if not user_id.isdigit():
                            raise ValueError('Invalid account')
                        save_tokens(settings, result, user_id, env_path)
                    outcome = 'connected'
                except (httpx.HTTPError, ValueError, KeyError, TypeError, OSError):
                    pass
        response = RedirectResponse('/?x_connection=' + outcome, status_code=303,
                                    headers={'Cache-Control': 'no-store', 'Referrer-Policy': 'no-referrer'})
        response.delete_cookie('x_oauth', path='/api/connections/x')
        return response

    return router
