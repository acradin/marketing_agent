# Viral Engine 0.1.0

SNS에서 반응이 좋은 게시물을 수집·분석하고, 그 패턴으로 내 제품의 게시물 초안을 만들어 사람이 검토·승인한 뒤 발행하는 **로컬 실행형 콘텐츠 실험 엔진**입니다.

> **현재 상태:** 첫 구현 단계입니다. 외부 서비스 없이도 UI와 데이터 계층은 동작하지만, 명세 전체가 완료되었거나 실제 플랫폼 연결이 검증되었다는 뜻은 아닙니다. 남은 범위는 [아래](#미구현-범위)를 참고하세요.

## 목차

- [지원 플랫폼](#지원-플랫폼)
- [빠른 시작: 데모](#빠른-시작-데모-api-키-불필요)
- [실제 연결로 실행](#실제-연결로-실행)
- [환경 변수](#환경-변수)
- [사용 흐름](#사용-흐름)
- [데이터와 작업 처리](#데이터와-작업-처리)
- [순위 해석](#순위-해석)
- [테스트](#테스트)
- [미구현 범위](#미구현-범위)
- [관련 문서](#관련-문서)

## 지원 플랫폼

| 플랫폼 | 수집 | 발행 |
|---|---|---|
| Reddit | 키워드 검색, 성과 반복 수집 | 텍스트 |
| YouTube | 키워드 검색, 통계 | JSON 내보내기만 |
| X | 최근 7일 검색, 통계 | 텍스트 |
| Instagram | 연결한 내 프로 계정의 최신 게시물 50개 | 공개 HTTPS JPEG 1장 + 캡션 |
| TikTok | 허용된 개별 공개 영상 URL의 메타데이터 | JSON 내보내기만 |

플랫폼별 인증 방식과 제한은 [플랫폼 설정 가이드](docs/platform-setup.md)를 먼저 확인하세요.

## 빠른 시작: 데모 (API 키 불필요)

요구 사항: Windows PowerShell, Python 3.12 이상.

```powershell
git clone https://github.com/acradin/marketing_agent.git
cd marketing_agent
./scripts/start.ps1 -Demo
```

브라우저에서 http://127.0.0.1:8767 을 열고 아래 순서로 눌러보세요.

**Reddit 검색 → 게시물 → 구조 분석 → 패턴·생성 → 검토·발행**

- 검색 키워드는 아무 값이나 괜찮습니다. 생성 화면의 제품·타깃·사실 항목은 모두 입력해야 합니다.
- 작업은 약 3초 주기로 처리됩니다. 결과가 안 보이면 잠시 후 탭을 다시 선택하세요.
- 승인한 초안을 수정·저장하면 승인이 취소되는 것도 확인할 수 있습니다.

데모 모드의 특징:

- 화면 상단에 노란색 DEMO 안내가 표시되는 별도 앱입니다.
- 수집 결과와 AI 응답은 고정된 fixture이고, 지표는 모두 null입니다.
- 외부 발행은 차단되며, 종료하면 데모 DB가 삭제됩니다.
- `Ctrl+C`로 종료합니다.

> 실행 정책 때문에 스크립트가 차단되면, 한 번 설치된 이후에는 `./.venv/Scripts/python.exe -m scripts.demo`로 직접 실행할 수 있습니다.

## 실제 연결로 실행

```powershell
Copy-Item .env.example .env   # 처음 한 번만. 이후 .env에 키를 입력
./scripts/start.ps1
```

- 대시보드: http://127.0.0.1:8765
- API 문서: http://127.0.0.1:8765/docs

`start.ps1`은 `.venv` 가상환경을 만들고 의존성을 설치한 뒤 DB 마이그레이션을 적용하고 서버를 띄웁니다. `.env`를 수정했다면 앱을 재시작하세요.

### 연결 점검

```powershell
./scripts/start.ps1 -Check
```

- 앱과 별도의 PowerShell 창에서 실행합니다. (설치 후에는 `./.venv/Scripts/python.exe -m scripts.check_connections`와 동일)
- 결과는 `docs/live-connections.json`에 저장됩니다. **종료 코드 0은 전체 성공을 뜻하지 않으므로** 항목별 status와 HTTP 코드를 확인하세요.
- 키가 설정되어 있으면 실제 읽기 API와 짧은 LLM 요청을 보내므로 quota·요금이 발생할 수 있습니다. 발행은 하지 않습니다.

### 참고 사항

- 포트 사용 중 오류가 나면 이미 실행 중인 앱을 기존 창에서 `Ctrl+C`로 종료하세요. 같은 DB로 여러 서버를 띄우지 마세요.
- 의존성은 버전 범위로 설치되므로 나중에 설치한 버전이 검증 환경과 다를 수 있습니다.
- UI는 Node.js 없이 동작하도록 순수 HTML/JavaScript로 작성했습니다. (Next.js 전환은 미구현)
- Docker: `docker compose up --build`로 실행할 수 있도록 설정은 제공하지만, Docker 실행은 검증하지 않았습니다.

## 환경 변수

모든 키는 `.env`에만 입력합니다. UI나 소스 코드에 넣지 마세요.

### 공통·LLM

| 변수 | 설명 |
|---|---|
| `VE_LLM_BASE_URL` | OpenAI API 주소. 기본 `https://api.openai.com/v1` |
| `VE_LLM_API_KEY` | **필수.** OpenAI API 키 |
| `VE_LLM_MODEL` | 사용할 모델. 기본 `gpt-4.1-mini` |
| `VE_ALLOW_PUBLIC_URLS` | 허용된 공개 영상 URL의 메타데이터 수집 활성화. 기본 `false` |
| `VE_ENABLE_PUBLISHING` | Reddit·X·Instagram 외부 발행 활성화. 기본 `false` |

> AI 분석·생성 시 원본 게시물 텍스트와 제품 설명이 OpenAI로 전송됩니다. Ollama는 더 이상 필요하지 않습니다.

### Reddit

| 변수 | 설명 |
|---|---|
| `VE_REDDIT_TOKEN` | Reddit API OAuth bearer token. 읽기와 발행 scope는 별개이며, 자동 갱신은 미구현 |
| `VE_REDDIT_USER_AGENT` | 앱 이름과 실제 연락 가능한 계정을 포함한 User-Agent |
| `VE_REDDIT_SUBREDDIT` | 발행할 서브레딧 이름 (`r/` 제외) |

### YouTube

| 변수 | 설명 |
|---|---|
| `VE_YOUTUBE_API_KEY` | YouTube Data API가 활성화된 키 |

### X · Instagram

| 변수 | 설명 |
|---|---|
| `VE_X_BEARER_TOKEN` | X 수집용 |
| `VE_X_API_KEY`, `VE_X_API_SECRET`, `VE_X_ACCESS_TOKEN`, `VE_X_ACCESS_TOKEN_SECRET` | X 발행용 OAuth 1.0a (Read and Write 권한) |
| `VE_X_USER_ID` | 발행 대상 X 계정의 숫자 ID (사용자 이름 아님) |
| `VE_INSTAGRAM_TOKEN` | **Facebook Login** 방식으로 받은 Graph API 토큰 |
| `VE_INSTAGRAM_USER_ID` | Instagram 프로 계정 숫자 ID |
| `VE_INSTAGRAM_API_VERSION` | Graph API 버전. 기본 `v24.0` |

X·Instagram의 권한 요구 사항과 제약은 [플랫폼 설정 가이드](docs/platform-setup.md)에 자세히 정리되어 있습니다.

## 사용 흐름

1. **발견**: Reddit/YouTube 키워드를 검색하거나, 허용된 개별 TikTok/YouTube URL을 수집합니다.
2. **작업 기록**: 실제 성공·실패를 확인합니다. "설정됨" 표시는 연결 성공을 뜻하지 않습니다.
3. **게시물**: 원본 URL, 게시·수집 시각, 관측 스냅샷, 비교 표본을 확인합니다.
4. **구조 분석**: 모델 가설과 근거 게시물에 연결된 패턴을 생성합니다.
5. **패턴·생성**: 제품의 확인된 사실과 타깃 고객을 입력해 초안을 만듭니다.
6. **검토**: 초안을 수정·저장하고 승인합니다. 수정하면 기존 승인은 무효화됩니다.
7. **발행**: 발행이 활성화된 Reddit·X·Instagram 대상에 한해 발행 버튼을 직접 눌러 게시합니다.
8. **실험 결과**: 지표를 재수집해 초안 → 패턴 → 원본 게시물로 이어지는 성과를 추적합니다.

**안전 장치**

- 어떤 게시물도 자동으로 승인하거나 발행하지 않습니다.
- 모델 응답은 구조 검증과 원문 유사성 검사를 통과해야 초안으로 저장됩니다. 유사성 검사가 표절을 완전히 걸러내지는 못하므로 사람의 검토가 필요합니다.

## 데이터와 작업 처리

**저장**

- SQLite(WAL) + SQLAlchemy, Alembic으로 마이그레이션합니다.
- 플랫폼 게시물 ID로 중복을 제거하고, 관측 시각·출처별 스냅샷을 저장합니다.
- 관측할 수 없는 수치는 null로 둡니다. (예: Reddit score를 likes로 변환하지 않음)

**작업 큐**

- 첫 수집 후 1·6·24·72시간 뒤에 후속 관측 작업을 예약합니다. 이는 게시 후 경과 시간이 아니라 수집 기준입니다.
- 재시도 3회, 지수 backoff, 10분 lease, 재시작 시 만료된 lease 복구를 지원합니다. 단일 API 프로세스 운영을 전제로 합니다.
- 정기 검색은 발견 탭에서 예약·중단합니다. API는 `POST /api/schedules`, `DELETE /api/schedules/{id}`이며 최소 간격은 60분입니다.

**발행 안정성**

- 네트워크 발행 전에 intent를 먼저 기록해, 응답이 불확실하거나 프로세스가 중단되어도 중복 발행되지 않도록 합니다.
- 상태가 `publishing` 또는 `publication_unknown`이면 실제 계정에서 게시 여부를 먼저 확인하세요. 자동 재시도나 수동 복구(reconcile) API는 없습니다.

**피드백**

- `/api/feedback/learning`에서 관측 기반 추천을 확인합니다. 비교 가능한 발행 실험이 5개 미만이면 `insufficient_baseline`을 반환합니다.
- 가중치 자동 최적화나 인과 추론은 하지 않습니다.

**API 보호**

- 상태를 변경하는 API를 직접 호출할 때는 `X-Viral-Local: 1` 헤더가 필요합니다. 외부 공개 배포용 인증 시스템은 아닙니다.

## 순위 해석

- 같은 플랫폼·형식·관측 출처·지표 집합·게시 후 나이 구간·계정 규모 구간끼리만 비교합니다.
- 비교 표본이 5개 미만이면 점수를 만들지 않습니다.
- 계정 규모를 알 수 없으면 `partial_baseline`과 경고를 반환합니다.
- ER 계산에 필요한 지표가 일부 없으면 "부분 ER"로 구분합니다.
- 값이 감소한 카운터는 성장 속도 계산에 쓰지 않습니다.
- 여러 플랫폼의 점수를 하나로 합치지 않습니다.

**알려진 한계**

- 작성자 기준 중앙값은 이미 저장된 데이터 범위 안에서만 계산됩니다. 작성자의 최근 게시물을 자동 수집해 baseline을 넓히는 기능은 미구현입니다.
- 검색은 플랫폼별 최대 50개, 1페이지만 가져오며 전체 결과를 보장하지 않습니다.
- YouTube 영상 검색은 Shorts 여부를 판별하지 않습니다.

## 테스트

```powershell
./.venv/Scripts/python.exe -m pytest -q
```

테스트의 가짜 수집기·LLM·발행 응답은 테스트 DB에서만 쓰이며, 실제 시장 성과를 의미하지 않습니다.

## 미구현 범위

**검증 필요** (사용자 API 권한·계정 연결 후)

- 실제 2개 플랫폼 수집
- 실제 LLM 분석·생성
- 승인된 실제 게시와 후속 실측

**미구현**

- TikTok 키워드 탐색, TikTok Direct Post
- Instagram 전체 공개 탐색, 동영상·Reels·캐러셀 발행
- X 미디어·스레드 발행
- 국내 커뮤니티 수집
- Postiz/Hermes 통합
- 영상 전사·프레임 분석
- 패턴 병합·클러스터링
- 토큰 자동 갱신
- Next.js UI

## 관련 문서

| 문서 | 내용 |
|---|---|
| [docs/platform-setup.md](docs/platform-setup.md) | X·Instagram 등 플랫폼별 설정과 제한 |
| [docs/specification.md](docs/specification.md) | 5.5 이후 보완 명세와 단계별 인수 조건 |
| [docs/verification.md](docs/verification.md) | 검증 결과와 남은 범위 |
| [docs/integrations.md](docs/integrations.md) | 오픈소스 평가와 확인 범위 |
