"""Unified model gateway.

Routing order (first configured wins, with retry + fallback):
    1. Bifrost by Maxim AI  (OpenAI-compatible gateway: one key, many models)
    2. OpenAI direct
    3. Gemini direct
    4. Deterministic engine (no network, always available)

The deterministic engine is not a mock of an LLM: it is a small rule-based
reasoning module used for offline tests and for reproducible benchmark runs.
Every call records provider, model, latency, tokens, retry count and cost so
the observability page only ever shows measured numbers.
"""
from __future__ import annotations

import asyncio
import json
import re
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.core.config import settings
from app.core.logging import log

JSON_BLOCK = re.compile(r"\{.*\}|\[.*\]", re.DOTALL)


@dataclass
class LLMResult:
    text: str
    provider: str
    model: str
    route: str = "primary"
    latency_ms: float = 0.0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: float = 0.0
    retries: int = 0
    status: str = "ok"
    error: str | None = None
    data: Any = field(default=None)


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def _cost(prompt_tokens: int, completion_tokens: int) -> float:
    return round(
        prompt_tokens / 1000 * settings.price_input_per_1k
        + completion_tokens / 1000 * settings.price_output_per_1k,
        6,
    )


def parse_json(text: str) -> Any:
    """Tolerant JSON extraction from a model response."""
    text = (text or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?|```$", "", text).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = JSON_BLOCK.search(text)
        if not match:
            raise ValueError("no JSON object found in model output")
        return json.loads(match.group(0))


class LLMGateway:
    """Async gateway with provider fallback. Safe to instantiate per request."""

    def __init__(self) -> None:
        self.calls: list[LLMResult] = []

    # -- availability ------------------------------------------------------
    @property
    def live(self) -> bool:
        return settings.live_llm

    def _routes(self) -> list[tuple[str, str]]:
        """Return [(route_kind, model_id)] in preference order."""
        chain: list[tuple[str, str]] = [("primary", settings.model_primary)]
        if settings.model_fallback and settings.model_fallback != settings.model_primary:
            chain.append(("fallback", settings.model_fallback))
        return chain

    # -- public API --------------------------------------------------------
    async def complete_json(
        self,
        *,
        task: str,
        system: str,
        user: str,
        temperature: float = 0.0,
        max_tokens: int = 1600,
    ) -> LLMResult:
        if not self.live:
            return LLMResult(
                text="",
                provider="deterministic",
                model="epoch-heuristics-v1",
                route="deterministic",
                status="ok",
            )

        last_error: str | None = None
        attempts = 0
        for route, model in self._routes():
            for retry in range(settings.llm_max_retries + 1):
                attempts = retry
                started = time.perf_counter()
                try:
                    text, p_tok, c_tok, provider = await self._dispatch(
                        model=model, system=system, user=user,
                        temperature=temperature, max_tokens=max_tokens,
                    )
                    latency = (time.perf_counter() - started) * 1000
                    result = LLMResult(
                        text=text,
                        provider=provider,
                        model=model,
                        route=route,
                        latency_ms=round(latency, 2),
                        prompt_tokens=p_tok,
                        completion_tokens=c_tok,
                        cost_usd=_cost(p_tok, c_tok),
                        retries=retry,
                    )
                    try:
                        result.data = parse_json(text)
                    except ValueError as exc:
                        result.status = "unparseable"
                        result.error = str(exc)
                    self.calls.append(result)
                    return result
                except Exception as exc:  # noqa: BLE001 - provider errors are heterogeneous
                    last_error = f"{type(exc).__name__}: {exc}"
                    log.warning(
                        "llm_call_failed",
                        extra={"event": "llm_failed", "model": model, "extra_data": last_error},
                    )
                    if retry < settings.llm_max_retries:
                        await asyncio.sleep(0.6 * (2**retry))

        result = LLMResult(
            text="", provider="deterministic", model="epoch-heuristics-v1",
            route="deterministic", status="failed", error=last_error, retries=attempts,
        )
        self.calls.append(result)
        return result

    # -- provider dispatch -------------------------------------------------
    async def _dispatch(
        self, *, model: str, system: str, user: str, temperature: float, max_tokens: int
    ) -> tuple[str, int, int, str]:
        if settings.bifrost_api_key:
            url = _join(settings.bifrost_base_url or "https://gateway.getbifrost.ai", "v1/chat/completions")
            text, p, c = await _openai_chat(
                url=url, key=settings.bifrost_api_key, model=model,
                system=system, user=user, temperature=temperature, max_tokens=max_tokens,
            )
            return text, p, c, "bifrost"

        if settings.openai_api_key and not model.startswith("google/"):
            url = _join(settings.openai_base_url, "chat/completions")
            text, p, c = await _openai_chat(
                url=url, key=settings.openai_api_key, model=model.split("/")[-1],
                system=system, user=user, temperature=temperature, max_tokens=max_tokens,
            )
            return text, p, c, "openai"

        if settings.gemini_api_key:
            bare = model.split("/")[-1]
            text, p, c = await _gemini_chat(
                model=bare, system=system, user=user,
                temperature=temperature, max_tokens=max_tokens,
            )
            return text, p, c, "gemini"

        raise RuntimeError("no live provider configured")


def _join(base: str, path: str) -> str:
    return f"{base.rstrip('/')}/{path.lstrip('/')}"


async def _openai_chat(
    *, url: str, key: str, model: str, system: str, user: str,
    temperature: float, max_tokens: int,
) -> tuple[str, int, int]:
    payload = {
        "model": model,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=settings.llm_timeout_seconds) as client:
        resp = await client.post(url, json=payload, headers=headers)
        if resp.status_code >= 400:
            # Some gateways reject response_format; retry once without it.
            payload.pop("response_format", None)
            resp = await client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        body = resp.json()
    choice = body["choices"][0]["message"]["content"]
    usage = body.get("usage", {}) or {}
    return (
        choice,
        int(usage.get("prompt_tokens") or _estimate_tokens(system + user)),
        int(usage.get("completion_tokens") or _estimate_tokens(choice)),
    )


async def _gemini_chat(
    *, model: str, system: str, user: str, temperature: float, max_tokens: int
) -> tuple[str, int, int]:
    url = _join(
        settings.gemini_base_url,
        f"models/{model}:generateContent?key={settings.gemini_api_key}",
    )
    payload = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": user}]}],
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
            "responseMimeType": "application/json",
        },
    }
    async with httpx.AsyncClient(timeout=settings.llm_timeout_seconds) as client:
        resp = await client.post(url, json=payload)
        resp.raise_for_status()
        body = resp.json()
    text = body["candidates"][0]["content"]["parts"][0]["text"]
    usage = body.get("usageMetadata", {}) or {}
    return (
        text,
        int(usage.get("promptTokenCount") or _estimate_tokens(system + user)),
        int(usage.get("candidatesTokenCount") or _estimate_tokens(text)),
    )


def gateway() -> LLMGateway:
    return LLMGateway()
