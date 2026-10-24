from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from apps.api.main import create_app
from packages.core.config import Settings
from packages.core.models import Post, Snapshot, Draft, Job, Pattern, Analysis, Event, now
from packages.core.service import persist, enqueue
from packages.collectors.base import Observation
from packages.collectors.adapters import Reddit, YouTube
from packages.analytics.ranking import rank
from packages.publishing.base import approval_hash
from packages.intelligence.llm import PatternAnalysis, GeneratedContent


@pytest.fixture
def client(tmp_path):
    settings = Settings(_env_file=None, database_url="sqlite:///" + str(tmp_path / "test.db"), llm_model="test-model", enable_publishing=True, reddit_token="test-token", reddit_subreddit="example")
    app = create_app(settings, scheduling=False)
    with TestClient(app, headers={"X-Viral-Local": "1"}) as c:
        yield c


def observation(**overrides):
    return Observation(**{"platform": "reddit", "platform_post_id": "abc", "canonical_url": "https://www.reddit.com/r/test/comments/abc/test/", "text": "A useful source text with observations and a specific story.", "published_at": datetime.now(timezone.utc) - timedelta(hours=2), "source": "reddit_oauth", "metrics": {"comments": 12, "score": 40}, **overrides})


def seed(client):
    service = client.app.state.service
    with service.sessions.begin() as s:
        post = persist(s, observation())
        return post.id


def test_snapshot_dedupe_preserves_missing_metrics(client):
    o = observation()
    with client.app.state.sessions.begin() as s:
        persist(s, o)
        persist(s, o)
        persist(s, o.model_copy(update={"observed_at": o.observed_at + timedelta(hours=1)}))
    posts = client.get('/api/posts').json()
    assert len(posts) == 1
    assert len(posts[0]['snapshots']) == 2
    assert posts[0]['snapshots'][0]['metrics']['likes'] is None
    assert posts[0]['ranking']['engagement_rate'] is None
    assert posts[0]['ranking']['status'] == 'insufficient_baseline'


def test_provider_mappings():
    r = Reddit.parse({"id": "a", "permalink": "/r/a/comments/a/", "score": -2, "num_comments": 3, "created_utc": 100})
    assert r.metrics.get('likes') is None and r.metrics['score'] == -2
    y = YouTube.parse({"id": "x", "snippet": {"title": "title", "publishedAt": "2026-01-01T00:00:00Z"}, "statistics": {"viewCount": "20"}})
    assert y.metrics['views'] == 20 and y.metrics['likes'] is None


def test_job_deduplication_retry_and_secret_redaction(client):
    sessions = client.app.state.sessions
    with sessions.begin() as s:
        a = enqueue(s, 'discover', {}, 'same')
        b = enqueue(s, 'discover', {}, 'same')
        assert a.id == b.id
        job_id = a.id
    def fail(*_):
        raise RuntimeError('https://api.test/?key=secret')
    client.app.state.service.execute = fail
    for _ in range(3):
        with sessions.begin() as s:
            s.get(Job, job_id).run_at = now()
        client.app.state.worker.tick()
    with sessions() as s:
        j = s.get(Job, job_id)
        assert j.state == 'failed' and j.attempts == 3
        assert 'secret' not in j.error
        assert len(s.scalars(select(Event)).all()) == 6


def test_expired_lease_recovers(client):
    with client.app.state.sessions.begin() as s:
        j = enqueue(s, 'discover', {}, 'expired')
        j.state, j.attempts = 'running', 1
        j.lease_until = '2000-01-01T00:00:00+00:00'
        job_id = j.id
    client.app.state.service.execute = lambda *_: {'count': 0}
    client.app.state.worker.tick()
    with client.app.state.sessions() as s:
        assert s.get(Job, job_id).state == 'succeeded'
        assert s.get(Job, job_id).attempts == 2


def create_draft(client):
    post_id = seed(client)
    with client.app.state.sessions.begin() as s:
        a = Analysis(post_id=post_id, model='test', result={'hypotheses': []})
        s.add(a); s.flush()
        p = Pattern(analysis_id=a.id, platform='reddit', content_type='text', name='question', structure=['question', 'evidence'], example_post_ids=[post_id])
        s.add(p); s.flush()
        d = Draft(pattern_id=p.id, platform='reddit', brief={'product': 'demo'}, title='Original draft', text='Original content to approve.', destination='example')
        s.add(d); s.flush()
        return d.id


def test_approval_edit_and_double_publish(client):
    draft_id = create_draft(client)
    assert client.post(f'/api/drafts/{draft_id}/publish').status_code == 409
    assert client.post(f'/api/drafts/{draft_id}/approve', json={'version': 1}).status_code == 200
    edit = client.put(f'/api/drafts/{draft_id}', json={'title':'Changed','text':'Changed original content.','destination':'example','version':1})
    assert edit.json()['state'] == 'review' and edit.json()['approved_hash'] is None
    assert client.post(f'/api/drafts/{draft_id}/approve', json={'version': 1}).status_code == 409
    assert client.post(f'/api/drafts/{draft_id}/approve', json={'version': 2}).status_code == 200
    calls = []
    def publish(draft):
        calls.append(draft.id)
        return 'new123', 'https://www.reddit.com/r/example/comments/new123/test/'
    client.app.state.service.publisher.publish = publish
    assert client.post(f'/api/drafts/{draft_id}/publish').status_code == 200
    assert client.post(f'/api/drafts/{draft_id}/publish').status_code == 200
    assert calls == [draft_id]
    feedback = client.get('/api/feedback/results').json()
    assert feedback[0]['pattern_id'] and feedback[0]['post_id']
    assert len(client.get('/api/jobs').json()) == 5


