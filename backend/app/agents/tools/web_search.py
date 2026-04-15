from __future__ import annotations

from dataclasses import dataclass
from html import unescape
import re
import time
from urllib.parse import parse_qs, quote_plus, unquote, urlparse

import httpx


DUCKDUCKGO_SEARCH_URL = "https://html.duckduckgo.com/html/?q={query}"
DEFAULT_MAX_RESULTS = 5
CACHE_TTL_SECONDS = 300
MAX_CACHE_ENTRIES = 128


_search_cache: dict[str, tuple[float, list[dict]]] = {}


BLOCKED_DOMAINS = {
    "duckduckgo.com",
    "localhost",
    "127.0.0.1",
}


SEARCH_HINTS = (
    "search",
    "find",
    "look up",
    "latest",
    "current",
    "today",
    "news",
    "recent",
    "web",
    "internet",
    "what is happening",
    "who won",
    "price",
)


def should_use_web_search(text: str) -> bool:
    normalized = " ".join(str(text or "").lower().split())
    if not normalized:
        return False

    return any(hint in normalized for hint in SEARCH_HINTS)


def _clean_text(value: str) -> str:
    return " ".join(str(value or "").split()).strip()


def _normalize_ddg_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.netloc.endswith("duckduckgo.com") and parsed.path.startswith("/l/"):
        query = parse_qs(parsed.query)
        target = query.get("uddg", [""])[0]
        if target:
            return unquote(target)

    if url.startswith("//"):
        return f"https:{url}"
    return url


def _strip_tags(value: str) -> str:
    return _clean_text(re.sub(r"<[^>]+>", " ", unescape(value or "")))


def _extract_ddg_results(html: str, max_results: int) -> list[dict]:
    # Capture anchors first; each one is a search hit candidate.
    anchor_pattern = re.compile(
        r'<a[^>]*class="[^"]*result__a[^"]*"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
        re.IGNORECASE | re.DOTALL,
    )
    snippet_pattern = re.compile(
        r'<(?:a|span)[^>]*class="[^"]*result__snippet[^"]*"[^>]*>(.*?)</(?:a|span)>',
        re.IGNORECASE | re.DOTALL,
    )

    results: list[dict] = []
    seen_urls: set[str] = set()
    for match in anchor_pattern.finditer(html):
        raw_url, raw_title = match.group(1), match.group(2)
        url = _normalize_ddg_url(unescape(raw_url))
        lower_url = url.lower()
        if "duckduckgo.com/y.js" in lower_url or "ad_provider=" in lower_url:
            continue
        if not url or url in seen_urls:
            continue

        seen_urls.add(url)
        title = _strip_tags(raw_title) or url

        # Look near this anchor for the closest snippet.
        window = html[match.end(): match.end() + 1800]
        snippet_match = snippet_pattern.search(window)
        snippet = _strip_tags(snippet_match.group(1)) if snippet_match else ""

        results.append({"title": title, "url": url, "snippet": snippet})
        if len(results) >= max_results:
            break

    return results


def _is_low_quality_result(item: dict) -> bool:
    url = _clean_text(item.get("url") or "")
    title = _clean_text(item.get("title") or "")

    if not url or not title or len(title) < 4:
        return True

    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return True

    domain = parsed.netloc.lower().replace("www.", "")
    if not domain or domain in BLOCKED_DOMAINS:
        return True

    return False


def _cache_key(query: str, max_results: int) -> str:
    return f"{query.lower().strip()}::{max_results}"


def _get_from_cache(key: str) -> list[dict] | None:
    item = _search_cache.get(key)
    if not item:
        return None

    expires_at, payload = item
    if expires_at <= time.time():
        _search_cache.pop(key, None)
        return None

    return payload


def _put_in_cache(key: str, payload: list[dict]) -> None:
    if len(_search_cache) >= MAX_CACHE_ENTRIES:
        # Remove one arbitrary old key to keep memory bounded.
        oldest_key = next(iter(_search_cache.keys()), None)
        if oldest_key:
            _search_cache.pop(oldest_key, None)

    _search_cache[key] = (time.time() + CACHE_TTL_SECONDS, payload)


def _build_search_result(rank: int, title: str, url: str, snippet: str) -> dict:
    parsed = urlparse(url)
    return SearchResult(
        rank=rank,
        title=_clean_text(title or url),
        url=_clean_text(url),
        snippet=_clean_text(snippet),
        domain=parsed.netloc.replace("www.", "") or "unknown",
    ).to_dict()


@dataclass
class SearchResult:
    rank: int
    title: str
    url: str
    snippet: str
    domain: str

    def to_dict(self) -> dict:
        return {
            "rank": self.rank,
            "title": self.title,
            "url": self.url,
            "snippet": self.snippet,
            "domain": self.domain,
        }


async def search_web(query: str, max_results: int = DEFAULT_MAX_RESULTS) -> list[dict]:
    search_query = _clean_text(query)
    if not search_query:
        return []

    key = _cache_key(search_query, max_results)
    cached = _get_from_cache(key)
    if cached is not None:
        return cached

    # DuckDuckGo is the only web-search backend in this project.
    url = DUCKDUCKGO_SEARCH_URL.format(query=quote_plus(search_query))
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
        )
    }

    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True, headers=headers) as client:
        response = await client.get(url)
        response.raise_for_status()

    extracted = _extract_ddg_results(response.text, max_results=max_results)

    results: list[SearchResult] = []
    seen_canonical_urls: set[str] = set()
    for index, item in enumerate(extracted[:max_results], start=1):
        if _is_low_quality_result(item):
            continue

        item_url = _normalize_ddg_url(item.get("url", ""))
        parsed = urlparse(item_url)

        canonical_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip("/")
        if canonical_url in seen_canonical_urls:
            continue
        seen_canonical_urls.add(canonical_url)

        results.append(
            SearchResult(
                rank=len(results) + 1,
                title=_clean_text(item.get("title") or item_url or search_query),
                url=item_url,
                snippet=_clean_text(item.get("snippet") or ""),
                domain=parsed.netloc.replace("www.", "") or "unknown",
            )
        )

        if len(results) >= max_results:
            break

    payload = [result.to_dict() for result in results]
    _put_in_cache(key, payload)

    return payload


async def get_search_diagnostics(query: str, max_results: int = DEFAULT_MAX_RESULTS) -> dict:
    search_query = _clean_text(query)
    if not search_query:
        return {
            "query": query,
            "cache_hit": False,
            "result_count": 0,
            "results": [],
            "context_preview": "",
        }

    key = _cache_key(search_query, max_results)
    cache_hit = _get_from_cache(key) is not None
    results = await search_web(search_query, max_results=max_results)

    return {
        "query": search_query,
        "cache_hit": cache_hit,
        "result_count": len(results),
        "results": results,
        "context_preview": build_search_context(results)[:1200],
    }


def build_search_context(results: list[dict]) -> str:
    if not results:
        return "No web search results were found."

    lines: list[str] = []
    for result in results:
        rank = result.get("rank", "?")
        title = _clean_text(result.get("title") or "Untitled result")
        url = _clean_text(result.get("url") or "")
        snippet = _clean_text(result.get("snippet") or "")

        block = [f"[{rank}] {title}", f"URL: {url}"]
        if snippet:
            block.append(f"Snippet: {snippet}")
        lines.append("\n".join(block))

    return "\n\n".join(lines)