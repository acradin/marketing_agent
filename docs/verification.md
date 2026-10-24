# 2026-10-24 추가 플랫폼 검증

- pytest: 24 passed. X/Instagram 계약·대상 계정 검증·다중 플랫폼 발행 영수증과 후속 관측·이미지 변경 승인 취소·수동 내보내기 포함.
- Playwright Chromium: 수집 → 분석 → 초안 → 승인 → 수정 후 승인 취소, 전체 탭, 모바일 폭, JavaScript 오류 없음 통과. 외부 서비스는 가짜 응답.
- 실제 진단: Reddit/YouTube/X/Instagram/OpenAI 인증 설정 없음으로 건너뜀. OpenAI 네트워크 응답 401, Reddit/YouTube 403은 인증 성공이 아님.
- 실제 발행 시도 없음. X/Instagram의 실제 계정 연결·발행·성과 관측 검증은 남아 있음.
- FastAPI TestClient의 httpx 사용에 관한 deprecation warning 1개가 있으며 테스트는 통과함.
- 결과: [pytest XML](test-results.xml), [브라우저](browser-check.json), [실제 진단](live-connections.json).
- 설정 및 기능 한계: [플랫폼 안내](platform-setup.md).

---

## 이전 검증 기록 (당시 범위)

# 구현 검증 기록

검증일: 2026-10-24 · Windows · Python 3.12.4

## 이번 보완 및 직접 실행 검증

- [보완 명세 v0.2](specification.md): 생성/승인/발행/측정/운영/데이터/API 계약, 미구현 경계, 단계별 인수 절차 추가. Reddit+YouTube 우선 검증은 기존 구현 기준 제안이며 원래 TikTok 목표를 완료 처리하지 않았습니다.
- pytest 재실행: 12 passed, 1 deprecation warning. [XML](test-results.xml)을 다시 열어 실패 0건을 확인했습니다.
- 기존 격리 Chromium 흐름을 재실행해 통과했습니다. [브라우저 결과](browser-check.json)도 다시 열어 확인했습니다.
- 새 대화형 데모(8767): 실제 브라우저에서 검색→임시 SQLite→게시물 표시→고정 분석→고정 생성→승인→수정 후 승인 해제를 확인했습니다. 승인 상태의 발행 API는 HTTP 409로 차단됐고 JavaScript 오류가 없었습니다. 이 흐름은 fixture이며 실제 SNS/LLM 검증이 아닙니다. 첫 확인 시 PowerShell stdin 문자 인코딩으로 locator 검증이 실패했고 UTF-8로 다시 실행해 통과했습니다.
- Clone Browser 패널에서 노란 DEMO 안내와 초기 화면을 열어 확인했습니다. 패널 클릭은 stale ref로 실패했으며, 위 흐름 조작은 별도 Playwright에서 확인했습니다.
- 실제 앱(8765)과 데모(8767)를 이 세션에서 실행해 두었습니다. 프로세스 종료나 컴퓨터 재시작 이후에는 실행 스크립트로 다시 시작해야 합니다. 이번 실행 PID는 각각 22200, 1564입니다. 해당 프로세스가 여전히 Python 서버인지 확인한 뒤 필요하면 `Stop-Process -Id 22200,1564`로 종료할 수 있습니다. PID는 재사용될 수 있습니다.

| 실제 연결 경계 | 결과 | 의미 / 다음 조치 |
|---|---|---|
| 로컬 /api/status | HTTP 200 | 로컬 API 접근 확인 |
| 로컬 Ollama /v1/models | ConnectError | 현재 기본 포트에서 연결되지 않음. 모델 서버 시작 후 모델명 설정 |
| Reddit OAuth endpoint, 무인증 | HTTP 403 | HTTP 응답 수신만 확인, 데이터 수집 실패. 유효한 승인/토큰 필요 |
| YouTube videos endpoint, 무키 | HTTP 403 | HTTP 응답 수신만 확인, 데이터 수집 실패. API 키 필요 |
| 인증된 Reddit/YouTube 수집 | skipped | 설정 없음. 실제 게시물/지표 미검증 |
| 실제 LLM 분석/생성 | 분석 skipped, 생성 미실행 | 모델 설정 없음 |
| 실제 발행/시장 반응 | 미실행 | 승인된 게시와 장시간 관측 필요 |

실측 기록은 [live-connections.json](live-connections.json)에 있습니다. `*_network`의 `passed`는 HTTP 응답 수신을 뜻할 뿐이며, 내부 `http_status: 403`은 접근 거부입니다. 키/예외 전문은 기록하지 않았고 진단은 운영 DB에 데이터를 쓰지 않았습니다. 첫 진단 당시 로컬 앱도 꺼져 있었고, 앱 실행 후 다시 기록한 최종 결과입니다.

