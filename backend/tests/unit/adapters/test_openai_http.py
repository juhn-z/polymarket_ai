"""Unit tests for OpenAIHttpClient (direct HTTP, respx-mocked)."""
from __future__ import annotations

import json

import httpx
import pytest
import respx

from app.adapters.openai_client import OpenAIHttpClient


@pytest.fixture
def client() -> OpenAIHttpClient:
    return OpenAIHttpClient(
        api_key="sk-test",
        base_url="https://api.openai.com/v1",
    )


_SCHEMA = {
    "type": "object",
    "properties": {"answer": {"type": "string"}},
    "required": ["answer"],
    "additionalProperties": False,
}


@respx.mock
async def test_predict_posts_structured_output_request(client: OpenAIHttpClient) -> None:
    route = respx.post("https://api.openai.com/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {"content": '{"answer": "42"}', "role": "assistant"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"total_tokens": 321},
            },
        )
    )

    result = await client.predict(
        system="sys",
        user="usr",
        response_schema=_SCHEMA,
        seed=7,
        model="gpt-5.4",
    )

    assert route.called
    req_body = route.calls.last.request.content
    req = json.loads(req_body)

    assert req["model"] == "gpt-5.4"
    assert req["seed"] == 7
    assert req["messages"][0] == {"role": "system", "content": "sys"}
    assert req["messages"][1] == {"role": "user", "content": "usr"}
    assert req["response_format"]["type"] == "json_schema"
    assert req["response_format"]["json_schema"]["strict"] is True
    assert req["response_format"]["json_schema"]["schema"] == _SCHEMA

    assert route.calls.last.request.headers["authorization"] == "Bearer sk-test"

    assert result["content"] == {"answer": "42"}
    assert result["tokens_used"] == 321
    assert result["latency_ms"] >= 0


@respx.mock
async def test_predict_uses_gpt5_compatible_params(client: OpenAIHttpClient) -> None:
    """GPT-5.x reject `top_p` and `max_tokens` — request must use
    `max_completion_tokens` and omit `top_p` (verified live against gpt-5.5)."""
    route = respx.post("https://api.openai.com/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": '{"answer": "ok"}', "role": "assistant"}}],
                "usage": {"total_tokens": 3},
            },
        )
    )

    await client.predict(
        system="sys", user="usr", response_schema=_SCHEMA, seed=3, model="gpt-5.5"
    )

    body = json.loads(route.calls.last.request.content)
    assert "max_completion_tokens" in body
    assert "max_tokens" not in body
    assert "top_p" not in body


@respx.mock
async def test_predict_uses_custom_base_url_for_openai_compatible_proxy() -> None:
    """An OpenAI-compatible proxy (e.g. AIHubMix) works by changing only base_url."""
    route = respx.post("https://aihubmix.com/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": '{"answer": "42"}', "role": "assistant"}}],
                "usage": {"total_tokens": 11},
            },
        )
    )

    proxy_client = OpenAIHttpClient(api_key="sk-proxy", base_url="https://aihubmix.com/v1")
    try:
        result = await proxy_client.predict(
            system="sys", user="usr", response_schema=_SCHEMA, seed=1, model="gpt-5.5"
        )
    finally:
        await proxy_client.aclose()

    assert route.called
    assert json.loads(route.calls.last.request.content)["model"] == "gpt-5.5"
    assert route.calls.last.request.headers["authorization"] == "Bearer sk-proxy"
    assert result["content"] == {"answer": "42"}


@respx.mock
async def test_predict_raises_value_error_on_non_json_content(client: OpenAIHttpClient) -> None:
    respx.post("https://api.openai.com/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={
                "choices": [
                    {"message": {"content": "not json at all", "role": "assistant"}}
                ],
                "usage": {"total_tokens": 10},
            },
        )
    )

    with pytest.raises(ValueError, match="content is not valid JSON"):
        await client.predict(
            system="sys", user="usr", response_schema=_SCHEMA, seed=7, model="gpt-5.4"
        )


@respx.mock
async def test_predict_raises_on_http_error(client: OpenAIHttpClient) -> None:
    respx.post("https://api.openai.com/v1/chat/completions").mock(
        return_value=httpx.Response(429, json={"error": {"message": "rate limited"}})
    )

    with pytest.raises(httpx.HTTPStatusError):
        await client.predict(
            system="sys", user="usr", response_schema=_SCHEMA, seed=7, model="gpt-5.4"
        )
