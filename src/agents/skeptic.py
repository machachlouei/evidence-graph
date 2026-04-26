from __future__ import annotations

"""Skeptic — MVP scope:
  ✓ Bias detection — source monoculture check (graph traversal, no LLM)
  ✓ Disconfirmation search — targeted query against HIGH-confidence claims
  ✗ Debate sub-graph — deferred to full design
"""

import json
from typing import Optional

from src.graph.evidence_graph import EvidenceGraph
from src.graph.schemas import Claim
from src.utils.llm_client import chat
from src.utils.logging import ResearchTrace

MONOCULTURE_THRESHOLD = 0.70  # >70% of sources from same type → flag
DISCONF_CONFIDENCE_THRESHOLD = 0.80  # only challenge HIGH-confidence claims


# ── Bias detection ────────────────────────────────────────────────────────────

def detect_source_bias(graph: EvidenceGraph, trace: Optional[ResearchTrace] = None) -> list[dict]:
    """Flag HIGH-confidence claims where supporting sources show monoculture."""
    flags = []
    for claim in graph.get_high_confidence_claims(DISCONF_CONFIDENCE_THRESHOLD):
        dist = graph.get_source_distribution(claim.claim_id)
        sources = dist["sources"]
        if len(sources) < 2:
            continue  # single-source claims are flagged as low-evidence elsewhere

        type_counts: dict[str, int] = {}
        for s in sources:
            t = s["source_type"]
            type_counts[t] = type_counts.get(t, 0) + 1

        dominant_type = max(type_counts, key=lambda k: type_counts[k])
        dominant_ratio = type_counts[dominant_type] / len(sources)

        if dominant_ratio >= MONOCULTURE_THRESHOLD:
            flag = {
                "claim_id": claim.claim_id,
                "claim_text": claim.text,
                "bias_type": "source_monoculture",
                "detail": f"{dominant_ratio:.0%} of sources are '{dominant_type}'",
            }
            flags.append(flag)
            if trace:
                trace.skeptic_bias_flagged(claim.claim_id, "source_monoculture", flag["detail"])

    return flags


# ── Disconfirmation search ────────────────────────────────────────────────────

DISCONF_SYSTEM = """\
You are a skeptical research assistant. Generate a search query designed to find evidence AGAINST a given claim.

The query should target:
- Null results or failed replications
- Scope limitations or conditions under which the claim breaks down
- Contradicting studies, meta-analyses, or critiques
- Alternative explanations that undermine the claim

Return exactly this JSON:
{
  "query": "<search query>",
  "search_types": ["web", "arxiv"],
  "rationale": "<one sentence on what disconfirming evidence would look like>"
}"""


def generate_disconfirmation_queries(
    graph: EvidenceGraph,
    already_challenged: set[str],
    trace: Optional[ResearchTrace] = None,
) -> list[dict]:
    """Generate disconfirmation search queries for HIGH-confidence claims not yet challenged."""
    high_conf_claims = graph.get_high_confidence_claims(DISCONF_CONFIDENCE_THRESHOLD)
    unchallenged = [c for c in high_conf_claims if c.claim_id not in already_challenged]

    queries = []
    for claim in unchallenged[:3]:  # cap at 3 per iteration to control cost
        try:
            raw = chat(DISCONF_SYSTEM, f"Claim to challenge: {claim.text}", max_tokens=256)
            if raw.startswith("```"):
                raw = raw.split("```")[1].lstrip("json").strip()
            result = json.loads(raw)
            result["claim_id"] = claim.claim_id
            result["priority"] = "medium"
            result["reason"] = "skeptic_disconfirmation"
            queries.append(result)

            if trace:
                trace.skeptic_disconfirmation(claim.claim_id, result["query"], found=False)
        except Exception:
            continue

    return queries


def run_skeptic(
    graph: EvidenceGraph,
    skeptic_coverage: dict,
    trace: Optional[ResearchTrace] = None,
) -> tuple[list[dict], list[dict]]:
    """Run full MVP Skeptic pass.

    Returns:
        bias_flags: list of detected bias issues
        disconf_queries: list of search queries to issue
    """
    bias_flags = detect_source_bias(graph, trace)
    already_challenged = {
        cid for cid, info in skeptic_coverage.items() if info.get("challenged")
    }
    disconf_queries = generate_disconfirmation_queries(graph, already_challenged, trace)

    # Mark claims as challenged in coverage tracking
    for q in disconf_queries:
        cid = q.get("claim_id")
        if cid:
            if cid not in skeptic_coverage:
                skeptic_coverage[cid] = {}
            skeptic_coverage[cid]["challenged"] = True

    return bias_flags, disconf_queries
