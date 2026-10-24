# 오픈소스 통합 평가

확인일: 2026-10-24. 공개 README, 라이선스, 패키지 정의 및 일부 실행 코드를 직접 열어 확인했습니다. GitHub metadata API 호출은 HTTP 오류로 실패해 저장소의 최신 push 시각과 전체 유지보수 상태는 확인하지 못했습니다. 설치·실행을 검증하지 않은 프로젝트를 동작한다고 표시하지 않습니다. 원본 파일 수집 결과는 `upstream-audit.json`에 있습니다.

| 프로젝트 | 확인한 자료와 판단 | 채택 상태 |
|---|---|---|
| [Hermes](https://github.com/NousResearch/hermes-agent) | README, pyproject, MIT 라이선스, cron/scheduler.py 확인. scheduler가 내부 세션·설정·런타임에 깊이 연결됨. 현재 pyproject 설명은 3.14 운영을 전제하며 현재 Python 3.12 MVP와 직접 결합할 근거 부족. LLM 비용은 선택 공급자에 따름. | 설치·실행 미검증, 독립 작업 인터페이스 유지 |
| [Jev Social](https://github.com/socai-io/jev-social) | README·package.json·MIT 확인. Node 22+, socai CLI, 실제 로그인 Chrome에 의존. Instagram/TikTok/LinkedIn 읽기 조사, 기본 TypeSafe Jev/OpenRouter 경로. 접근 가능한 UI에 한정되며 모든 성과 필드를 보장하지 않음. | Node·계정·공급자 연결 미검증, 보류 |
| [socialfetch](https://github.com/edgeaig/socialfetch) | README·라이선스 확인. CLI/MCP/HTTP 인터페이스. TikTok oEmbed는 제목·작성자 중심이므로 본 MVP의 반복 성과 관측을 대체하지 못함. 라이선스 문구는 원본 파일에 보관, 전체 구현 분석 미완료. | 미채택, 실행 미검증 |
| [yt-dlp](https://github.com/yt-dlp/yt-dlp) | 공개 README 및 설치 패키지 확인 대상. Python metadata extraction을 어댑터 뒤에 배치. URL별 공개 접근 가능 여부에 종속. 미디어 다운로드·로그인·쿠키 주입 없음. upstream의 기본 branch는 master이므로 main 원본 수집 실패는 프로젝트 부재를 뜻하지 않음. | 선택형 URL metadata backend, 실플랫폼 추출 성공 미검증 |
| [TrendRadar](https://github.com/yassmin1/TrendRadar) | README/main.py 확인. Streamlit, 여러 수집기와 분석 모듈, mock/live 분리. 요청한 LICENSE 경로는 없었으므로 재배포 라이선스 미확인. | 설계 참고만, 코드 복사·의존성 편입 없음 |
| [Postiz](https://github.com/gitroomhq/postiz-app) | README, package.json, AGPL-3.0 LICENSE, posts.controller.ts 확인. 게시 CRUD 및 서비스 분리가 있음. 별도 서버·플랫폼 OAuth 구성 필요, 통합 운영 부담이 있음. | 설치·발행·성과 API 미검증. 내부 Publisher 프로토콜로 교체 가능 |
| [Browser Harness](https://github.com/browser-use/browser-harness) | README, pyproject, MIT 확인. CLI 및 MCP, CDP를 통한 실제 Chrome 연결. 사용자 로그인 상태에 의존하며 플랫폼별 수집 계약 자체는 제공하지 않음. | 설치·브라우저 권한 미검증, 미채택 |

라이선스 이름 확인은 제품 전체의 재배포 검토 완료를 뜻하지 않습니다. 선택하지 않은 저장소의 코드는 앱에 포함하지 않았습니다. research-sources는 확인용 원문 자료이며 실행 모듈이 아닙니다.

추가 확인: Jev의 `src/index.js` export, socialfetch 단일 실행 스크립트, Browser Harness의 `run.py`를 열어 인터페이스를 확인했습니다. 설치한 yt-dlp 2026.10.21의 `extractor/tiktok.py`에서 play/digg/share/comment count 매핑을 확인했습니다. master branch의 LICENSE는 Unlicense 문구이며 설치 패키지의 라이선스/의존성 조건은 별도로 보존해야 합니다. 이 확인은 실제 TikTok 요청 성공을 뜻하지 않습니다.

## 플랫폼 계약

- [Reddit API](https://www.reddit.com/dev/api/): OAuth 검색·게시물 조회·텍스트 submit을 구현했습니다. API 사용 승인, 토큰 scope, 서브레딧 규칙과 호출 제한은 계정에 따라 다릅니다. score는 net score로 보존합니다.
- [YouTube search.list](https://developers.google.com/youtube/v3/docs/search/list), [videos.list](https://developers.google.com/youtube/v3/docs/videos/list): 검색 후 snippet/statistics를 결합합니다. 비공개 지표는 null이며 API key·quota가 필요합니다. 비용·quota는 공급자의 현재 프로젝트 설정을 기준으로 확인해야 합니다.
- [TikTok Research API](https://developers.tiktok.com/doc/research-api-get-started): 승인된 연구 프로젝트가 전제입니다. 일반 마케팅에 사용 가능한 API로 간주하지 않았습니다. 현재 구현은 허용된 개별 공개 영상 URL에 한정하며 탐색·수집 성공을 보장하지 않습니다.

이 실행에서는 외부 게시를 수행하지 않았습니다. SDK·API contract 테스트는 실제 계정 권한 검증을 대체하지 않습니다.


## 추가 채택

Tweepy 4.17.0(MIT)을 설치해 X API v2 수집·발행에 사용합니다. Instagram은 HTTPX로 공식 Facebook Login Graph API를 연결합니다. [설정·제한](platform-setup.md) 및 [테스트 결과](verification.md)를 참고하세요.
