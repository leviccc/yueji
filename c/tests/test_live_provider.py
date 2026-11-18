import httpx
import json
import pytest

from yueji_qa.config import Settings
from yueji_qa.providers import ChatClient, ProviderError


def test_deepseek_non_thinking_and_sanitized_usage():
    observations = []

    def handler(request):
        payload = json.loads(request.content)
        assert payload["thinking"] == {"type": "disabled"}
        assert payload["max_tokens"] == 2400
        return httpx.Response(200, json={
            "model": "deepseek-version-observed",
            "choices": [{"message": {"content": '{"answer":true}'}}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120,
                      "prompt_cache_hit_tokens": 60, "prompt_cache_miss_tokens": 40,
                      "completion_tokens_details": {"reasoning_tokens": 0}, "secret_field": "do-not-record"},
            "api_key": "do-not-record",
        })
    client = ChatClient("https://api.deepseek.com", "test-key", "deepseek-flash",
                        thinking="disabled", max_output_tokens=2400,
                        transport=httpx.MockTransport(handler), on_response=observations.append)
    assert client.complete_json("JSON", {}) == {"answer": True}
    assert observations[0]["model"] == "deepseek-version-observed"
    assert observations[0]["usage"]["total_tokens"] == 120
    assert "do-not-record" not in json.dumps(observations)
    assert "test-key" not in json.dumps(observations)


def test_billed_usage_recorded_even_if_generated_json_is_invalid():
    seen = []
    client = ChatClient("https://example.invalid", "key", "model", on_response=seen.append,
                        transport=httpx.MockTransport(lambda r: httpx.Response(200, json={
                            "usage": {"prompt_tokens": 10, "completion_tokens": 3, "total_tokens": 13},
                            "choices": [{"message": {"content": "invalid json"}}],
                        })))
    with pytest.raises(ProviderError):
        client.complete_json("JSON", {})
    assert seen[0]["usage"]["total_tokens"] == 13


def test_missing_usage_is_not_reported_as_measured_zero():
    seen = []
    client = ChatClient("https://example.invalid", "key", "model", on_response=seen.append,
                        transport=httpx.MockTransport(lambda r: httpx.Response(200, json={
                            "choices": [{"message": {"content": "{}"}}],
                        })))
    client.complete_json("JSON", {})
    assert seen[0]["usage_reported"] is False
    assert seen[0]["usage"] == {}


@pytest.mark.parametrize("fields", [{"llm_thinking": "bad"}, {"llm_max_output_tokens": 0}])
def test_invalid_live_configuration_fails_locally(fields):
    with pytest.raises(ValueError):
        Settings(**fields)
