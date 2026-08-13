"""
One interface. Every model in twin. sits behind this and nothing else.

This is the load-bearing file of the model-independence roadmap: the day an open
8B clears the golden set, swapping it is a config change, not a refactor. Any
code that imports an API SDK outside this module is a bug.

No network calls happen at import time. Adapters are lazy so the eval harness can
run with the mock provider on a laptop with no keys.
"""

from __future__ import annotations

import base64
import json
import os
import time
from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class VisionResponse:
    """What every provider must return. Nothing provider-specific leaks past here."""
    text: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: int = 0
    raw: dict[str, Any] = field(default_factory=dict)

    def json(self) -> Any:
        """Parse a JSON body out of the response, tolerating fenced output."""
        t = self.text.strip()
        if t.startswith("```"):
            t = t.split("```")[1]
            if t.startswith("json"):
                t = t[4:]
        start = min((i for i in (t.find("{"), t.find("[")) if i != -1), default=-1)
        if start == -1:
            raise ValueError(f"no JSON found in response: {self.text[:200]}")
        end = max(t.rfind("}"), t.rfind("]"))
        return json.loads(t[start:end + 1])


class VisionProvider(Protocol):
    name: str
    model: str
    # $ per 1M tokens, so the eval table can price every row
    price_in: float
    price_out: float

    def see(self, images: list[bytes], prompt: str, system: str = "",
            max_tokens: int = 1500) -> VisionResponse: ...


def _b64(b: bytes) -> str:
    return base64.standard_b64encode(b).decode()


def _media_type(b: bytes) -> str:
    if b[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if b[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if b[:4] == b"RIFF" and b[8:12] == b"WEBP":
        return "image/webp"
    return "image/jpeg"


class OpenAICompatVision:
    """
    Covers everything that speaks the OpenAI chat-completions shape: Fireworks,
    Together, DeepInfra, Groq, vLLM, OpenRouter, and OpenAI itself. This is the
    single adapter that unlocks the entire open-weights field for benchmarking —
    Qwen-VL, InternVL, Kimi-VL, MiniCPM and friends all arrive through here.
    """

    def __init__(self, model: str, base_url: str, api_key_env: str,
                 price_in: float = 0.0, price_out: float = 0.0, name: str | None = None,
                 default_headers: dict[str, str] | None = None):
        self.name = name or f"{base_url.split('//')[-1].split('/')[0]}:{model}"
        self.model = model
        self.base_url = base_url
        self.api_key_env = api_key_env
        self.price_in = price_in
        self.price_out = price_out
        self.default_headers = default_headers or {}
        self._client = None

    def _c(self):
        if self._client is None:
            from openai import OpenAI  # lazy
            self._client = OpenAI(base_url=self.base_url,
                                  api_key=os.environ[self.api_key_env],
                                  default_headers=self.default_headers)
        return self._client

    def see(self, images, prompt, system="", max_tokens=1500) -> VisionResponse:
        parts = [{"type": "image_url",
                  "image_url": {"url": f"data:{_media_type(im)};base64,{_b64(im)}"}}
                 for im in images]
        parts.append({"type": "text", "text": prompt})
        msgs = ([{"role": "system", "content": system}] if system else []) + \
               [{"role": "user", "content": parts}]
        t0 = time.time()
        r = self._c().chat.completions.create(
            model=self.model, messages=msgs, max_tokens=max_tokens, temperature=0)
        u = r.usage
        return VisionResponse(
            text=r.choices[0].message.content or "",
            model=self.model,
            input_tokens=getattr(u, "prompt_tokens", 0),
            output_tokens=getattr(u, "completion_tokens", 0),
            latency_ms=int((time.time() - t0) * 1000),
        )


class MockVision:
    """
    Replays recorded decodes from disk. Two jobs, both real:
      1. CI — the harness must run green with no keys and no spend.
      2. Regression — once a model's outputs are recorded, prompt-only changes
         can be scored against the recording to isolate prompt effects from
         model drift.
    """

    def __init__(self, fixtures: dict[str, str], name: str = "mock"):
        self.name = name
        self.model = "mock"
        self.price_in = self.price_out = 0.0
        self._f = fixtures
        self._i = 0

    def see(self, images, prompt, system="", max_tokens=1500) -> VisionResponse:
        key = str(self._i)
        self._i += 1
        return VisionResponse(text=self._f.get(key, "{}"), model="mock", latency_ms=1)


# --------------------------------------------------------------------------- #
# Registry — the eval table's row list lives here, nowhere else.
# --------------------------------------------------------------------------- #

def registry() -> dict[str, Any]:
    orv = lambda model, pin, pout: OpenAICompatVision(
        model, "https://openrouter.ai/api/v1", "OPENROUTER_API_KEY", pin, pout,
        name=f"openrouter:{model}",
        default_headers={"HTTP-Referer": "https://github.com/Ynwa114/vogueBench",
                         "X-Title": "vogueBench"},
    )
    return {
        # Frontier aliases deliberately remain short for label/eval commands, but
        # every live request routes through OpenRouter and one credential source.
        "sonnet":    lambda: orv("anthropic/claude-sonnet-5", 2.0, 10.0),
        "haiku":     lambda: orv("anthropic/claude-haiku-4.5", 1.0, 5.0),
        "gpt56":     lambda: orv("openai/gpt-5.6-terra", 1.0, 6.0),
        # open weights — candidates for the tagger first, the decode later
        "qwen-vl":  lambda: orv("qwen/qwen2.5-vl-72b-instruct", 0.25, 0.75),
        "llama-v":  lambda: orv("meta-llama/llama-4-scout", 0.10, 0.30),
        # OpenRouter prices verified 2026-08-14. Update with an eval note if routed
        # pricing changes, because these values drive the cost column.
        "or-gemini":  lambda: orv("google/gemini-2.5-flash", 0.3, 2.5),
        "or-qwen-vl": lambda: orv("qwen/qwen2.5-vl-72b-instruct", 0.25, 0.75),
        "or-llama-v": lambda: orv("meta-llama/llama-4-scout", 0.10, 0.30),
    }


def get(alias: str):
    r = registry()
    if alias not in r:
        raise KeyError(f"unknown provider '{alias}'. known: {', '.join(r)}")
    return r[alias]()
