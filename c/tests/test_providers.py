"""Provider contract and privacy checks; these tests never use the network."""

import json

import httpx
import pytest

from yueji_qa.providers import ChatClient, EmbedClient, ProviderError


SECRET = "sk-test-never-leak-this"


def chat_with_response(response):
    return ChatClient(
        "https://example.invalid/v1/", SECRET, "test-model",
        transport=httpx.MockTransport(lambda request: response),
    )


def chat_response(content, **choice_extra):
    return httpx.Response(200, json={"choices": [{"message": {"content": content}, **choice_extra}]})


@pytest.mark.parametrize("content", ['{"answer":"原文"}', '```json\n{"answer":"原文"}\n```'])
def test_chat_json_and_code_fence(content):
    assert chat_with_response(chat_response(content)).complete_json("返回 JSON", {"q": "谁"}) == {"answer": "原文"}


def test_chat_request_contract():
    def handler(request):
        assert str(request.url) == "https://example.invalid/v1/chat/completions"
        assert request.headers["Authorization"] == "Bearer " + SECRET
        body = json.loads(request.content)
        assert body["response_format"] == {"type": "json_object"}
        assert body["temperature"] == 0
        assert body["model"] == "test-model"
        assert json.loads(body["messages"][1]["content"]) == {"question": "林舟是谁？"}
        return chat_response('{"claims":[]}')

    client = ChatClient("https://example.invalid/v1", SECRET, "test-model", transport=httpx.MockTransport(handler))
    assert client.complete_json("请返回 JSON", {"question": "林舟是谁？"}) == {"claims": []}


@pytest.mark.parametrize("response", [
    httpx.Response(200, json={}),
    httpx.Response(200, json={"choices": []}),
    httpx.Response(200, json={"choices": [None]}),
    httpx.Response(200, json={"choices": [{"message": None}]}),
    httpx.Response(200, json={"choices": [{"message": {"content": None}}]}),
    httpx.Response(200, content=b"not JSON"),
    httpx.Response(200, json=[]),
    chat_response("[]"),
    chat_response("untrusted prefix {\"answer\": 1}"),
    chat_response('{"answer":NaN}'),
])
def test_chat_rejects_malformed_results(response):
    with pytest.raises(ProviderError) as caught:
        chat_with_response(response).complete_json("JSON", {})
    assert caught.value.code == "provider_invalid_response"


@pytest.mark.parametrize("reason", ["length", "content_filter"])
def test_chat_rejects_incomplete_result_even_if_json_valid(reason):
    with pytest.raises(ProviderError) as caught:
        chat_with_response(chat_response("{}", finish_reason=reason)).complete_json("JSON", {})
    assert caught.value.code == "provider_incomplete_response"


@pytest.mark.parametrize("status,code", [
    (401, "provider_auth_error"), (403, "provider_auth_error"),
    (429, "provider_rate_limited"), (500, "provider_unavailable"),
    (400, "provider_http_error"), (302, "provider_http_error"),
])
def test_http_errors_are_sanitized_and_never_retried(status, code):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(status, text=SECRET, headers={"Location": "https://other.invalid/"})

    client = ChatClient("https://example.invalid/v1", SECRET, "test", transport=httpx.MockTransport(handler))
    with pytest.raises(ProviderError) as caught:
        client.complete_json("JSON", {})
    assert caught.value.code == code
    assert SECRET not in str(caught.value)
    assert len(calls) == 1


@pytest.mark.parametrize("error,code", [
    (httpx.ReadTimeout(SECRET), "provider_timeout"),
    (httpx.ConnectError(SECRET), "provider_network_error"),
])
def test_network_error_details_are_not_exposed(error, code):
    def handler(request):
        raise error

    client = ChatClient("https://example.invalid/v1", SECRET, "test", transport=httpx.MockTransport(handler))
    with pytest.raises(ProviderError) as caught:
        client.complete_json("JSON", {})
    assert caught.value.code == code
    assert SECRET not in str(caught.value)
    assert caught.value.__suppress_context__ is True


