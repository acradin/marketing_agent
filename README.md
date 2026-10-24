# Viral Engine 0.1.0

**추가 구현:** X 검색·텍스트 발행(Tweepy), Instagram 내 계정 수집·단일 이미지 발행, 다중 플랫폼 초안·JSON 내보내기. [플랫폼별 설정과 제한](docs/platform-setup.md)을 먼저 확인하세요.

```powershell
git clone https://github.com/acradin/marketing_agent.git
cd marketing_agent
./scripts/start.ps1 -Demo
```


로컬에서 실행하는 콘텐츠 실험 엔진의 첫 구현입니다. 외부 서비스 연결 전에도 UI와 데이터 계층을 실행할 수 있습니다. **아직 명세 전체의 완료나 실제 2개 플랫폼 수집 성공을 의미하지 않습니다.**

## 직접 체험하기 (API 키 불필요)

```powershell
./scripts/start.ps1 -Demo
```

http://127.0.0.1:8767 에서 **Reddit 검색 → 게시물 → 구조 분석 → 패턴·생성 → 검토·발행**을 눌러보세요. 검색 키워드는 아무 값이나 가능하며 생성 화면의 제품·타깃·사실은 모두 입력하세요. 작업은 약 3초 주기로 실행하므로 잠시 후 탭을 다시 선택하세요. 승인 후 본문을 수정·저장하면 승인이 취소되는 것을 확인할 수 있습니다.

노란 DEMO 안내가 있는 별도 앱입니다. 수집·AI 응답은 고정 fixture이며 지표는 null입니다. 외부 발행은 차단되고 종료하면 데모 DB가 삭제됩니다. Ctrl+C로 종료합니다. 실행 정책으로 스크립트가 차단되면 이미 설치된 환경에서 `./.venv/Scripts/python.exe -m scripts.demo`를 실행하세요.

## 실제 연결 실행

Windows PowerShell에서 이 폴더를 열고 실행하세요.

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
./scripts/start.ps1
```

대시보드: http://127.0.0.1:8765 · API 문서: http://127.0.0.1:8765/docs

`.env`를 수정한 뒤 앱을 재시작하세요. 별도 PowerShell 창에서 `./scripts/start.ps1 -Check`로 연결을 점검할 수 있습니다. 이미 설치했다면 `./.venv/Scripts/python.exe -m scripts.check_connections`도 같습니다. 결과는 `docs/live-connections.json`에 저장합니다. 키가 설정된 경우 실제 읽기 API와 짧은 LLM 분석 요청을 보내므로 공급자 quota/요금이 적용될 수 있습니다. 발행은 하지 않습니다. JSON의 개별 status와 HTTP 코드를 확인하세요. 스크립트 종료 코드 0은 전체 연결 성공을 뜻하지 않습니다.

포트 사용 중 오류가 나면 이미 열린 앱을 확인하고 기존 실행 창에서 Ctrl+C로 종료하세요. 같은 DB에 여러 서버를 실행하지 마세요. 자동 설치 의존성은 버전 범위 기반이므로 향후 설치 버전이 기존 검증 환경과 달라질 수 있습니다.

Python 3.12 이상이 필요합니다. 가상환경에만 의존성을 설치합니다. Node.js 없이 실행하도록 첫 UI는 HTML/JavaScript로 구현했습니다. 권장 스택의 Next.js/TypeScript/Tailwind 전환은 남아 있습니다.

Docker가 설치되어 있으면 `docker compose up --build`로 실행할 수 있습니다. 컨테이너 설정은 제공하지만 이 환경에서 Docker 실행은 검증하지 않았습니다.

## 연결 설정

`.env`에 직접 입력하세요. 키는 UI나 소스에 넣지 않습니다.

| 설정 | 용도 |
|---|---|
| `VE_REDDIT_TOKEN` | Reddit API 접근 권한을 가진 OAuth bearer token. 읽기와 발행 scope는 별개입니다. 자동 갱신은 미구현입니다. |
| `VE_REDDIT_USER_AGENT` | 앱 이름과 실제 연락 가능한 계정을 포함한 User-Agent |
| `VE_YOUTUBE_API_KEY` | YouTube Data API가 활성화된 키 |
| `VE_LLM_BASE_URL` | OpenAI API: `https://api.openai.com/v1` |
| `VE_LLM_MODEL` | Default: `gpt-4.1-mini` |
| `VE_LLM_API_KEY` | Required: your OpenAI API key |
| `VE_ALLOW_PUBLIC_URLS` | 허용된 공개 영상 URL의 메타데이터 수집을 명시적으로 활성화 |
| `VE_ENABLE_PUBLISHING` | Reddit·X·Instagram 외부 발행 활성화. 기본 false |
| `VE_REDDIT_SUBREDDIT` | 발행할 서브레딧 이름, `r/` 제외 |

AI analysis and generation send source text and product briefs to OpenAI. Ollama is no longer required.

