from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional


@dataclass
class TraceEvent:
    timestamp: float
    component: str          # e.g. "query_architect", "search_agent", "graph_manager"
    event: str              # e.g. "search_issued", "claim_extracted", "edge_detected"
    data: dict = field(default_factory=dict)
    error: Optional[str] = None


class ResearchTrace:
    """Structured execution trace for a single research session.

    Written alongside every report output so any bad report can be fully
    reconstructed from first principles.
    """

    def __init__(self, query: str, session_id: str):
        self.query = query
        self.session_id = session_id
        self.started_at = time.time()
        self.events: list[TraceEvent] = []

    def log(
        self,
        component: str,
        event: str,
        data: Optional[dict] = None,
        error: Optional[str] = None,
    ) -> None:
        self.events.append(
            TraceEvent(
                timestamp=time.time(),
                component=component,
                event=event,
                data=data or {},
                error=error,
            )
        )

    # ── Convenience helpers ──────────────────────────────────────────────────

    def search_issued(self, query: str, source_type: str) -> None:
        self.log("search_agent", "search_issued", {"query": query, "source_type": source_type})

    def search_result(self, query: str, source_type: str, result_count: int, latency_ms: float) -> None:
        self.log(
            "search_agent", "search_result",
            {"query": query, "source_type": source_type, "result_count": result_count, "latency_ms": latency_ms},
        )

    def search_failed(self, query: str, source_type: str, reason: str) -> None:
        self.log("search_agent", "search_failed", {"query": query, "source_type": source_type}, error=reason)

    def claims_extracted(self, doc_id: str, claim_count: int) -> None:
        self.log("claim_extractor", "claims_extracted", {"doc_id": doc_id, "claim_count": claim_count})

    def edge_detected(self, src_claim: str, tgt_claim: str, relationship: str, confidence: float) -> None:
        self.log(
            "graph_manager", "edge_detected",
            {"src": src_claim, "tgt": tgt_claim, "relationship": relationship, "confidence": confidence},
        )

    def contradiction_found(self, edge_id: str, src_text: str, tgt_text: str) -> None:
        self.log("contradiction_hunter", "contradiction_found", {"edge_id": edge_id, "src": src_text, "tgt": tgt_text})

    def contradiction_resolved(self, edge_id: str, status: str) -> None:
        self.log("contradiction_hunter", "contradiction_resolved", {"edge_id": edge_id, "status": status})

    def skeptic_bias_flagged(self, claim_id: str, bias_type: str, detail: str) -> None:
        self.log("skeptic", "bias_flagged", {"claim_id": claim_id, "bias_type": bias_type, "detail": detail})

    def skeptic_disconfirmation(self, claim_id: str, query: str, found: bool) -> None:
        self.log("skeptic", "disconfirmation_search", {"claim_id": claim_id, "query": query, "found_challenge": found})

    def stability_check(self, iteration: int, new_nodes: int, new_edges: int, is_stable: bool) -> None:
        self.log(
            "graph_manager", "stability_check",
            {"iteration": iteration, "new_nodes": new_nodes, "new_edges": new_edges, "is_stable": is_stable},
        )

    def tool_error(self, component: str, tool: str, error: str) -> None:
        self.log(component, "tool_error", {"tool": tool}, error=error)

    # ── Serialization ────────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "query": self.query,
            "started_at": self.started_at,
            "duration_seconds": round(time.time() - self.started_at, 2),
            "event_count": len(self.events),
            "events": [
                {
                    "timestamp": e.timestamp,
                    "component": e.component,
                    "event": e.event,
                    "data": e.data,
                    **({"error": e.error} if e.error else {}),
                }
                for e in self.events
            ],
        }

    def write(self, output_dir: Path) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / f"trace_{self.session_id}.json"
        path.write_text(json.dumps(self.to_dict(), indent=2))
        return path

    def summary(self) -> dict:
        """Concise summary for the report metadata block."""
        errors = [e for e in self.events if e.error]
        search_events = [e for e in self.events if e.event == "search_issued"]
        return {
            "session_id": self.session_id,
            "duration_seconds": round(time.time() - self.started_at, 2),
            "total_searches": len(search_events),
            "total_events": len(self.events),
            "errors": [{"component": e.component, "error": e.error} for e in errors],
        }
