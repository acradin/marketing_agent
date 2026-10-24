# Instagram 계정 연결

기존 `.env`의 `INSTAGRAM_APP_ID`와 `INSTAGRAM_APP_SECRET`을 사용합니다. `VE_` 접두사가 있는 동일 이름도 지원합니다. Meta·Threads 앱 키로 자동 대체하지 않습니다.

1. Meta 개발자 앱의 **Instagram API with Instagram Login → Business login settings**에서 리디렉션 URI `https://localhost/instagram/callback`을 등록합니다. 앱 설정이 이 주소를 허용하는지는 실제 대시보드에서 확인해야 합니다. 다른 HTTPS 주소를 등록했다면 `.env`의 `VE_INSTAGRAM_REDIRECT_URI`를 같은 주소로 설정하고 서버를 재시작합니다.
2. Viral Engine → 발견 → Instagram → 연결 상세 → **Instagram 연결 → 로그인 준비**를 누릅니다.
3. **Instagram에서 로그인·권한 승인** 링크를 열어 비즈니스 또는 크리에이터 계정으로 승인합니다. 개발 모드에서는 해당 계정의 앱 역할·테스터 초대 수락이 필요할 수 있습니다.
4. 승인 뒤 이동한 주소 전체를 복사하여 원래 Viral Engine 화면의 **승인 후 돌아온 주소**에 붙여 넣고 **연결 완료**를 누릅니다. 기본 localhost HTTPS 주소는 서버가 없어 오류 화면이 나타날 수 있으며, 주소창에 `code`와 `state`가 있는 주소를 복사하면 됩니다. 이 주소는 인증 정보를 포함하므로 채팅에 보내지 마세요.
5. 서버가 인증 코드를 토큰으로 교환하고 장기 토큰과 프로 계정 ID를 `.env`에 저장합니다. 실행 중인 수집·발행 어댑터에도 즉시 반영됩니다. 발행 활성화 여부는 바뀌지 않습니다.

이는 로컬 앱용 수동 콜백 전달 방식입니다. 공개 HTTPS 콜백 서버나 자동 리디렉션 처리는 포함하지 않습니다. 동일 브라우저에서 10분 안에 완료해야 하며 서버를 재시작하면 다시 로그인 준비를 눌러야 합니다.

연결 후 `VE_INSTAGRAM_AUTH_MODE=instagram`을 저장하고 `graph.instagram.com`을 사용합니다. 기존 Facebook Login 토큰 설정은 기본 `facebook` 모드에서 유지됩니다. 요청 권한은 `instagram_business_basic`, `instagram_business_content_publish`입니다.

토큰 자동 갱신은 아직 없습니다. 만료·권한 철회 시 다시 연결해야 합니다. 앱 키가 로컬 설정에서 읽히는 것과 Meta에서 실제 승인·토큰 교환에 성공하는 것은 별개입니다.

## 검증

- 기존 테스트 및 새 OAuth 테스트 28개 통과.
- 새 테스트는 모의 API로 토큰 교환, 프로 계정 조회, `.env` 보존·재로드, Instagram API 호스트 전환을 확인합니다.
- 잘못된 리디렉션, 다른 브라우저, 만료, 콜백 재사용, 승인 거절, API 실패를 확인합니다.
- 실제 Instagram 로그인·권한 승인·토큰 교환은 아직 수행하지 않았습니다.
- Meta 공식 Business Login 문서는 이번 조회에서 HTTP 429를 반환하여 최신 대시보드 정책을 확인하지 못했습니다.

공식 참고: https://developers.facebook.com/docs/instagram-platform/instagram-api-with-instagram-login/business-login/
