"""LLM client — OpenAI-compatible chat completions.

Works with OpenAI, DeepSeek, Moonshot, Qwen (dashscope), vLLM, Ollama /v1,
LM Studio and any other endpoint that implements POST /chat/completions.

Design notes:
- Pure stdlib (urllib) so the core install stays dependency-light.
- `stream=True` yields SSE deltas for the playground.
- When no API key is configured, we fall back to a deterministic *mock*
  provider so the whole product is demoable offline.
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Iterator


@dataclass
class LLMError(Exception):
    message: str
    status: int = 0

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.message


@dataclass
class Completion:
    text: str
    model: str
    latency_ms: int
    tokens_in: int
    tokens_out: int
    mocked: bool = False


def _post(url: str, payload: dict, api_key: str, timeout: int) -> urllib.request.Request:
    data = json.dumps(payload).encode()
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return urllib.request.Request(url, data=data, headers=headers, method="POST")


def _parse_error(err: urllib.error.HTTPError) -> str:
    try:
        body = json.loads(err.read().decode())
        msg = body.get("error", {}).get("message") if isinstance(body.get("error"), dict) else body.get("message")
        return msg or str(err)
    except Exception:
        return str(err)


def _rough_tokens(text: str) -> int:
    """Cheap estimate: CJK ~1 char/token, latin ~4 chars/token."""
    cjk = sum(1 for c in text if "\u4e00" <= c <= "\u9fff")
    return max(1, cjk + (len(text) - cjk) // 4)


def chat(
    base_url: str,
    api_key: str,
    model: str,
    prompt: str,
    temperature: float = 0.7,
    max_tokens: int = 1024,
    system: str = "",
    timeout: int = 60,
) -> Completion:
    """Blocking chat completion."""
    if not api_key and "localhost" not in base_url and "127.0.0.1" not in base_url:
        return mock_completion(prompt, model)

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": model, "messages": messages,
        "temperature": temperature, "max_tokens": max_tokens, "stream": False,
    }
    url = base_url.rstrip("/") + "/chat/completions"
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(_post(url, payload, api_key, timeout), timeout=timeout) as r:
            body = json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        raise LLMError(f"上游返回 {e.code}: {_parse_error(e)}", e.code) from e
    except urllib.error.URLError as e:
        raise LLMError(f"无法连接 {base_url} — {e.reason}") from e
    except TimeoutError as e:
        raise LLMError(f"请求超时（{timeout}s）") from e

    latency = int((time.perf_counter() - started) * 1000)
    try:
        text = body["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError) as e:
        raise LLMError(f"响应格式异常: {str(body)[:200]}") from e
    usage = body.get("usage") or {}
    return Completion(
        text=text,
        model=body.get("model") or model,
        latency_ms=latency,
        tokens_in=usage.get("prompt_tokens") or _rough_tokens(prompt),
        tokens_out=usage.get("completion_tokens") or _rough_tokens(text),
    )


def chat_stream(
    base_url: str,
    api_key: str,
    model: str,
    prompt: str,
    temperature: float = 0.7,
    max_tokens: int = 1024,
    system: str = "",
    timeout: int = 60,
) -> Iterator[str]:
    """Yield text deltas (SSE). Falls back to mock streaming when offline."""
    if not api_key and "localhost" not in base_url and "127.0.0.1" not in base_url:
        yield from mock_stream(prompt)
        return

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    payload = {
        "model": model, "messages": messages,
        "temperature": temperature, "max_tokens": max_tokens, "stream": True,
    }
    url = base_url.rstrip("/") + "/chat/completions"
    try:
        resp = urllib.request.urlopen(_post(url, payload, api_key, timeout), timeout=timeout)
    except urllib.error.HTTPError as e:
        raise LLMError(f"上游返回 {e.code}: {_parse_error(e)}", e.code) from e
    except urllib.error.URLError as e:
        raise LLMError(f"无法连接 {base_url} — {e.reason}") from e

    with resp:
        for raw in resp:
            line = raw.decode("utf-8", "ignore").strip()
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                break
            try:
                chunk = json.loads(data)
            except json.JSONDecodeError:
                continue
            delta = (chunk.get("choices") or [{}])[0].get("delta", {}).get("content")
            if delta:
                yield delta


# --------------------------------- mocks ---------------------------------

_MOCK_NOTE = (
    "> ⚠️ **演示模式** — 未配置 API Key，以下为本地模拟输出。\n"
    "> 到「模型设置」填入任意 OpenAI 兼容服务的 Key 即可接入真实模型。\n\n"
)


def mock_completion(prompt: str, model: str = "") -> Completion:
    started = time.perf_counter()
    body = mock_text(prompt)
    return Completion(
        text=body, model=model or "mock-1",
        latency_ms=int((time.perf_counter() - started) * 1000) + 12,
        tokens_in=_rough_tokens(prompt), tokens_out=_rough_tokens(body), mocked=True,
    )


def mock_text(prompt: str) -> str:
    head = prompt.strip().splitlines()[0][:80] if prompt.strip() else "(empty)"
    return (
        _MOCK_NOTE +
        f"针对你的请求「{head}」，这里是结构化返回示例：\n\n"
        "## 1. 关键判断\n"
        "- 输入已被正确解析，模板变量全部完成替换。\n"
        "- 若接入真实模型，这里将返回符合提示词约束的实际内容。\n\n"
        "## 2. 输出结构\n"
        "| 字段 | 说明 |\n|---|---|\n"
        "| summary | 一句话结论 |\n| risks | 风险清单 |\n| next | 建议下一步 |\n\n"
        "## 3. 下一步\n"
        "在「模型设置」中配置 provider，然后回到 Playground 重新运行即可对比真实效果。\n"
    )


def mock_stream(prompt: str) -> Iterator[str]:
    text = mock_text(prompt)
    step = 6
    for i in range(0, len(text), step):
        yield text[i:i + step]
