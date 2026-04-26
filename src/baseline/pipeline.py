from __future__ import annotations

"""Naive pipeline baseline for ablation comparison.

Architecture:
  query → web_search + arxiv_search → concatenate → LLM synthesize → report

Intentionally simple — no graph, no contradiction detection, no iterative refinement.
The baseline's job is to be demonstrably worse on contradictory-sources queries.
"""

import uuid
from pathlib import Path

from src.tools.arxiv_search import arxiv_search
from src.tools.web_search import web_search
from src.utils.llm_client import chat


BASELINE_SYSTEM = """\
You are a research assistant. Summarize the provided search results into a research report.
Write a confident, well-organized report with an executive summary and key findings.
Cite sources where possible. Do not flag uncertainty unless the text explicitly states it."""


def run_baseline(query: str, output_dir: str = "outputs/baseline") -> dict:
    """Run the naive pipeline baseline. Returns path to report."""
    session_id = uuid.uuid4().hex[:8]

    # Single-pass search
    web_results = web_search(query, max_results=8)
    arxiv_results = arxiv_search(query, max_results=5)

    context_parts = []
    sources = []
    for r in web_results:
        context_parts.append(f"[WEB] {r.title}\nURL: {r.url}\n{r.content[:1500]}")
        sources.append(r.url)
    for r in arxiv_results:
        context_parts.append(f"[ARXIV] {r.title}\nURL: {r.url}\n{r.content[:1500]}")
        sources.append(r.url)

    context = "\n\n---\n\n".join(context_parts[:12])  # cap context

    prompt = f"""Research question: {query}

Search results:
{context}

Write a structured research report answering the question."""

    try:
        report = chat(BASELINE_SYSTEM, prompt, max_tokens=3000)
    except Exception as e:
        report = f"[Baseline failed: {e}]"

    report += f"\n\n---\n\n**Baseline metadata:** {len(web_results)} web results, {len(arxiv_results)} arXiv results, 1 iteration"

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    report_path = out / f"baseline_{session_id}.md"
    report_path.write_text(report, encoding="utf-8")

    return {
        "session_id": session_id,
        "report_path": str(report_path),
        "sources": len(sources),
        "iterations": 1,
    }
