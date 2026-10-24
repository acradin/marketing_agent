# X 로그인 연결

발견 → X 연결 상세 → X 연결 → X에서 로그인·권한 승인.
승인하면 앱이 코드를 자동 교환하고 원래 화면에 연결 결과를 표시합니다.
주소를 복사해서 붙여 넣을 필요는 없습니다.

## 최초 앱 설정

1. X 개발자 콘솔에서 앱의 OAuth 2.0 사용자 인증을 활성화합니다.
2. 콜백 URL을 `http://127.0.0.1:8765/api/connections/x/callback`으로 정확히 등록합니다.
3. `.env`에 `VE_X_CLIENT_ID`를 설정합니다. Web App / Automated App은 `VE_X_CLIENT_SECRET`도 설정합니다. Native App 등 public client는 secret 없이 PKCE를 사용합니다.
4. 서버를 재시작하고 `http://127.0.0.1:8765/`를 엽니다. `localhost`와 `127.0.0.1`을 섞지 마세요. 다른 주소를 사용하면 `VE_X_REDIRECT_URI`와 개발자 콘솔을 함께 변경해야 합니다.

Client ID는 OAuth 1.0a API Key나 Meta·Instagram 앱 키와 다릅니다.
키와 토큰은 채팅이나 Git에 넣지 말고 로컬 `.env`에 직접 설정하세요.
서버는 `--no-access-log`로 실행해 콜백 URL의 승인 코드가 접근 로그에 남지 않게 합니다.

## 저장 및 사용

- 요청 권한: `tweet.read tweet.write users.read offline.access`.
- 브라우저에 묶인 일회용 state, 10분 만료, PKCE S256으로 인증 요청을 검증합니다.
- 승인 콜백에서 `/2/users/me`로 확인한 계정 ID와 토큰·만료 시각을 `.env`에 원자적으로 저장합니다. UI와 API 응답에는 토큰을 반환하지 않습니다.
- 수집과 발행은 연결된 OAuth 2.0 토큰을 사용하며, 만료 60초 전부터 다음 API 사용 시 갱신합니다. 갱신 실패 시 재연결 오류를 반환합니다.
- 기존 Bearer / OAuth 1.0a 설정은 OAuth 2.0 연결이 없을 때 계속 사용할 수 있습니다.
- 연결 자체는 발행하지 않습니다. 기존 발행 활성화, 초안 승인, 발행 대상 계정 검증을 유지합니다.
- X API 이용 권한·크레딧·요청 제한은 별도입니다. 로그인 성공이 검색이나 게시 API의 이용 가능성을 보장하지 않습니다.
- 로컬 단일 프로세스용 구현입니다. 서버 재시작 시 진행 중인 로그인은 다시 시작해야 합니다.

## 검증

`python -m pytest -q`에서 OAuth PKCE 교환, 저장 후 설정 재로딩, state/브라우저/만료 검증, 재사용 차단, 취소, 권한 부족, 제공자 오류, 토큰 갱신, OAuth 2.0 수집·발행 모드, 기존 발행 보호를 검사합니다. 제공자 응답은 테스트에서 모킹합니다. 실제 X 로그인은 유효한 X 앱 설정과 사용자 승인이 필요합니다.

공식 기준: [X OAuth 2.0 PKCE](https://docs.x.com/fundamentals/authentication/oauth-2-0/authorization-code).
