from __future__ import annotations

from typing import Any, Optional

from typing_extensions import TypedDict

from src.graph.evidence_graph import EvidenceGraph
from src.graph.schemas import RawDocument
from src.utils.logging import ResearchTrace


class ResearchState(TypedDict):
    # ── Input ────────────────────────────────────────────────────────────────
    query: str
    session_id: str

    # ── Query Architect output ───────────────────────────────────────────────
    research_brief: dict  # structured brief with sub-questions, query_type, scope

    # ── Accumulated evidence ─────────────────────────────────────────────────
    raw_documents: list[dict]   # serialized RawDocument dicts
    claims: list[dict]          # serialized Claim dicts

    # ── Core data structure (not serializable natively — held as Any) ────────
    evidence_graph: Any         # EvidenceGraph instance

    # ── Loop control ─────────────────────────────────────────────────────────
    iteration_count: int
    max_iterations: int         # set by Query Architect based on difficulty
    search_budget_remaining: int
    stability_window: int       # consecutive iterations to check for stability
    stability_threshold_nodes: int
    stability_threshold_edges: int

    # ── Skeptic tracking ─────────────────────────────────────────────────────
    skeptic_challenges_this_iteration: int   # >0 → one more CH pass before stability
    skeptic_coverage: dict      # {claim_id: {challenged: bool, found_disconfirming: bool}}

    # ── Iteration bookkeeping ────────────────────────────────────────────────
    nodes_added_this_iteration: int
    contradiction_edges_added_this_iteration: int

    # ── Current search targets ───────────────────────────────────────────────
    pending_search_queries: list[dict]  # [{query, source_types, priority, reason}]

    # ── Output ───────────────────────────────────────────────────────────────
    final_report: Optional[str]
    graph_json: Optional[dict]  # serialized graph for output
    trace: Any                  # ResearchTrace instance


def initial_state(query: str, session_id: str) -> ResearchState:
    """Return a fresh state for a new research session with safe defaults."""
    import os
    return ResearchState(
        query=query,
        session_id=session_id,
        research_brief={},
        raw_documents=[],
        claims=[],
        evidence_graph=EvidenceGraph(),
        iteration_count=0,
        max_iterations=int(os.getenv("RESEARCH_MAX_ITERATIONS", "8")),
        search_budget_remaining=int(os.getenv("RESEARCH_SEARCH_BUDGET", "40")),
        stability_window=int(os.getenv("RESEARCH_STABILITY_WINDOW", "5")),
        stability_threshold_nodes=int(os.getenv("RESEARCH_STABILITY_THRESHOLD_NODES", "3")),
        stability_threshold_edges=int(os.getenv("RESEARCH_STABILITY_THRESHOLD_EDGES", "2")),
        skeptic_challenges_this_iteration=0,
        skeptic_coverage={},
        nodes_added_this_iteration=0,
        contradiction_edges_added_this_iteration=0,
        pending_search_queries=[],
        final_report=None,
        graph_json=None,
        trace=ResearchTrace(query=query, session_id=session_id),
    )
