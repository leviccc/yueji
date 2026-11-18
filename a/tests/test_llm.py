import json

import httpx
import pytest

from yueji_plot.config import Settings
from yueji_plot.llm import Qwen
from yueji_plot.models import Extraction


def test_qwen_structured_non_thinking_request_and_usage(store, book):
    captured = []

    def handle(request):
        body = json.loads(request.content)
        captured.append(body)
        assert request.url.path == "/compatible-mode/v1/chat/completions"
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": '{"events":[]}'}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 1200, "completion_tokens": 40},
            },
        )

    model = Qwen(Settings(api_key="unit-test-key"), store, transport=httpx.MockTransport(handle))
    assert model.generate(Extraction, "抽取事件", {"source": "测试段落"}, book["id"]).events == []
    assert captured[0]["model"] == "qwen-plus-2025-12-01"
    assert captured[0]["enable_thinking"] is False
    assert captured[0]["response_format"] == {"type": "json_object"}
    assert store.usage()["input_tokens"] == 1200
    assert store.usage()["cost_cny"] == pytest.approx(0.00104)


def test_invalid_model_json_still_records_billed_usage(store, book):
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "不是JSON"}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 10},
            },
        )
    )
    model = Qwen(Settings(api_key="unit-test-key"), store, transport=transport)
    with pytest.raises(ValueError):
        model.generate(Extraction, "抽取事件", {}, book["id"])
    assert store.usage()["output_tokens"] == 10


def test_failed_http_response_does_not_expose_authorization(store, book):
    transport = httpx.MockTransport(
        lambda request: httpx.Response(401, json={"error": "no access"})
    )
    model = Qwen(Settings(api_key="private-value"), store, transport=transport)
    with pytest.raises(ValueError, match="HTTP 401") as error:
        model.generate(Extraction, "抽取", {}, book["id"])
    assert "private-value" not in str(error.value)


def test_missing_key_causes_no_external_request_or_bill(store, book):
    model = Qwen(Settings(), store)
    with pytest.raises(ValueError, match="DASHSCOPE_API_KEY"):
        model.generate(Extraction, "抽取", {}, book["id"])
    assert store.usage()["calls"] == 0