사용자 실행: [README](../README.md)의 `start.ps1 -Demo`로 키 없이 화면을 체험하고, 실제 연결은 `.env` 설정 후 일반 실행 및 `-Check`를 사용하세요. 기존 `.env`는 덮어쓰지 않습니다. 대화형 데모의 지표는 null입니다. 현재 실행은 직접 Python 모듈로 확인했으며 새 환경에서 설치를 포함하는 PowerShell 스크립트 전체 재설치는 수행하지 않았습니다.

## 확인된 결과

- pytest: 12개 통과. 스냅샷 중복·결측값, 플랫폼 필드 매핑, 실패 3회 종료와 오류 내 비밀값 비노출, 만료 lease 복구, 승인 취소·버전 충돌, 중복 발행 방지, 불확실한 발행의 재시도 차단, 로컬 쓰기 보호, 가짜 공급자 전체 흐름, 순위 cohort 분리, 완료 작업 재실행 중복 방지, 정기 검색, 실험 부족 상태를 검사했습니다.
- Chromium: 브라우저 폼 → FastAPI → SQLite → 게시물 표시 → 분석 → 패턴 → 초안 → 승인 → 수정 후 승인 취소를 확인했습니다. 외부 응답은 모두 테스트 fixture입니다. 실제 외부 발행은 하지 않았습니다.
- 390px 화면에서 수평 overflow 없음, JavaScript pageerror 없음.
- Alembic `upgrade head` 성공, 로컬 Uvicorn 실행 및 Browser 패널의 초기 대시보드 표시 확인.
- pytest에서 Starlette TestClient의 httpx 사용 deprecation 경고 1건. 테스트 실패는 아니며 다음 의존성 갱신 때 호환성 검토가 필요합니다.

기계 판독 증거: [pytest XML](test-results.xml), [브라우저 결과](browser-check.json).

## 검증하지 못한 경계

Reddit OAuth·YouTube API·LLM endpoint가 설정되지 않아 실제 수집·분석·생성은 미검증입니다. 두 플랫폼 실제 수집, 실제 승인 발행과 1/6/24/72시간 시장 반응은 아직 성공 기준을 충족하지 않았습니다. TikTok URL 추출도 실제 성공을 주장하지 않습니다. Docker 실행은 미검증입니다.

## 명세와의 차이

- 첫 UI는 FastAPI에서 제공하는 HTML/JavaScript입니다. Next.js·TypeScript·Tailwind 미구현.
- Reddit/YouTube 키워드 수집 계약과 선택적 TikTok/YouTube URL 수집을 구현했습니다. TikTok 키워드 discovery는 미구현.
- 텍스트 구조 분석과 생성만 구현. 영상 전사·프레임·vision은 미구현.
- 근거 게시물별 패턴 저장 및 발행 실험 연결은 구현. 패턴 자동 병합·임베딩 클러스터링은 미구현.
- 데이터 기반 다음 실험 추천은 제공하되 인과 효과나 모델 가중치의 자동 학습을 주장하지 않습니다.
- 단일 로컬 API 프로세스를 전제로 합니다. 분산 실행, 장시간 lease heartbeat, 토큰 자동 갱신, 불확실한 발행 수동 reconcile UI는 추가 작업입니다.
- API 검색은 1페이지, 최대 50개로 제한됩니다. 언어·계정·해시태그 전용 필터와 작성자 전체 baseline 수집은 남아 있습니다.

## 데이터 구분

테스트 데이터는 임시 SQLite DB를 사용하고 종료 후 제거합니다. 기본 운영 DB에 샘플 성과를 넣지 않았습니다. `publication_receipt`의 모든 성과는 null이며, 실제 관측 작업이 성공해야 지표가 생깁니다. timestamp는 UTC로 정규화하며 관측 시각을 목표 시각으로 대체하지 않습니다.


## OpenAI migration (2026-10-24)

Default endpoint: https://api.openai.com/v1; model: gpt-4.1-mini. Updated runtime defaults, local .env, template, readiness status, missing-key validation and provider diagnostics. Local .env contains no OpenAI key at verification time. Existing running processes must be restarted.

Validation: pytest -q: 14 passed, 1 Starlette/httpx deprecation warning. Added mock-transport checks for OpenAI URL, bearer authentication, model, JSON request and validated generation response; missing-key test verifies no network request. These are mocked checks, not live OpenAI success. Real collection, generation and publication still require credentials and live verification.