def test_unknown_publication_never_retried(client):
    draft_id = create_draft(client)
    client.post(f'/api/drafts/{draft_id}/approve', json={'version': 1})
    calls=[]
    def timeout(draft):
        calls.append(draft.id)
        raise TimeoutError('unknown')
    client.app.state.service.publisher.publish = timeout
    assert client.post(f'/api/drafts/{draft_id}/publish').status_code == 502
    assert client.post(f'/api/drafts/{draft_id}/publish').status_code == 409
    assert len(calls) == 1
    assert client.get('/api/drafts').json()[0]['state'] == 'publication_unknown'


def test_local_write_protection(client):
    assert client.post('/api/discover', headers={'Origin':'https://evil.example'}, json={'platform':'reddit','query':'test'}).status_code == 403
    assert client.get('/api/status', headers={'Host':'evil.example'}).status_code == 403
    assert client.post('/api/discover', json={'platform':'tiktok','query':'test'}).status_code == 422


def test_end_to_end_mock_providers(client):
    service = client.app.state.service
    service.collectors['reddit'].discover = lambda *_: [observation()]
    client.post('/api/discover', json={'platform':'reddit','query':'coding'})
    client.app.state.worker.tick()
    post_id = client.get('/api/posts').json()[0]['id']
    service.intelligence.analyze = lambda _: PatternAnalysis(hook_type='question', opening_sentence='Question', main_topic='coding', narrative=['problem','example'], emotions=['curiosity'], curiosity_gap='answer', value_proposition='save time', cta='try', tone='clear', target_audience='developers', hypotheses=[{'factor':'hook','explanation':'May invite attention','confidence':.4}])
    client.post(f'/api/posts/{post_id}/analyze')
    client.app.state.worker.tick()
    pattern = client.get('/api/patterns').json()[0]
    service.intelligence.generate = lambda *_: GeneratedContent(title='A practical experiment',text='Try this original workflow with a concrete example from your project.')
    client.post('/api/generate',json={'pattern_id':pattern['id'],'platform':'reddit','product':'tool','audience':'developers','facts':'local first','destination':'example'})
    client.app.state.worker.tick()
    draft = client.get('/api/drafts').json()[0]
    assert draft['state'] == 'review'
    assert client.get('/api/analyses').json()[0]['result']['interpretation'] == 'hypotheses_only'


def test_ranking_separates_age_platform_and_counter_reset():
    post = SimpleNamespace(id='target', platform='youtube', content_type='video', published_at='2026-01-01T00:00:00+00:00', author_id='author', paid_promotion=None)
    def snap(comments,hour):
        return SimpleNamespace(metrics={'likes':10,'comments':comments,'views':100,'author_followers':100},observed_at=f'2026-01-01T{hour:02}:00:00+00:00',source='api')
    peers=[(SimpleNamespace(**{**vars(post),'id':str(i)}), snap(i,2)) for i in range(6)]
    result=rank(post,[snap(20,1),snap(10,2)],peers)
    assert result['sample_size']==6 and result['relative_performance'] is not None
    assert result['growth_per_hour'] is None
    assert 'counter_decreased_or_collection_error' in result['warnings']
    assert result['engagement_rate'] is None and result['partial_engagement_rate']==.2
    peers[0][0].platform='reddit'
    assert rank(post,[snap(10,2)],peers)['sample_size']==5


def test_committed_job_replay_is_idempotent(client):
    calls=[]
    service=client.app.state.service
    def discover(*_):
        calls.append(1)
        return [observation()]
    service.collectors['reddit'].discover=discover
    payload={'platform':'reddit','query':'test'}
    first=service.execute('discover',payload,'replay-job')
    second=service.execute('discover',payload,'replay-job')
    assert first == second and len(calls) == 1
    assert len(client.get('/api/posts').json()[0]['snapshots']) == 1


def test_schedule_survives_and_can_be_disabled(client):
    response=client.post('/api/schedules',json={'platform':'reddit','query':'test','interval_minutes':60})
    assert response.status_code == 200
    schedule_id=response.json()['id']
    client.app.state.service.collectors['reddit'].discover=lambda *_: []
    client.app.state.worker.tick()
    assert len(client.get('/api/jobs').json()) == 1
    client.app.state.worker.tick()
    assert len(client.get('/api/jobs').json()) == 1
    assert client.delete('/api/schedules/'+schedule_id).json()['enabled'] is False


def test_learning_never_invents_experiments(client):
    create_draft(client)
    row=client.get('/api/feedback/learning').json()[0]
    assert row['status']=='insufficient_baseline'
    assert row['median_engagement_percentile'] is None
    assert row['measured_experiments']==0 and row['generated_variants']==1
