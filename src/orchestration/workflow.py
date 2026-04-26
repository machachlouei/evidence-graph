from __future__ import annotations

"""LangGraph stateful workflow for the deep research agent system.

Loop structure:
  query_architect → search → extract_and_graph → [stable? → report | unstable → contradiction_hunt → skeptic → search → ...]

Stopping conditions (first hit wins):
  1. Graph stability threshold reached AND skeptic_challenges_this_iteration == 0
  2. iteration_count >= max_iterations
  3. search_budget_remaining <= 0
"""

import uuid
from typing import Literal

from langgraph.graph import END, StateGraph

from src.agents.claim_extractor import extract_claims
from src.agents.contradiction_hunter import (
    attempt_resolution,
    get_contradiction_search_queries,
)
from src.agents.graph_manager import add_claims_to_graph
from src.agents.query_architect import build_research_brief
from src.agents.report_generator import generate_report, save_outputs
from src.agents.skeptic import run_skeptic
from src.graph.schemas import RawDocument, SourceType
from src.orchestration.state import ResearchState, initial_state
from src.tools.arxiv_search import arxiv_search
from src.tools.web_search import web_search


# ── Node implementations ─────────────────────────────────────────────────────

def node_query_architect(state: ResearchState) -> dict:
    trace = state["trace"]
    brief = build_research_brief(state["query"], trace)
    return {
        "research_brief": brief,
        "max_iterations": brief.get("max_iterations", state["max_iterations"]),
        "search_budget_remaining": brief.get("search_budget", state["search_budget_remaining"]),
        "pending_search_queries": brief.get("initial_search_queries", []),
    }


def node_search(state: ResearchState) -> dict:
    trace = state["trace"]
    pending = state["pending_search_queries"]
    budget = state["search_budget_remaining"]
    new_docs: list[dict] = []

    for search_item in pending:
        if budget <= 0:
            break
        query = search_item.get("query", "")
        source_types = search_item.get("source_types", ["web", "arxiv"])

        if "web" in source_types:
            import time
            t0 = time.time()
            trace.search_issued(query, "web")
            results = web_search(query, max_results=3)
            latency = (time.time() - t0) * 1000
            if results:
                trace.search_result(query, "web", len(results), latency)
                for r in results:
                    new_docs.append({
                        "doc_id": f"doc_{uuid.uuid4().hex[:8]}",
                        "url": r.url,
                        "title": r.title,
                        "content": r.content,
                        "source_type": "web",
                        "publication_date": r.published_date,
                        "search_query": query,
                    })
            else:
                trace.search_failed(query, "web", "no results or tool error")
            budget -= 1

        if "arxiv" in source_types and budget > 0:
            import time
            t0 = time.time()
            trace.search_issued(query, "arxiv")
            results = arxiv_search(query, max_results=3)
            latency = (time.time() - t0) * 1000
            if results:
                trace.search_result(query, "arxiv", len(results), latency)
                for r in results:
                    new_docs.append({
                        "doc_id": f"doc_{uuid.uuid4().hex[:8]}",
                        "url": r.url,
                        "title": r.title,
                        "content": r.content,
                        "source_type": "preprint",
                        "publication_date": r.published_date,
                        "search_query": query,
                    })
            else:
                trace.search_failed(query, "arxiv", "no results or tool error")
            budget -= 1

    return {
        "raw_documents": state["raw_documents"] + new_docs,
        "pending_search_queries": [],
        "search_budget_remaining": budget,
    }


def node_extract_and_graph(state: ResearchState) -> dict:
    trace = state["trace"]
    graph = state["evidence_graph"]
    existing_doc_ids = {c["source_id"] for c in state["claims"]}

    # Only process documents not yet extracted
    new_docs = [
        d for d in state["raw_documents"]
        if d["doc_id"] not in existing_doc_ids
    ]

    _SOURCE_TYPE_MAP = {
        "web": SourceType.WEB,
        "preprint": SourceType.PREPRINT,
        "peer_reviewed": SourceType.PEER_REVIEWED,
        "institutional_blog": SourceType.INSTITUTIONAL_BLOG,
    }

    all_new_claims = []
    for doc_dict in new_docs:
        doc = RawDocument(
            doc_id=doc_dict["doc_id"],
            url=doc_dict["url"],
            title=doc_dict["title"],
            content=doc_dict["content"],
            source_type=_SOURCE_TYPE_MAP.get(doc_dict["source_type"], SourceType.WEB),
            publication_date=doc_dict["publication_date"],
            search_query=doc_dict.get("search_query", ""),
        )
        claims = extract_claims(doc, trace)
        all_new_claims.extend(claims)

    nodes_added, contradiction_edges_added = add_claims_to_graph(all_new_claims, graph, trace)
    graph.record_iteration(nodes_added, contradiction_edges_added)

    trace.stability_check(
        state["iteration_count"] + 1,
        nodes_added,
        contradiction_edges_added,
        graph.is_stable(
            state["stability_threshold_nodes"],
            state["stability_threshold_edges"],
            state["stability_window"],
        ),
    )

    return {
        "claims": state["claims"] + [c.to_dict() for c in all_new_claims],
        "evidence_graph": graph,
        "iteration_count": state["iteration_count"] + 1,
        "nodes_added_this_iteration": nodes_added,
        "contradiction_edges_added_this_iteration": contradiction_edges_added,
        "skeptic_challenges_this_iteration": 0,  # reset before skeptic runs
    }


