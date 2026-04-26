from __future__ import annotations

import os
import time
from dataclasses import dataclass

import httpx


@dataclass
class SearchResult:
    url: str
    title: str
    content: str
    published_date: str
    source: str = "web"


def web_search(query: str, max_results: int = 5) -> list[SearchResult]:
    """Search the web via Tavily. Returns [] on any failure — callers must handle empty results."""
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        raise EnvironmentError("TAVILY_API_KEY not set")

    payload = {
        "api_key": api_key,
        "query": query,
        "search_depth": "advanced",
        "max_results": max_results,
        "include_raw_content": True,
    }

    for attempt in range(3):
        try:
            response = httpx.post(
                "https://api.tavily.com/search",
                json=payload,
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()
            results = []
            for r in data.get("results", []):
                content = r.get("raw_content") or r.get("content") or ""
                results.append(SearchResult(
                    url=r.get("url", ""),
                    title=r.get("title", ""),
                    content=content[:8000],  # cap per-document token cost
                    published_date=r.get("published_date", "unknown"),
                    source="web",
                ))
            return results
        except httpx.TimeoutException:
            if attempt < 2:
                time.sleep(2 ** attempt)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                time.sleep(5)
            else:
                break
        except Exception:
            break

    return []
