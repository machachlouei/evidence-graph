from __future__ import annotations

import json
from typing import Optional

from src.graph.evidence_graph import EvidenceGraph
from src.graph.schemas import Edge, ResolutionStatus
from src.utils.llm_client import chat
from src.utils.logging import ResearchTrace


QUERY_GEN_SYSTEM = """\
You are a research specialist who resolves contradictions between scientific claims.

Given two contradictory claims and their sources, generate a targeted search query that would find evidence to resolve or explain the contradiction. The query should:
1. Target the specific point of disagreement, not the general topic
2. Look for meta-analyses, systematic reviews, or studies that compare both positions
3. Include date range terms if the contradiction may be time-sensitive (e.g., "2023 2024")

Return exactly this JSON:
{
  "query": "<targeted search query>",
  "search_types": ["web", "arxiv"],
  "rationale": "<one sentence on what this query is looking for>"
}"""


RESOLUTION_SYSTEM = """\
You are a research arbitrator. Given two contradictory claims and a set of new evidence, determine whether the contradiction can be resolved.

Resolution options:
- "resolved_for_source": New evidence clearly supports Claim A and explains why Claim B is wrong/limited
- "resolved_for_target": New evidence clearly supports Claim B and explains why Claim A is wrong/limited
- "resolved_scope": Both claims are correct but apply to different conditions (e.g., model scale, dataset, task type)
- "irreducible": After reviewing evidence, the contradiction remains genuinely unresolved
- "insufficient_evidence": New evidence does not address the specific contradiction

Return exactly this JSON:
{
  "resolution": "<one of the five values>",
  "confidence": <float 0.0-1.0>,
  "explanation": "<one sentence explaining the resolution>"
}"""


def generate_resolution_query(edge: Edge, graph: EvidenceGraph) -> Optional[dict]:
    """Generate a targeted search query to resolve a contradiction edge."""
    src = graph.get_claim(edge.source_claim_id)
    tgt = graph.get_claim(edge.target_claim_id)
    if not src or not tgt:
        return None

    prompt = f"""Claim A: {src.text}
Source A: {src.source_url} ({src.source_date})

Claim B: {tgt.text}
Source B: {tgt.source_url} ({tgt.source_date})

These two claims contradict each other. Generate a search query to find evidence that resolves this contradiction."""

    try:
        raw = chat(QUERY_GEN_SYSTEM, prompt, max_tokens=256)
        if raw.startswith("```"):
            raw = raw.split("```")[1].lstrip("json").strip()
        result = json.loads(raw)
        result["edge_id"] = edge.edge_id
        result["priority"] = "high"
        result["reason"] = "contradiction_resolution"
        return result
    except Exception:
        return None


def attempt_resolution(
    edge: Edge,
    graph: EvidenceGraph,
    new_claim_texts: list[str],
    trace: Optional[ResearchTrace] = None,
) -> ResolutionStatus:
    """Given new evidence, determine if a contradiction edge can be resolved."""
    src = graph.get_claim(edge.source_claim_id)
    tgt = graph.get_claim(edge.target_claim_id)
    if not src or not tgt or not new_claim_texts:
        return ResolutionStatus.UNRESOLVED

    evidence_block = "\n".join(f"- {t}" for t in new_claim_texts[:10])
    prompt = f"""Claim A: {src.text}
Claim B: {tgt.text}

New evidence retrieved:
{evidence_block}

Can this contradiction be resolved?"""

    try:
        raw = chat(RESOLUTION_SYSTEM, prompt, max_tokens=256)
        if raw.startswith("```"):
            raw = raw.split("```")[1].lstrip("json").strip()
        parsed = json.loads(raw)
        resolution_str = parsed.get("resolution", "irreducible")

        status_map = {
            "resolved_for_source": ResolutionStatus.RESOLVED_FOR_SOURCE,
            "resolved_for_target": ResolutionStatus.RESOLVED_FOR_TARGET,
            "resolved_scope": ResolutionStatus.RESOLVED_SCOPE,
            "irreducible": ResolutionStatus.IRREDUCIBLE,
            "insufficient_evidence": ResolutionStatus.UNRESOLVED,
        }
        status = status_map.get(resolution_str, ResolutionStatus.UNRESOLVED)

        if trace:
            trace.contradiction_resolved(edge.edge_id, status.value)

        return status
    except Exception:
        return ResolutionStatus.UNRESOLVED


def get_contradiction_search_queries(
    graph: EvidenceGraph,
    max_queries: int = 5,
    trace: Optional[ResearchTrace] = None,
) -> list[dict]:
    """Generate search queries for all unresolved contradictions, up to max_queries."""
    unresolved = graph.get_unresolved_contradictions()
    queries = []
    for edge in unresolved[:max_queries]:
        if trace:
            src = graph.get_claim(edge.source_claim_id)
            tgt = graph.get_claim(edge.target_claim_id)
            if src and tgt:
                trace.contradiction_found(edge.edge_id, src.text[:80], tgt.text[:80])
        q = generate_resolution_query(edge, graph)
        if q:
            queries.append(q)
    return queries
