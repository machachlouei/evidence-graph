from __future__ import annotations

"""End-to-end demo runner using pre-written fixtures instead of live search.

LLM calls made:
  - Claim extraction:   3 docs × 1 Gemini call = 3
  - Edge detection:     ~15 claims → ~10 pairs pass filter → 10 Groq calls
  - Report generation:  1 Gemini call
  Total: ~14–18 LLM calls
"""

import uuid
from pathlib import Path

from src.agents.claim_extractor import extract_claims
from src.agents.graph_manager import add_claims_to_graph
from src.agents.report_generator import generate_report, save_outputs
from src.demo.fixtures import FIXTURES
from src.graph.evidence_graph import EvidenceGraph
from src.orchestration.state import initial_state
from src.utils.logging import ResearchTrace


DEMO_QUERY = (
    "Is chain-of-thought prompting an effective reasoning strategy for LLMs, "
    "or does it primarily improve output formatting? "
    "Find the fault lines and explain what accounts for the conflicting results."
)

DEMO_BRIEF = {
    "original_query": DEMO_QUERY,
    "query_type": "contradictory_sources",
    "core_question": DEMO_QUERY,
    "sub_questions": [],
}


def run_demo(output_dir: str = "outputs/demo") -> dict:
    session_id = f"demo_{uuid.uuid4().hex[:6]}"
    trace = ResearchTrace(query=DEMO_QUERY, session_id=session_id)
    graph = EvidenceGraph()

    print(f"  Session: {session_id}")
    print(f"  Documents: {len(FIXTURES)} fixtures (no web search)")

    # ── Step 1: Extract claims from each fixture ──────────────────────────────
    all_claims = []
    for doc in FIXTURES:
        print(f"  Extracting claims: {doc.title[:60]}...")
        claims = extract_claims(doc, trace)
        print(f"    → {len(claims)} claims extracted")
        all_claims.extend(claims)

    print(f"  Total claims: {len(all_claims)}")

    # ── Step 2: Add to graph with edge detection ──────────────────────────────
    print("  Running edge detection (Groq)...")
    nodes_added, contradiction_edges = add_claims_to_graph(all_claims, graph, trace)
    graph.record_iteration(nodes_added, contradiction_edges)

    unresolved = graph.get_unresolved_contradictions()
    print(f"  Graph: {nodes_added} nodes, {contradiction_edges} contradiction edges, "
          f"{len(unresolved)} unresolved")

    # ── Step 3: Generate report ───────────────────────────────────────────────
    print("  Generating report (Gemini)...")
    report = generate_report(DEMO_QUERY, graph, DEMO_BRIEF, trace)

    # ── Step 4: Save outputs ──────────────────────────────────────────────────
    paths = save_outputs(report, graph, session_id, Path(output_dir), trace)
    print(f"  Report:  {paths['report']}")
    print(f"  Graph:   {paths['graph']}")
    print(f"  Trace:   {paths.get('trace', 'n/a')}")

    return {
        "session_id": session_id,
        "claims": len(all_claims),
        "nodes": nodes_added,
        "contradiction_edges": contradiction_edges,
        "unresolved_contradictions": len(unresolved),
        "report_path": str(paths["report"]),
        "graph_path": str(paths["graph"]),
        "trace_summary": trace.summary(),
    }