def node_contradiction_hunt(state: ResearchState) -> dict:
    trace = state["trace"]
    graph = state["evidence_graph"]

    # Attempt to resolve contradictions that have new evidence available
    # (new claims were added this iteration — check if any resolve existing edges)
    new_claim_texts = [c["text"] for c in state["claims"][-20:]]  # last batch

    for edge in graph.get_unresolved_contradictions():
        status = attempt_resolution(edge, graph, new_claim_texts, trace)
        if status.value not in ("unresolved",):
            graph.resolve_contradiction(edge.edge_id, status, [])

    # Generate search queries for still-unresolved contradictions
    queries = get_contradiction_search_queries(graph, max_queries=3, trace=trace)
    return {"pending_search_queries": queries}


def node_skeptic(state: ResearchState) -> dict:
    trace = state["trace"]
    graph = state["evidence_graph"]
    skeptic_coverage = state["skeptic_coverage"].copy()

    bias_flags, disconf_queries = run_skeptic(graph, skeptic_coverage, trace)

    # Add disconfirmation queries to pending searches
    existing_pending = state["pending_search_queries"]
    combined = existing_pending + [
        {"query": q["query"], "source_types": q.get("search_types", ["web", "arxiv"]),
         "priority": q.get("priority", "medium"), "reason": q.get("reason", "skeptic")}
        for q in disconf_queries
    ]

    return {
        "pending_search_queries": combined,
        "skeptic_challenges_this_iteration": len(disconf_queries),
        "skeptic_coverage": skeptic_coverage,
    }


def node_report(state: ResearchState) -> dict:
    trace = state["trace"]
    graph = state["evidence_graph"]
    report = generate_report(state["query"], graph, state["research_brief"], trace)
    graph_json = graph.to_node_link_data()
    return {"final_report": report, "graph_json": graph_json}


# ── Routing ──────────────────────────────────────────────────────────────────

def should_continue(state: ResearchState) -> Literal["contradiction_hunt", "report"]:
    graph = state["evidence_graph"]
    iteration = state["iteration_count"]
    max_iter = state["max_iterations"]
    budget = state["search_budget_remaining"]
    skeptic_challenges = state["skeptic_challenges_this_iteration"]

    if budget <= 0:
        return "report"
    if iteration >= max_iter:
        return "report"

    stable = graph.is_stable(
        state["stability_threshold_nodes"],
        state["stability_threshold_edges"],
        state["stability_window"],
    )
    # Only call stable if the Skeptic found nothing new this iteration
    if stable and skeptic_challenges == 0:
        return "report"

    return "contradiction_hunt"


# ── Graph assembly ────────────────────────────────────────────────────────────

def build_workflow() -> StateGraph:
    g = StateGraph(ResearchState)

    g.add_node("query_architect", node_query_architect)
    g.add_node("search", node_search)
    g.add_node("extract_and_graph", node_extract_and_graph)
    g.add_node("contradiction_hunt", node_contradiction_hunt)
    g.add_node("skeptic", node_skeptic)
    g.add_node("report", node_report)

    g.set_entry_point("query_architect")
    g.add_edge("query_architect", "search")
    g.add_edge("search", "extract_and_graph")
    g.add_conditional_edges(
        "extract_and_graph",
        should_continue,
        {"contradiction_hunt": "contradiction_hunt", "report": "report"},
    )
    g.add_edge("contradiction_hunt", "skeptic")
    g.add_edge("skeptic", "search")
    g.add_edge("report", END)

    return g.compile()


def run_research(query: str, output_dir: str = "outputs") -> dict:
    """Entry point for a research session. Returns paths to output files."""
    from pathlib import Path
    session_id = uuid.uuid4().hex[:8]
    state = initial_state(query, session_id)

    workflow = build_workflow()
    final_state = workflow.invoke(state)

    paths = save_outputs(
        report=final_state["final_report"],
        graph=final_state["evidence_graph"],
        session_id=session_id,
        output_dir=Path(output_dir),
        trace=final_state["trace"],
    )

    return {
        "session_id": session_id,
        "report_path": str(paths["report"]),
        "graph_path": str(paths["graph"]),
        "trace_path": str(paths.get("trace", "")),
        "iterations": final_state["iteration_count"],
        "claims": len(final_state["claims"]),
    }