def test_response_size_is_bounded():
    client = chat_with_response(httpx.Response(200, content=b"x" * (2 * 1024 * 1024 + 1)))
    with pytest.raises(ProviderError) as caught:
        client.complete_json("JSON", {})
    assert caught.value.code == "provider_response_too_large"


def embed_with_data(data):
    return EmbedClient(
        "https://example.invalid/v1", SECRET, "test-embedding",
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json={"data": data})),
    )


def test_embeddings_restore_provider_indices():
    client = embed_with_data([
        {"index": 1, "embedding": [2, 0]},
        {"index": 0, "embedding": [0, 1]},
    ])
    assert client.embed(["甲", "乙"]) == [[0.0, 1.0], [2.0, 0.0]]


def test_embedding_request_contract_and_empty_input():
    calls = []

    def handler(request):
        calls.append(request)
        assert str(request.url) == "https://example.invalid/v1/embeddings"
        assert json.loads(request.content) == {"model": "emb", "input": ["原文"], "encoding_format": "float"}
        return httpx.Response(200, json={"data": [{"index": 0, "embedding": [1, 2]}]})

    client = EmbedClient("https://example.invalid/v1", "", "emb", transport=httpx.MockTransport(handler))
    assert client.embed([]) == []
    assert len(calls) == 0
    assert client.embed(["原文"]) == [[1.0, 2.0]]
    assert "Authorization" not in calls[0].headers


@pytest.mark.parametrize("data", [
    [], None, [{}], [None],
    [{"index": 0, "embedding": []}],
    [{"index": 0, "embedding": [True, 1]}],
    [{"index": 0, "embedding": ["1", 1]}],
    [{"index": 0, "embedding": [0, 0]}],
    [{"index": True, "embedding": [1]}],
    [{"index": 1, "embedding": [1]}],
    [{"index": -1, "embedding": [1]}],
])
def test_embeddings_reject_malformed_data(data):
    with pytest.raises(ProviderError) as caught:
        embed_with_data(data).embed(["原文"])
    assert caught.value.code == "provider_invalid_response"


@pytest.mark.parametrize("data", [
    [{"index": 0, "embedding": [1]}, {"index": 0, "embedding": [2]}],
    [{"index": 0, "embedding": [1]}, {"index": 1, "embedding": [1, 2]}],
])
def test_embeddings_reject_duplicates_and_inconsistent_dimensions(data):
    with pytest.raises(ProviderError):
        embed_with_data(data).embed(["甲", "乙"])


@pytest.mark.parametrize("number", ["NaN", "Infinity", "-Infinity", "1e400"])
def test_embeddings_reject_nonfinite_values(number):
    content = '{"data":[{"index":0,"embedding":[' + number + ']}]}'
    client = EmbedClient("https://example.invalid/v1", SECRET, "emb", transport=httpx.MockTransport(lambda request: httpx.Response(200, text=content)))
    with pytest.raises(ProviderError) as caught:
        client.embed(["原文"])
    assert caught.value.code == "provider_invalid_response"


@pytest.mark.parametrize("texts", [None, "原文", [""], [1], ["x" * 16001], ["x"] * 129])
def test_embedding_input_bounds_do_not_contact_provider(texts):
    def handler(request):
        pytest.fail("invalid input must not reach the provider")

    client = EmbedClient("https://example.invalid/v1", SECRET, "emb", transport=httpx.MockTransport(handler))
    with pytest.raises(ProviderError) as caught:
        client.embed(texts)
    assert caught.value.code == "invalid_input"


@pytest.mark.parametrize("base_url", ["file:///tmp/secret", "https://user:secret@example.com/v1", "https://example.com/v1?key=secret", "not a URL"])
def test_invalid_configuration(base_url):
    with pytest.raises(ProviderError) as caught:
        ChatClient(base_url, SECRET, "test")
    assert caught.value.code == "configuration_error"
    assert SECRET not in str(caught.value)
