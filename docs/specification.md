# Viral Engine 개발 명세 보완안 v0.2

2026-10-24 · 상태: 로컬 초기 구현 + 외부 연결 대기. 원래 v0.1의 1~5.4 원칙을 유지하고, 전달된 5.5 이후의 누락 범위를 정의한다. 이 문서는 전체 구현 완료 선언이 아니다.

## 범위와 단계

첫 검증 플랫폼은 기존 구현이 있는 Reddit + YouTube로 제안한다. 원래 P0인 TikTok을 삭제하지 않되, TikTok 키워드 탐색은 다음 단계로 남긴다. YouTube 검색 결과를 Shorts라고 단정하지 않는다.

| 단계 | 산출물 | 통과 조건 | 현재 상태 |
|---|---|---|---|
| 로컬 흐름 | 수집 작업→DB→분석→초안→승인 | 격리 fixture로 화면/API/DB 연결 확인 | 구현, 자동 검증 |
| 실제 읽기 | Reddit·YouTube 원본과 반복 스냅샷 | 플랫폼별 실제 게시물 1개 이상, URL/출처/UTC 시각, 후속 관측 | 키 미설정 |
| 실제 AI | 분석 가설과 독창적 초안 | 실제 모델 응답의 스키마 검증, 근거 연결 | 모델 미설정 |
| 승인 발행 | 승인한 Reddit 게시물과 영수증 | 사용자 승인 내용·대상 일치, 중복 발행 없음 | 실제 발행 미검증 |
| 측정 | 발행 후 스냅샷과 관측 비교 | 1/6/24/72시간 목표 작업과 실제 관측 시각 기록 | 실제 시장 데이터 없음 |

## 5.5 Content Generation Engine

입력: `pattern_id`, `platform`, `product`, `audience`, 확인 가능한 `facts`, `language`, `destination`. 제품/타깃/사실은 필수이며 원본의 주장이나 지표를 새 제품의 사실로 이전하지 않는다.

출력: 제목 1~300자, 본문 20~20,000자, 패턴 참조, 입력 brief, 버전, 상태. 현재 플랫폼별 글자 수·영상 규격 검사는 별도 미구현이며 발행 전 사람 검토가 필요하다. 영상 생성 기능은 포함하지 않는다.

모델 입력은 신뢰할 수 없는 자료로 취급한다. JSON 구조 검증 실패나 원문 유사성 제한 초과는 초안 저장 실패로 처리한다. 현재 연속 80자 이상 일치 또는 전체 유사도 0.75 초과를 차단하지만 표절·의미상 복제를 완전히 검출하지 못한다. 여러 변형 자동 비교와 프롬프트 버전 저장은 후속 요구사항이다.

## 5.6 Review / Publish

상태: `review → approved → publishing → published`. 제목·본문·대상 수정 시 버전 증가 및 `review` 복귀. 승인에는 내용·플랫폼·대상·버전의 hash를 저장하고 발행 직전에 재검사한다.

실제 지원 발행은 Reddit 텍스트 게시뿐이다. `VE_ENABLE_PUBLISHING=true`, 유효한 OAuth 권한, 설정한 subreddit과 초안 대상 일치, 현재 저장본 승인, 별도 발행 클릭을 모두 요구한다. 진단 및 데모는 게시하지 않는다.

네트워크 호출 전 발행 intent를 DB에 확정한다. 응답이 불확실하면 `publication_unknown`, 프로세스 중단으로 `publishing`에 남아도 재발행을 차단한다. 사용자는 계정에서 실제 게시 여부를 확인해야 한다. 수동 reconciliation UI/API는 후속 구현이며 DB를 임의 수정해 재시도하지 않는다. 승인되지 않은 자동 발행·예약 발행은 범위 밖이다.

## 5.7 Measure / Learn

발행 receipt는 원격 ID/URL만 증명하며 반응 지표는 모두 null이다. 첫 실제 관측을 즉시 예약하고 첫 수집 기준 1/6/24/72시간 후 관측을 예약한다. 앱이 꺼져 있으면 재시작 후 지연 실행하며 목표 시각을 관측 시각으로 기록하지 않는다.

동일 플랫폼·콘텐츠 형식·지표 출처/집합·게시 후 나이·계정 규모의 비교 집단을 사용한다. 비교 표본 5개 미만은 점수 없음, 계정 규모 미상은 불완전 baseline으로 표시한다. 실험 5개 미만은 학습 추천에서 `insufficient_baseline`이다. 이는 통계적 유의성 기준이 아니다. 계정 선택 편향, 주제·시간·유료 홍보 영향이 있어 인과 효과나 바이럴 성공 확률을 주장하지 않는다.

## 6. 데이터 계약

| 엔터티 | 식별과 근거 | 보존 규칙 |
|---|---|---|
| Post | 플랫폼 + 원격 ID, canonical URL | 같은 게시물 재수집 시 중복 생성 금지 |
| Snapshot | 게시물 + observed_at + source | 누적 관측, 결측 null, 단위/정의 보존 |
| Analysis / Pattern | 모델, 분석 JSON, 근거 게시물 ID | confidence는 가설 평가, 실제 성과와 분리 |
| Draft | brief, pattern_id, version, 승인 hash | 수정 시 재승인 |
| Job / Event | dedupe_key, 시도 횟수, lease, 실행 기록 | 완료 효과 중복 적용 방지 |