## 사용 흐름

1. 발견에서 Reddit/YouTube 키워드를 검색하거나 허용된 개별 TikTok/YouTube URL을 수집합니다.
2. 작업 기록에서 실제 성공 또는 실패를 확인합니다. 설정됨 표시는 연결 성공을 뜻하지 않습니다.
3. 게시물에서 원본 URL, 게시·수집 시각, 실제 관측 스냅샷, 비교 표본을 확인합니다.
4. 구조 분석을 실행하면 모델 가설과 근거 게시물에 연결된 패턴이 생성됩니다.
5. 패턴·생성에서 제품의 확인된 사실과 타깃 고객을 입력합니다.
6. 초안을 수정·저장하고 승인합니다. 수정은 기존 승인을 무효화합니다.
7. 활성화된 Reddit·X·Instagram 대상에 한해 별도 발행 버튼을 눌러 게시합니다.
8. 지표 재수집과 실험 결과에서 초안 → 패턴 → 게시물 성과를 추적합니다.

시스템은 어떤 게시물도 자동 승인하거나 자동 발행하지 않습니다. 모델 응답은 구조 검증과 원문 유사성 검사를 통과해야 초안으로 저장됩니다. 유사성 검사는 완전한 표절 검출을 보장하지 않으며 사람의 검토가 필요합니다.

## 데이터와 작업 처리

- SQLite WAL, SQLAlchemy, Alembic 초기 마이그레이션.
- 플랫폼 게시물 ID 기준 중복 제거, 관측 시각·출처별 스냅샷 저장.
- 관측 불가능한 수치는 null. Reddit score는 likes로 변환하지 않습니다.
- 첫 수집 후 1·6·24·72시간에 후속 관측 작업을 예약합니다. 정확한 게시 후 경과 시점이라고 표시하지 않습니다.
- 작업 큐는 재시도 3회, 지수 backoff, 10분 lease, 재시작 후 만료 lease 복구를 제공합니다. 단일 API 프로세스 운영을 전제로 합니다.
- 네트워크 발행 전에 intent를 기록합니다. 응답 불확실·프로세스 중단 시 재발행을 막습니다. `publishing` 또는 `publication_unknown`이면 실제 계정을 먼저 확인해야 합니다. 자동 재시도나 수동 reconcile API는 없습니다.
- 관측 추천은 `/api/feedback/learning`에서 확인합니다. 비교 가능한 발행 실험 5개 미만이면 `insufficient_baseline`을 반환합니다. 가중치 자동 최적화나 인과 추론은 하지 않습니다.
- 정기 검색: 발견 탭에서 현재 검색 조건과 간격을 예약하거나 중단합니다. API는 `POST /api/schedules`, `DELETE /api/schedules/{id}`이며 간격은 최소 60분입니다.
- 직접 API를 변경 호출할 때 `X-Viral-Local: 1` 헤더가 필요합니다. 외부 공개 배포용 인증 시스템은 아닙니다.

## 순위 해석

같은 플랫폼·형식·관측 출처·지표 집합·게시 후 나이 구간·계정 규모 구간을 비교합니다. 비교 표본 5개 미만이면 점수를 만들지 않습니다. 계정 규모를 알 수 없으면 `partial_baseline`과 경고를 반환합니다. ER 전체 지표가 없으면 부분 ER로 구분합니다. 감소한 카운터는 성장 속도로 쓰지 않습니다.

같은 작성자의 관측 표본 중앙값은 저장된 데이터 범위에 한정됩니다. 작성자의 모든 최근 게시물을 자동 수집하는 baseline 확장 기능은 미구현입니다. 현재 검색은 플랫폼별 최대 50개 1페이지이며 전체 결과를 보장하지 않습니다. YouTube 영상 검색은 Shorts 판별이 아닙니다. 여러 플랫폼의 점수를 하나로 합치지 않습니다.

## 검증

```powershell
./.venv/Scripts/python.exe -m pytest -q
```

테스트의 가짜 수집기·LLM·발행 응답은 테스트 DB에서만 사용하며 실제 시장 성과가 아닙니다. 검증 결과와 남은 범위는 `docs/verification.md`, 오픈소스 평가 및 확인 범위는 `docs/integrations.md`에서 확인하세요.

## 남은 명세 범위

실제 2개 플랫폼 수집, 실제 LLM 분석·생성, 승인된 실제 게시 및 후속 실측은 사용자 API 권한과 계정 연결 후 검증해야 합니다. TikTok 키워드 탐색, Instagram 전체 공개 탐색·동영상 발행, X 미디어 발행, 국내 커뮤니티, Postiz/Hermes 통합, 영상 전사·프레임 분석, 패턴 병합·클러스터링, Next.js UI는 미구현입니다. 5.5 이후의 보완 명세와 단계별 인수 조건은 [개발 명세 보완안](docs/specification.md)에 있습니다.
