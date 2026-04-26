from __future__ import annotations

import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass


NS = "http://www.w3.org/2005/Atom"

# arXiv CS categories relevant to LLM/AI research
_CS_CATEGORIES = {"cs.CL", "cs.AI", "cs.LG", "cs.NE", "stat.ML"}


@dataclass
class ArxivResult:
    url: str
    title: str
    content: str        # abstract
    published_date: str
    authors: list[str]
    source: str = "preprint"


def arxiv_search(query: str, max_results: int = 5) -> list[ArxivResult]:
    """Search arXiv via their public API.

    Searches title AND abstract fields only (not all fields) to avoid
    spurious matches from unrelated papers that share common words.
    Filters results to CS/ML categories unless the query is clearly
    outside that domain.
    Returns [] on any failure.
    """
    # Use ti: (title) and abs: (abstract) instead of all: to avoid
    # pulling in physics papers that contain incidental keyword matches
    encoded_query = urllib.parse.quote(query)
    search_query = f"ti:{encoded_query}+OR+abs:{encoded_query}"
    url = (
        f"https://export.arxiv.org/api/query"
        f"?search_query={search_query}"
        f"&start=0&max_results={max_results * 2}"  # fetch extra to allow filtering
        f"&sortBy=relevance&sortOrder=descending"
    )

    for attempt in range(3):
        try:
            with urllib.request.urlopen(url, timeout=20) as resp:
                xml_content = resp.read()
            break
        except Exception:
            if attempt < 2:
                time.sleep(2 ** attempt)
            else:
                return []

    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError:
        return []

    results = []
    for entry in root.findall(f"{{{NS}}}entry"):
        title_el = entry.find(f"{{{NS}}}title")
        summary_el = entry.find(f"{{{NS}}}summary")
        published_el = entry.find(f"{{{NS}}}published")
        id_el = entry.find(f"{{{NS}}}id")

        title = title_el.text.strip() if title_el is not None and title_el.text else ""
        abstract = summary_el.text.strip() if summary_el is not None and summary_el.text else ""
        published = published_el.text[:10] if published_el is not None and published_el.text else "unknown"
        arxiv_url = id_el.text.strip() if id_el is not None and id_el.text else ""

        if not title or not abstract:
            continue

        # Extract category tags and filter to CS/ML unless no CS results at all
        categories = {
            tag.get("term", "")
            for tag in entry.findall("{http://www.w3.org/2005/Atom}category")
        }
        # Skip clearly non-CS papers (physics, math-only, etc.)
        if categories and not categories.intersection(_CS_CATEGORIES):
            continue

        authors = [
            a.find(f"{{{NS}}}name").text.strip()
            for a in entry.findall(f"{{{NS}}}author")
            if a.find(f"{{{NS}}}name") is not None and a.find(f"{{{NS}}}name").text
        ]

        results.append(ArxivResult(
            url=arxiv_url,
            title=title,
            content=abstract,
            published_date=published,
            authors=authors,
        ))

        if len(results) >= max_results:
            break

    return results
