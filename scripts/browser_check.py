"""Isolated end-to-end browser check. All social/LLM responses are fixtures, never live data."""
import json
import tempfile
import threading
import time
from pathlib import Path
import httpx
import uvicorn
from playwright.sync_api import sync_playwright, expect
from apps.api.main import create_app
from packages.core.config import Settings
from packages.collectors.base import Observation
from packages.intelligence.llm import PatternAnalysis, GeneratedContent


def run():
    with tempfile.TemporaryDirectory() as temp:
        app = create_app(Settings(_env_file=None, database_url='sqlite:///' + str(Path(temp) / 'browser.db'), llm_model='fixture-only'), scheduling=False)
        service = app.state.service
        service.collectors['reddit'].discover = lambda *_: [Observation(platform='reddit', platform_post_id='fixture', canonical_url='https://www.reddit.com/r/test/comments/fixture/test/', text='TEST FIXTURE: A concrete example of a useful development workflow.', source='test_fixture', metrics={'comments': 12})]
        service.intelligence.analyze = lambda _: PatternAnalysis(hook_type='test-question', opening_sentence='Test opening', main_topic='workflow', narrative=['problem','example','takeaway'], emotions=['curiosity'], curiosity_gap='answer', value_proposition='learn', cta='try', tone='clear', target_audience='developers', hypotheses=[{'factor':'question','explanation':'Test hypothesis only','confidence':.3}])
        service.intelligence.generate = lambda *_: GeneratedContent(title='TEST FIXTURE draft',text='This is synthetic test content for the browser approval workflow, not a live campaign.')
        server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=8766,log_level='warning'))
        thread=threading.Thread(target=server.run,daemon=True)
        thread.start()
        try:
            for _ in range(100):
                if server.started: break
                time.sleep(.1)
            assert server.started
            errors=[]
            with sync_playwright() as p:
                browser=p.chromium.launch(headless=True)
                page=browser.new_page(viewport={'width':1365,'height':1000})
                page.on('pageerror',lambda error: errors.append(str(error)))
                page.goto('http://127.0.0.1:8766')
                expect(page.get_by_role('heading',name='공개 게시물 검색')).to_be_visible()
                assert page.locator('#platform option[value=x]').count() == 1
                assert page.locator('#platform option[value=instagram]').count() == 1
                page.get_by_label('키워드').fill('fixture coding')
                page.get_by_role('button',name='수집 작업 시작').click()
                expect(page.get_by_role('status')).to_contain_text('작업 등록')
                app.state.worker.tick()
                page.get_by_role('button',name='게시물',exact=True).click()
                expect(page.get_by_text('TEST FIXTURE:',exact=False)).to_be_visible()
                page.get_by_role('button',name='구조 분석',exact=True).click()
                page.wait_for_timeout(300)
                app.state.worker.tick()
                page.get_by_role('button',name='패턴·생성',exact=True).click()
                expect(page.get_by_role('heading',name='test-question')).to_be_visible()
                page.get_by_label('제품',exact=True).fill('Fixture product')
                page.get_by_label('타깃 고객').fill('Developers')
                page.get_by_label('사용 가능한 사실·제품 설명').fill('Local workflow tool; no unverified performance claims.')
                page.get_by_label('발행 플랫폼', exact=True).select_option('instagram')
                page.get_by_label('Instagram 공개 JPEG URL').fill('https://example.com/image.jpg')
                page.get_by_role('button',name='초안 생성').click()
                page.wait_for_timeout(300)
                app.state.worker.tick()
                page.get_by_role('button',name='검토·발행',exact=True).click()
                expect(page.get_by_label('Instagram 공개 JPEG URL')).to_have_value('https://example.com/image.jpg')
                expect(page.get_by_role('link', name='저장본 JSON 내보내기')).to_be_visible()
                expect(page.get_by_label('제목',exact=True)).to_have_value('TEST FIXTURE draft')
                page.get_by_role('button',name='현재 저장본 승인').click()
                expect(page.get_by_role('button',name='승인된 저장본 외부 발행')).to_be_visible()
                page.get_by_label('본문',exact=True).fill('Edited test content which requires fresh approval.')
                page.get_by_role('button',name='수정 저장',exact=True).click()
                expect(page.get_by_text('버전 2',exact=True)).to_be_visible()
                expect(page.get_by_role('button',name='승인된 저장본 외부 발행')).to_have_count(0)
                page.get_by_role('button',name='실험 결과',exact=True).click()
                expect(page.get_by_role('heading',name='실험 결과',exact=True)).to_be_visible()
                page.get_by_role('button',name='작업 기록',exact=True).click()
                expect(page.get_by_role('heading',name='작업 기록',exact=True)).to_be_visible()
                page.set_viewport_size({'width':390,'height':844})
                assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
                browser.close()
            assert not errors, errors
            result={'status':'passed','browser':'Chromium','external_services':'fixture responses only','checks':['discovery UI to API and SQLite','post rendered','analysis to pattern','Instagram selection and image URL persisted to review', 'export link available', 'X and Instagram discovery options','approval enabled publish control','editing revoked approval','all tabs rendered','390px layout no horizontal overflow','no JavaScript errors'],'live_publication':False}
            Path('docs/browser-check.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
            print(json.dumps(result,ensure_ascii=False))
        finally:
            server.should_exit=True
            thread.join(timeout=15)


if __name__ == '__main__':
    run()
