from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.graph.evidence_graph import EvidenceGraph
from src.graph.schemas import ConfidenceLabel
from src.utils.llm_client import chat
from src.utils.logging import ResearchTrace


SYNTHESIS_SYSTEM = """\
You are a research report writer. You will be given a structured evidence graph — a set of claims with confidence scores and source citations — and must produce a clear, well-organized research report.

Critical rules:
1. ONLY report claims present in the provided graph. Do not add claims from your own knowledge.
2. Report confidence labels exactly as given — do not upgrade or downgrade them.
3. Surface ALL unresolved contradictions — do not smooth them over or pick a side.
4. Low-evidence areas (single source) must be flagged explicitly.
5. Use the exact confidence label (HIGH/MEDIUM/LOW/CONTESTED) from the graph.

Write in clear prose with a structured format. Each claim must cite its sources."""


def generate_report(
    query: str,
    graph: EvidenceGraph,
    research_brief: dict,
    trace: Optional[ResearchTrace] = None,
) -> str:
    """Generate the final research report from the stable Evidence Graph."""
    structure = graph.to_report_structure()

    # Build a compact graph summary to pass to the LLM
    graph_summary = _build_graph_summary(structure)

    prompt = f"""Research question: {query}

Evidence graph (stable — {structure['metadata']['total_claims']} claims, {structure['metadata']['total_contradiction_edges']} contradictions found):

{graph_summary}

Write a structured research report. Include:
1. Executive Summary (2-3 sentences)
2. Confidence Legend: HIGH >0.80 | MEDIUM 0.50-0.80 | LOW <0.50 | CONTESTED active contradiction
3. Key Findings (grouped by confidence, each with claim text, confidence score, evidence)
4. Unresolved Contradictions (each one fully surfaced with both positions)
5. Low-Evidence Areas (topics with single source or missing independent replication)
6. Research Metadata (numbers from the graph)"""

    try:
        report_body = chat(SYNTHESIS_SYSTEM, prompt, max_tokens=4096)
    except Exception as e:
        if trace:
            trace.tool_error("report_generator", "llm_call", str(e))
        report_body = _fallback_report(query, structure)

    # Append quality self-assessment
    qa = _quality_assessment(graph, structure, trace)
    return f"{report_body}\n\n---\n\n## System Quality Assessment\n\n```json\n{json.dumps(qa, indent=2)}\n```"


def _build_graph_summary(structure: dict) -> str:
    """Convert report structure to a compact text summary for the LLM prompt."""
    lines = []
    claims_by_conf = structure.get("claims_by_confidence", {})

    for label in ["HIGH", "MEDIUM", "LOW", "CONTESTED"]:
        claims = claims_by_conf.get(label, [])
        if not claims:
            continue
        lines.append(f"\n### {label} confidence claims:")
        for item in claims:
            claim = item["claim"]
            score = item["confidence_score"]
            sup_count = item["source_count"]
            low_ev = item["low_evidence"]
            lines.append(f'- [{score:.2f}] "{claim["text"]}"')
            lines.append(f'  Source: {claim["source_url"]} ({claim["source_date"]})')
            if item["contradicting_sources"]:
                for cs in item["contradicting_sources"]:
                    lines.append(f'  CONTRADICTED BY: {cs["source_url"]}')
            if low_ev:
                lines.append("  ⚠ LOW EVIDENCE — single source")

    contradictions = structure.get("unresolved_contradictions", [])
    if contradictions:
        lines.append("\n### Unresolved contradictions:")
        for c in contradictions:
            a = c["position_a"]
            b = c["position_b"]
            lines.append(f'- Position A: "{a["text"]}" ({a["source_url"]})')
            lines.append(f'  Position B: "{b["text"]}" ({b["source_url"]})')
            lines.append(f'  Status: {c["resolution_status"]}')

    return "\n".join(lines)


def _fallback_report(query: str, structure: dict) -> str:
    """Minimal structured report when LLM call fails — reads directly from graph structure."""
    lines = [f"# Research Report: {query}", "", "## ⚠ LLM synthesis unavailable — raw graph output", ""]
    meta = structure["metadata"]
    lines += [
        f"- Total claims: {meta['total_claims']}",
        f"- Contradiction edges: {meta['total_contradiction_edges']}",
        f"- Unresolved: {meta['unresolved_contradictions']}",
        "",
        "## Claims",
    ]
    for label, claims in structure.get("claims_by_confidence", {}).items():
        lines.append(f"\n### {label}")
        for item in claims:
            lines.append(f"- [{item['confidence_score']:.2f}] {item['claim']['text']}")
            lines.append(f"  Source: {item['claim']['source_url']}")
    return "\n".join(lines)


def _quality_assessment(
    graph: EvidenceGraph,
    structure: dict,
    trace: Optional[ResearchTrace] = None,
) -> dict:
    meta = structure["metadata"]
    unresolved = meta["unresolved_contradictions"]
    irreducible = meta["irreducible_contradictions"]
    total = meta["total_claims"]
    low_evidence = sum(
        1
        for claims in structure.get("claims_by_confidence", {}).values()
        for item in claims
        if item["low_evidence"]
    )

    overall_conf = (
        sum(graph.get_confidence(c.claim_id) for c in graph.all_claims()) / total
        if total > 0 else 0.0
    )

    return {
        "overall_confidence": round(overall_conf, 3),
        "total_claims": total,
        "contradiction_handling": {
            "found": meta["total_contradiction_edges"],
            "resolved": meta["total_contradiction_edges"] - unresolved - irreducible,
            "unresolved": unresolved,
            "irreducible": irreducible,
        },
        "low_evidence_claim_count": low_evidence,
        "trace_summary": trace.summary() if trace else {},
    }


def save_outputs(
    report: str,
    graph: EvidenceGraph,
    session_id: str,
    output_dir: Path,
    trace: Optional[ResearchTrace] = None,
) -> dict[str, Path]:
    """Write report, graph JSON, and trace to output_dir. Returns paths."""
    output_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    report_path = output_dir / f"report_{session_id}_{ts}.md"
    report_path.write_text(report, encoding="utf-8")

    graph_path = output_dir / f"graph_{session_id}_{ts}.json"
    graph_path.write_text(json.dumps(graph.to_node_link_data(), indent=2), encoding="utf-8")

    paths = {"report": report_path, "graph": graph_path}

    if trace:
        trace_path = trace.write(output_dir)
        paths["trace"] = trace_path

    return paths