현재 SQLite WAL + SQLAlchemy + Alembic, 단일 API 프로세스가 기준이다. 테스트 및 데모는 임시 DB를 사용한다. 데모 지표는 null이고 source는 `demo_fixture`다. prompt version, 원본 응답 아카이브, 데이터 내보내기/삭제 UI, 보존기간 정책 자동화는 미구현이다.

## 7. 실행·복구 계약

작업은 `queued → running → succeeded` 또는 재시도 후 `failed`. 현재 총 3회 시도, 재시도 대기 60초·120초, 10분 lease. 시작된 작업은 재시작 후 lease 만료 시 복구한다. 주기 검색 최소 간격 60분, 현재 검색 최대 50개 한 페이지. 장시간 heartbeat, 공급자별 Retry-After 처리와 오류별 재시도 분류는 후속 구현이다.

외부 호출 예외 전문에 키가 포함될 수 있으므로 작업 기록과 진단에는 예외 종류/HTTP 상태만 남긴다. 공급자 장애는 가짜 데이터로 대체하지 않는다. 연결 진단은 DB에 글을 저장하지 않으므로 연결 테스트 성공과 실제 DB 수집 성공을 별도로 판단한다.

Windows Python 3.12+, 127.0.0.1 바인딩, API 프로세스 하나를 사용한다. 브라우저 쓰기 요청은 동일 origin 및 `X-Viral-Local: 1` 필요. 다중 사용자 인증이나 외부 공개 배포는 제공하지 않는다. 원격 LLM 선택 시 입력 본문·brief가 해당 서버로 전달된다.

백업은 앱 종료 후 `data` 폴더 전체와 별도로 안전하게 보관한 설정을 복사한다. 실행 중 SQLite 파일 하나만 복사하지 않는다. 복구는 앱 중지 후 기존 DB를 별도로 보관하고 백업을 복원한다. 복구 절차의 실제 실행 검증은 아직 하지 않았다.

## 8. API / 화면 계약

현재 API의 정확한 요청 스키마는 로컬 `/docs`와 `/openapi.json`을 기준으로 한다. 화면은 발견 / 게시물 / 패턴·생성 / 검토·발행 / 실험 결과 / 작업 기록이다.

| 기능 | 경로 | 성공 확인 |
|---|---|---|
| 연결 설정 상태 | GET /api/status | configured는 인증 성공이 아님 |
| 키워드/URL 수집 | POST /api/discover, /api/collect-url | job_id 반환 후 작업 succeeded 및 posts 확인 |
| 관측/분석 | POST /api/posts/{id}/observe, /analyze | Snapshot / Analysis 생성 |
| 초안 | POST /api/generate | review 상태 초안 |
| 수정/승인/발행 | PUT /api/drafts/{id}, POST .../approve, .../publish | 버전/hash 검증, remote URL |
| 반복 검색 | POST /api/schedules, DELETE .../{id} | 예약 생성/비활성화 |
| 결과/추천 | GET /api/feedback/results, /learning | 패턴→발행 글→관측 연결 |

## 9. 연결 인수 절차

1. 데모에서 검색→게시물→분석→패턴→생성→승인→수정 후 승인 해제를 확인한다. 실데이터 증거로 계산하지 않는다.
2. `.env`에 본인 API 키/토큰과 모델을 직접 입력하고 앱을 재시작한다. 비밀값을 채팅에 붙이지 않는다.
3. 진단 실행 후 `configuration_missing`, 연결 오류, HTTP 인증/권한 거부를 해결한다. HTTP 응답 수신만으로 수집 성공이라 판정하지 않는다.
4. 실제 화면에서 Reddit·YouTube 검색 후 플랫폼별 1개 이상 게시물과 실제 원본 URL, 실제 지표 또는 null, 관측 출처/시각을 확인한다. 재관측으로 동일 Post에 별도 Snapshot이 추가되는지 확인한다.
5. 실제 모델 분석/생성 후 원본과 주장·표현·대상을 검토한다. 키는 유효해도 모델 미설치·JSON 지원 불일치로 실패할 수 있다.
6. 본인이 승인한 Reddit 테스트 게시물 1개만 발행하고 계정의 원격 URL을 확인한다. 실패·불확실 시 재클릭하지 않는다.
7. 후속 관측이 쌓이면 실험 결과를 확인한다. 장기간 관측 완료 전에는 전체 루프 완료를 선언하지 않는다.

## 10. 확인한 공식 계약


오픈소스 채택 경계는 [기존 통합 조사](integrations.md), 실제 이번 실행 결과는 [검증 기록](verification.md)을 함께 확인한다.

AI provider: OpenAI Chat Completions, default model `gpt-4.1-mini`. Requires `VE_LLM_API_KEY`. Reference: https://developers.openai.com/api/docs/models/gpt-4.1-mini


## 2026-10-24 추가 구현

X(Tweepy) 검색·텍스트 발행, Instagram(HTTPX/Graph API) 내 계정 캡션 검색·JPEG 발행, 다중 플랫폼 초안과 JSON 내보내기를 구현했습니다. [상세 지원 범위와 인증](platform-setup.md)이 이 추가분의 기준입니다. 실제 연결은 인증 정보 입력 후 검증해야 합니다. TikTok Direct Post와 영상 제작은 미구현입니다.
