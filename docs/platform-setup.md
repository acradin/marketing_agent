# 추가 플랫폼 설정 및 구현 범위

## 지원 기능

| 플랫폼 | 수집 | 발행 | 구현 기반 |
|---|---|---|---|
| Reddit | 키워드·성과 반복 수집 | 텍스트 | HTTPX + 공식 OAuth API |
| YouTube | 키워드·통계 | JSON 내보내기 | HTTPX + Data API |
| X | 최근 7일 검색·통계 | 텍스트, OAuth 계정 ID 검증 | Tweepy 4.17.0 (MIT) |
| Instagram | 연결한 프로 계정 최신 50개 중 캡션 필터 | 공개 HTTPS JPEG 한 장 + 캡션 | HTTPX + Graph API, Facebook Login |
| TikTok | 허용된 개별 공개 영상 URL 메타데이터 | JSON 내보내기 | yt-dlp |

Instagram은 전체 공개 게시물 키워드 검색이 아닙니다. 검색어 `*`는 내 계정 최신 게시물을 조회합니다. X 검색은 최대 7일이고 API 접근 권한·요금·쿼터는 계정에 종속됩니다. 누락된 지표는 null이며 다른 지표로 추정하지 않습니다.

## X

`.env.example`의 `VE_X_*` 항목을 로컬 `.env`에 추가하세요.

- 수집: `VE_X_BEARER_TOKEN`.
- 발행: `VE_X_API_KEY`, `VE_X_API_SECRET`, `VE_X_ACCESS_TOKEN`, `VE_X_ACCESS_TOKEN_SECRET`.
- 대상 계정: `VE_X_USER_ID`는 사용자 이름이 아닌 숫자 ID입니다. 초안 발행 대상에도 같은 ID를 넣습니다.
- 앱과 사용자 토큰에 쓰기 권한이 필요합니다. 발행 직전에 인증한 계정 ID를 다시 확인합니다.
- 본문만 발행하며 제목은 내부 검토용입니다. 문자 수는 보수적으로 계산합니다. 긴 URL·복합 이모지는 실제 X 제한보다 일찍 거부될 수 있습니다. 미디어·스레드·장문 게시물은 지원하지 않습니다.

## Instagram

이 구현은 **Facebook Login 방식**입니다. Instagram Login 방식의 토큰을 혼용하지 마세요.

- Facebook 페이지에 연결된 Instagram 프로 계정과 해당 앱 접근 권한이 필요합니다.
- `VE_INSTAGRAM_TOKEN`: Facebook Login에서 얻은 Graph API 액세스 토큰.
- `VE_INSTAGRAM_USER_ID`: Instagram 프로 계정 숫자 ID.
- `VE_INSTAGRAM_API_VERSION=v24.0`: 앱에서 지원되는 버전을 확인하세요.
- 수집에는 `instagram_basic` 및 계정/페이지 접근 권한, 발행에는 `instagram_content_publish` 등 앱 구성에 맞는 권한이 필요합니다. 앱 심사·계정 역할 조건은 Meta 콘솔에서 확인합니다.
- 생성/검토 화면에서 같은 계정 ID와 공개 HTTPS JPEG URL을 입력합니다. Meta 서버가 이미지를 가져갈 수 있어야 합니다. 로컬 파일 업로드는 구현하지 않았습니다.
- 이미지 URL은 승인 해시에 포함됩니다. 변경하면 기존 승인이 취소됩니다. URL 내용 자체의 변경은 감지하지 못하므로 승인 후 변경되지 않는 이미지 주소를 사용하세요.
- 이미지 컨테이너 생성 → 준비 상태 확인 → 발행 → 원문 URL 조회 순서입니다. Reels·캐러셀·스토리는 미지원입니다.

## 실행과 검토

```powershell
./scripts/start.ps1 -Check
./scripts/start.ps1
```

실제 앱은 http://127.0.0.1:8765 입니다. 설정 변경 후 앱을 재시작하세요. 발행하려면 `VE_ENABLE_PUBLISHING=true`를 설정하고 저장본을 승인한 뒤 발행 버튼을 누릅니다. 수집 예약은 발행 예약이 아닙니다.

TikTok·YouTube·수동 초안은 검토 화면의 **저장본 JSON 내보내기**로 내려받습니다. 내보내기는 게시나 발행 완료 처리가 아닙니다. TikTok Direct Post, 토큰 자동 갱신, 영상 제작·업로드는 남은 범위입니다.

발행 도중 예외가 생기면 `publication_unknown`으로 기록하고 자동 재발행하지 않습니다. 컨테이너 준비 실패나 계정 불일치처럼 실제 게시 전 실패도 보수적으로 이 상태가 될 수 있습니다. 실제 계정 확인 후 별도 복구가 필요하며 복구 UI는 아직 없습니다.

## 오픈소스와 참고 문서

새 SNS 인증 클라이언트는 직접 작성하지 않고 [Tweepy](https://github.com/tweepy/tweepy)를 사용했습니다. Instagram은 기존 [HTTPX](https://github.com/encode/httpx)로 공식 API를 호출하는 얇은 어댑터입니다. yt-dlp·FastAPI·SQLAlchemy·Alembic·APScheduler도 기존대로 사용합니다. 의존성은 설치 패키지의 라이선스를 유지하며 외부 조사용 소스 사본은 저장소 업로드에서 제외합니다.

- [Tweepy Client API](https://docs.tweepy.org/en/latest/client.html)
- [Meta 공식 Instagram API 컬렉션](https://www.postman.com/meta/instagram/documentation/6yqw8pt/instagram-api)
- [yt-dlp](https://github.com/yt-dlp/yt-dlp)

계약 테스트는 실제 계정의 권한과 동작을 보증하지 않습니다. 실제 연결 진단 결과는 `live-connections.json`을 확인하세요.
