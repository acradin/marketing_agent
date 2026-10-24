import json
import httpx
import pytest
from packages.core.config import Settings
from packages.intelligence.llm import Intelligence, GeneratedContent


def test_missing_key_fails_before_network(monkeypatch):
    settings = Settings(_env_file=None, llm_api_key="")
    def forbidden(*args, **kwargs):
        pytest.fail("Missing key must not make a network request")
    monkeypatch.setattr(httpx, "Client", forbidden)
    assert not settings.llm_configured
    with pytest.raises(RuntimeError, match="VE_LLM_API_KEY"):
        Intelligence(settings).generate({}, {}, [])


def test_openai_generation_request_and_validation(monkeypatch):
    settings = Settings(_env_file=None, llm_api_key="test-key")
    original_client = httpx.Client
    def respond(request):
        assert str(request.url) == "https://api.openai.com/v1/chat/completions"
        assert request.headers['authorization'] == 'Bearer test-key'
        body = json.loads(request.content)
        assert body['model'] == 'gpt-4.1-mini'
        assert body['response_format'] == {'type': 'json_object'}
        return httpx.Response(200, json={'choices': [{'message': {'content': json.dumps({'title': 'Try a new workflow', 'text': 'Organize one note today using your local workspace.'})}}]})
    monkeypatch.setattr(httpx, 'Client', lambda **kwargs: original_client(transport=httpx.MockTransport(respond), **kwargs))
    assert isinstance(Intelligence(settings).generate({'product': 'notes'}, {}, []), GeneratedContent)
