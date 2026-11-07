"""Module C — Evidence Retrieval Engine.

Providers
--------
* TavilyProvider     — live web search (requires TAVILY_API_KEY).
* CorpusProvider      — deterministic retriever over a bundled evidence corpus.
                       Used when no search key is configured so the pipeline,
                       tests and benchmark stay fully reproducible offline.
* FixtureProvider     — deterministic retriever over an injected fixture set
                       (used by the benchmark to make retrieval reproducible).

All providers return the same normalised shape, then the engine deduplicates by
canonical URL, scores authority, and stamps every source with a retrieval time.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import httpx

from app.core.config import settings
from app.core.logging import log
from app.core.security import detect_prompt_injection, sanitize_text, validate_public_url
from app.services.research import textutil as tu

CORPUS_PATH = Path(__file__).with_name("corpus.json")

AUTHORITY_BY_TYPE = {"gov": 0.94, "docs": 0.9, "paper": 0.88, "wiki": 0.7, "news": 0.72, "blog": 0.48, "forum": 0.38, "web": 0.55}

HIGH_AUTHORITY_DOMAINS = {
    "docs.python.org": 0.95, "peps.python.org": 0.95, "react.dev": 0.94, "nodejs.org": 0.93,
    "developer.mozilla.org": 0.94, "kubernetes.io": 0.92, "postgresql.org": 0.94,
    "ietf.org": 0.95, "rfc-editor.org": 0.96, "eur-lex.europa.eu": 0.96, "gdpr-info.eu": 0.85,
    "who.int": 0.95, "bipm.org": 0.95, "tailwindcss.com": 0.9, "vite.dev": 0.9,
    "ubuntu.com": 0.88, "openai.com": 0.8, "blog.google": 0.78, "github.com": 0.75,
}
LOW_AUTHORITY_HINTS = ("medium.com", "blogspot", "wordpress.com", "quora.com", "pinterest")
NEWS_HINTS = ("reuters.com", "apnews.com", "bbc.com", "nytimes.com", "thehindu.com", "economictimes")
FORUM_HINTS = ("reddit.com", "stackoverflow.com", "news.ycombinator.com", "discourse")

TRACKING_PARAMS = {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "gclid", "fbclid", "ref", "si"}


class RetrievalProvider(Protocol):
    name: str

    async def search(self, query: str, *, max_results: int) -> list[dict]: ...


# --------------------------------------------------------------------------- #
# normalisation helpers
# --------------------------------------------------------------------------- #
def canonicalize(url: str) -> str:
    try:
        parsed = urlparse(url.strip())
    except ValueError:
        return url
    query = [(k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=False) if k.lower() not in TRACKING_PARAMS]
    path = parsed.path.rstrip("/") or "/"
    return urlunparse((parsed.scheme or "https", parsed.netloc.lower(), path, "", urlencode(query), ""))


def domain_of(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def classify_source(url: str) -> str:
    domain = domain_of(url)
    if domain.endswith((".gov", ".gov.in", ".gov.uk")) or domain.endswith(".int"):
        return "gov"
    if any(h in domain for h in NEWS_HINTS):
        return "news"
    if any(h in domain for h in FORUM_HINTS):
        return "forum"
    if any(h in domain for h in LOW_AUTHORITY_HINTS):
        return "blog"
    if domain.startswith("docs.") or domain in HIGH_AUTHORITY_DOMAINS or domain.endswith(".io") or "/docs" in url:
        return "docs"
    if "wikipedia.org" in domain:
        return "wiki"
    if any(k in url for k in ("/blog", "/news", "/posts/")):
        return "blog"
    return "web"


def authority_score(url: str, source_type: str, title: str = "") -> float:
    domain = domain_of(url)
    for known, score in HIGH_AUTHORITY_DOMAINS.items():
        if domain == known or domain.endswith("." + known):
            return score
    base = AUTHORITY_BY_TYPE.get(source_type, 0.55)
    return round(min(0.97, base), 3)


def dedupe_key(url: str, title: str) -> str:
    basis = canonicalize(url) or f"{domain_of(url)}::{re.sub(r'[^a-z0-9]', '', title.lower())[:80]}"
    return hashlib.sha256(basis.encode()).hexdigest()[:32]


def normalize_source(raw: dict, *, query: str, retrieved_at: datetime | None = None) -> dict:
    url = str(raw.get("url", "")).strip()
    title = tu.truncate(str(raw.get("title") or domain_of(url) or "Untitled source"), 300)
    content = sanitize_text(str(raw.get("content") or raw.get("snippet") or ""), max_chars=12000)
    published_raw = raw.get("published_date") or raw.get("published") or raw.get("date")
    published = tu.parse_date(str(published_raw)) if published_raw else None
    effective = tu.parse_date(str(raw.get("effective"))) if raw.get("effective") else None
    stype = str(raw.get("source_type") or classify_source(url))
    canonical = canonicalize(url)
    return {
        "url": url,
        "canonical_url": canonical,
        "domain": domain_of(canonical or url),
        "title": title,
        "publisher": raw.get("publisher"),
        "source_type": stype,
        "published_at": published,
        "effective_at": effective,
        "retrieved_at": retrieved_at or datetime.now(timezone.utc),
        "authority_score": authority_score(canonical or url, stype, title),
        "content": content,
        "version": raw.get("version"),
        "supersedes": raw.get("supersedes"),
        "raw_metadata": {k: v for k, v in raw.items() if k not in {"content", "url", "title"}},
        "injection_flags": detect_prompt_injection(content),
        "query": query,
    }


def deduplicate(sources: list[dict]) -> list[dict]:
    """Keep the richest record per canonical URL; merge hit counts."""
    by_key: dict[str, dict] = {}
    for src in sources:
        key = dedupe_key(src["url"], src["title"])
        existing = by_key.get(key)
        if existing is None:
            src["dedupe_key"] = key
            src["hit_queries"] = [src.pop("query", "")]
            by_key[key] = src
        else:
            if len(src["content"]) > len(existing["content"]):
                merged_queries = existing.get("hit_queries", [])
                src["hit_queries"] = merged_queries + [src.pop("query", "")]
                src["dedupe_key"] = key
                by_key[key] = src
            else:
                existing["hit_queries"].append(src.pop("query", ""))
    return list(by_key.values())


# --------------------------------------------------------------------------- #
# providers
# --------------------------------------------------------------------------- #
class TavilyProvider:
    name = "tavily"

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or settings.tavily_api_key

    async def search(self, query: str, *, max_results: int) -> list[dict]:
        payload = {
            "api_key": self.api_key,
            "query": query,
            "search_depth": "advanced",
            "include_answer": False,
            "include_raw_content": False,
            "max_results": max_results,
        }
        last_error: Exception | None = None
        for attempt in range(2):
            started = time.perf_counter()
            try:
                async with httpx.AsyncClient(timeout=settings.tavily_timeout_seconds) as client:
                    resp = await client.post(f"{settings.tavily_base_url.rstrip('/')}/search", json=payload)
                    resp.raise_for_status()
                    body = resp.json()
                log.info(
                    "tavily_search",
                    extra={
                        "event": "search",
                        "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                        "extra_data": {"query": query, "results": len(body.get("results", []))},
                    },
                )
                return [
                    {
                        "url": item.get("url", ""),
                        "title": item.get("title", ""),
                        "content": item.get("content", ""),
                        "published_date": item.get("published_date"),
                        "score": item.get("score"),
                        "publisher": domain_of(item.get("url", "")),
                    }
                    for item in body.get("results", [])
                    if item.get("url")
                ]
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                log.warning("tavily_failed", extra={"event": "search_failed", "extra_data": str(exc)[:200]})
                time.sleep(0.5 * (attempt + 1))
        raise RuntimeError(f"Tavily search failed after retries: {last_error}")


class CorpusProvider:
    """Deterministic lexical retriever over bundled documents."""

    name = "corpus"

    def __init__(self, documents: list[dict] | None = None) -> None:
        if documents is None:
            documents = json.loads(CORPUS_PATH.read_text())["documents"]
        self.documents = documents

    def _score(self, query: str, doc: dict) -> float:
        haystack = f"{doc.get('title', '')} {doc.get('content', '')} {doc.get('version', '')}"
        cov = tu.coverage(query, haystack)
        exact = 1.0 if query.lower() in haystack.lower() else 0.0
        return 0.75 * cov + 0.25 * exact

    async def search(self, query: str, *, max_results: int) -> list[dict]:
        scored = [(self._score(query, doc), doc) for doc in self.documents]
        scored = [(s, d) for s, d in scored if s >= 0.18]
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [
            {
                "url": doc["url"],
                "title": doc["title"],
                "content": doc["content"],
                "published_date": doc.get("published"),
                "effective": doc.get("effective"),
                "source_type": doc.get("source_type"),
                "version": doc.get("version"),
                "publisher": doc.get("publisher"),
                "score": round(score, 4),
            }
            for score, doc in scored[:max_results]
        ]


class FixtureProvider:
    """Deterministic retriever that returns pre-labelled evidence for a claim."""

    name = "fixture"

    def __init__(self, fixtures: dict[str, list[dict]]) -> None:
        self.fixtures = fixtures

    @staticmethod
    def _norm(text: str) -> str:
        return re.sub(r"[^a-z0-9 ]+", " ", str(text).lower()).strip()

    def _match(self, claim_key: str) -> str | None:
        """Fixture lookup tolerant to punctuation/atomic-splitting differences."""
        key = self._norm(claim_key)
        if key in {self._norm(k) for k in self.fixtures}:
            for k in self.fixtures:
                if self._norm(k) == key:
                    return k
        key_tokens = set(key.split())
        best: str | None = None
        best_score = 0.0
        for candidate in self.fixtures:
            cand_tokens = set(self._norm(candidate).split())
            if not cand_tokens:
                continue
            score = len(key_tokens & cand_tokens) / len(cand_tokens)
            if score > best_score:
                best, best_score = candidate, score
        return best if best_score >= 0.45 else None

    async def search_for_claim(self, claim_key: str, *, max_results: int = 6) -> list[dict]:
        matched = self._match(claim_key)
        return (self.fixtures.get(matched, []) if matched else [])[:max_results]

    async def search(self, query: str, *, max_results: int) -> list[dict]:
        for items in self.fixtures.values():
            for item in items:
                if item.get("url") == query:
                    return [item]
        return []


# --------------------------------------------------------------------------- #
# engine
# --------------------------------------------------------------------------- #
def build_provider(fixtures: dict[str, list[dict]] | None = None) -> RetrievalProvider:
    if fixtures is not None:
        return FixtureProvider(fixtures)
    if settings.tavily_api_key:
        return TavilyProvider()
    return CorpusProvider()


def _result_cap(depth: str) -> int:
    return {"quick": 3, "standard": settings.tavily_max_results, "deep": settings.tavily_max_results + 4}.get(
        depth, settings.tavily_max_results
    )


async def retrieve_evidence(
    claims: list[dict],
    plans: list[dict],
    *,
    depth: str,
    provider: RetrievalProvider | None = None,
    fixtures: dict[str, list[dict]] | None = None,
) -> tuple[list[dict], dict]:
    """Search for every planned query and return normalised, deduplicated sources."""
    import asyncio

    provider = provider or build_provider(fixtures)
    cap = _result_cap(depth)
    retrieved_at = datetime.now(timezone.utc)
    raw_hits: list[dict] = []
    searches = 0
    failed_searches = 0

    async def run(claim: dict, plan: dict) -> list[dict]:
        nonlocal searches, failed_searches
        if not plan.get("needs_evidence", True):
            return []
        out: list[dict] = []
        if isinstance(provider, FixtureProvider):
            searches += 1
            items = await provider.search_for_claim(claim["text"])
            for item in items:
                enriched = dict(item)
                enriched.setdefault("query", plan["queries"][0] if plan["queries"] else claim["text"])
                out.append(normalize_source(enriched, query=enriched.get("query", ""), retrieved_at=retrieved_at))
            return out
        for query in plan["queries"]:
            searches += 1
            try:
                hits = await provider.search(query, max_results=cap)
            except Exception as exc:  # noqa: BLE001
                failed_searches += 1
                log.warning("retrieval_failed", extra={"event": "retrieval_failed", "extra_data": str(exc)[:200]})
                continue
            for hit in hits:
                out.append(normalize_source(hit, query=query, retrieved_at=retrieved_at))
        return out

    semaphore = asyncio.Semaphore(max(1, settings.research_concurrency))

    async def guarded(claim: dict, plan: dict) -> list[dict]:
        async with semaphore:
            return await run(claim, plan)

    batches = await asyncio.gather(
        *(guarded(claim, plan) for claim, plan in zip(claims, plans)), return_exceptions=True
    )
    for batch in batches:
        if isinstance(batch, Exception):
            failed_searches += 1
            continue
        raw_hits.extend(batch)

    sources = deduplicate(raw_hits)
    sources.sort(key=lambda s: (-s["authority_score"], s["title"]))
    meta = {
        "provider": provider.name,
        "searches": searches,
        "failed_searches": failed_searches,
        "raw_hits": len(raw_hits),
        "unique_sources": len(sources),
        "deduplicated": max(0, len(raw_hits) - len(sources)),
        # Cost is only charged by Tavily; corpus/fixture retrieval is free.
        "search_cost_usd": round(searches * settings.tavily_price_per_search, 4) if provider.name == "tavily" else 0.0,
    }
    return sources, meta


async def fetch_url_document(url: str) -> tuple[str, str]:
    """Fetch a user-supplied URL safely (SSRF validated, size capped, content stripped)."""
    safe_url = validate_public_url(url)
    async with httpx.AsyncClient(
        timeout=15.0, follow_redirects=True, max_redirects=3,
        headers={"User-Agent": "EPOCH-AI/1.0 (+research verification)"},
    ) as client:
        async with client.stream("GET", safe_url) as resp:
            resp.raise_for_status()
            ctype = resp.headers.get("content-type", "")
            if "text/html" not in ctype and "text/plain" not in ctype:
                raise ValueError(f"Unsupported content type: {ctype}")
            chunks: list[bytes] = []
            size = 0
            async for chunk in resp.aiter_bytes():
                size += len(chunk)
                if size > settings.max_url_fetch_bytes:
                    break
                chunks.append(chunk)
    html = b"".join(chunks).decode("utf-8", errors="ignore")
    title_match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    title = tu.truncate(re.sub(r"\s+", " ", title_match.group(1)).strip(), 200) if title_match else domain_of(safe_url)
    text = re.sub(r"(?is)<(script|style|nav|footer|header|svg)[^>]*>.*?</\1>", " ", html)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = re.sub(r"&[a-z]+;", " ", text)
    text = sanitize_text(text, max_chars=settings.max_input_chars)
    return title, text
