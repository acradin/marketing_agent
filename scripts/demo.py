"""Interactive fixture demo, isolated temporary DB, no external API calls."""
import tempfile
from pathlib import Path
import uvicorn
from fastapi.responses import HTMLResponse
from apps.api.main import create_app
from packages.core.config import Settings
from packages.collectors.base import Observation
from packages.intelligence.llm import PatternAnalysis, GeneratedContent


def run():
    with tempfile.TemporaryDirectory(prefix="viral-demo-") as temp:
        settings = Settings(_env_file=None, database_url="sqlite:///" + str(Path(temp) / "demo.db"),
                            llm_model="DEMO-FIXTURE", reddit_token="", youtube_api_key="",
                            enable_publishing=False, allow_public_urls=False)
        app = create_app(settings)
        service = app.state.service
        def sample(*args):
            return Observation(platform="reddit", platform_post_id="demo-fixture", canonical_url="https://example.com/demo-fixture",
                               text="[DEMO] Small repeatable experiments help organize a content workflow. This is synthetic text.",
                               source="demo_fixture", metrics={})
        for adapter in service.collectors.values():
            adapter.discover = lambda *args: [sample()]
            adapter.observe = sample
        service.intelligence.analyze = lambda _: PatternAnalysis(
            hook_type="DEMO: 작은 실험", opening_sentence="작은 실험부터 시작하세요", main_topic="작업 흐름",
            narrative=["문제", "작은 실험", "관찰"], emotions=["호기심"], curiosity_gap="무엇을 배울까",
            value_proposition="실험 정리", cta="한 가지 시도", tone="담백함", target_audience="제작자",
            hypotheses=[{"factor": "small_steps", "explanation": "데모 가설이며 실제 분석이 아닙니다", "confidence": 0.1}])
        service.intelligence.generate = lambda *_: GeneratedContent(
            title="[DEMO] 작은 실험으로 시작하기", text="[DEMO] 오늘 하나의 아이디어를 기록하고 작은 실험을 계획해보세요. 이 문장은 화면 조작 확인용 고정 응답이며 실제 AI 생성 결과가 아닙니다.")
        # Replace the home route to keep a persistent, visible fixture warning on every tab.
        app.router.routes = [r for r in app.router.routes if getattr(r, "path", None) != "/"]
        @app.get("/", response_class=HTMLResponse)
        def home():
            html = Path("apps/web/index.html").read_text(encoding="utf-8")
            return html.replace("<body>", '<body><div style="padding:16px;background:#fff1a8;color:#171717">DEMO · 고정 가짜 응답 · 실제 수집/AI/발행 없음 · 종료 시 데이터 삭제 · Reddit 검색부터 시작하세요</div>')
        uvicorn.run(app, host="127.0.0.1", port=8767)


if __name__ == "__main__":
    run()
