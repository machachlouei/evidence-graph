from __future__ import annotations

import uuid
from collections import defaultdict

import networkx as nx

from src.graph.schemas import (
    CREDIBILITY_WEIGHTS,
    Claim,
    ConfidenceLabel,
    Edge,
    EdgeRelationship,
    ResolutionStatus,
    SourceType,
)


class EvidenceGraph:
    def __init__(self):
        self._graph = nx.DiGraph()
        self._claims: dict[str, Claim] = {}
        self._edges: dict[str, Edge] = {}
        # Track new nodes/edges per iteration for stability check
        self._iteration_new_nodes: list[int] = []
        self._iteration_new_contradiction_edges: list[int] = []

    # ── Mutation ────────────────────────────────────────────────────────────

    def add_claim(self, claim: Claim) -> None:
        self._claims[claim.claim_id] = claim
        self._graph.add_node(claim.claim_id, **claim.to_dict())

    def add_edge(self, edge: Edge) -> None:
        self._edges[edge.edge_id] = edge
        self._graph.add_edge(
            edge.source_claim_id,
            edge.target_claim_id,
            **edge.to_dict(),
        )

    def resolve_contradiction(
        self,
        edge_id: str,
        status: ResolutionStatus,
        evidence_claim_ids: list[str],
    ) -> None:
        if edge_id not in self._edges:
            return
        edge = self._edges[edge_id]
        edge.resolution_status = status
        edge.resolution_evidence = evidence_claim_ids
        self._graph[edge.source_claim_id][edge.target_claim_id]["resolution_status"] = status.value
        self._graph[edge.source_claim_id][edge.target_claim_id]["resolution_evidence"] = evidence_claim_ids

    # ── Stability tracking ──────────────────────────────────────────────────

    def record_iteration(self, new_nodes: int, new_contradiction_edges: int) -> None:
        self._iteration_new_nodes.append(new_nodes)
        self._iteration_new_contradiction_edges.append(new_contradiction_edges)

    def is_stable(self, threshold_nodes: int = 3, threshold_edges: int = 2, window: int = 5) -> bool:
        """Graph is stable when recent iterations have added fewer than threshold new nodes/edges."""
        if len(self._iteration_new_nodes) < window:
            return False
        recent_nodes = self._iteration_new_nodes[-window:]
        recent_edges = self._iteration_new_contradiction_edges[-window:]
        return max(recent_nodes) < threshold_nodes and max(recent_edges) < threshold_edges

    # ── Queries ─────────────────────────────────────────────────────────────

    def get_claim(self, claim_id: str) -> Claim | None:
        return self._claims.get(claim_id)

    def all_claims(self) -> list[Claim]:
        return list(self._claims.values())

    def all_edges(self) -> list[Edge]:
        return list(self._edges.values())

    def get_unresolved_contradictions(self) -> list[Edge]:
        return [
            e for e in self._edges.values()
            if e.relationship == EdgeRelationship.CONTRADICTS
            and e.resolution_status == ResolutionStatus.UNRESOLVED
        ]

    def get_irreducible_contradictions(self) -> list[Edge]:
        return [
            e for e in self._edges.values()
            if e.relationship == EdgeRelationship.CONTRADICTS
            and e.resolution_status == ResolutionStatus.IRREDUCIBLE
        ]

    def get_supporting_edges(self, claim_id: str) -> list[Edge]:
        return [
            e for e in self._edges.values()
            if e.target_claim_id == claim_id
            and e.relationship == EdgeRelationship.SUPPORTS
        ]

    def get_contradicting_edges(self, claim_id: str) -> list[Edge]:
        return [
            e for e in self._edges.values()
            if (e.target_claim_id == claim_id or e.source_claim_id == claim_id)
            and e.relationship == EdgeRelationship.CONTRADICTS
        ]

    def get_confidence(self, claim_id: str) -> float:
        """Structural confidence: credibility-weighted supporting / (supporting + contradicting)."""
        claim = self._claims.get(claim_id)
        if not claim:
            return 0.0

        support_weight = claim.credibility_weight  # the claim itself counts
        total_weight = claim.credibility_weight

        for edge in self._edges.values():
            other_id = None
            if edge.target_claim_id == claim_id and edge.relationship == EdgeRelationship.SUPPORTS:
                other_id = edge.source_claim_id
            elif edge.source_claim_id == claim_id and edge.relationship == EdgeRelationship.SUPPORTS:
                other_id = edge.target_claim_id

            if other_id:
                other = self._claims.get(other_id)
                if other:
                    support_weight += other.credibility_weight
                    total_weight += other.credibility_weight

            if edge.relationship == EdgeRelationship.CONTRADICTS:
                contra_id = (
                    edge.source_claim_id if edge.target_claim_id == claim_id else edge.target_claim_id
                )
                contra = self._claims.get(contra_id)
                if contra:
                    total_weight += contra.credibility_weight

        if total_weight == 0:
            return 0.0
        return round(support_weight / total_weight, 4)

    def get_confidence_label(self, claim_id: str) -> ConfidenceLabel:
        contradicting = self.get_contradicting_edges(claim_id)
        unresolved = [
            e for e in contradicting if e.resolution_status == ResolutionStatus.UNRESOLVED
        ]
        if unresolved:
            return ConfidenceLabel.CONTESTED

        score = self.get_confidence(claim_id)
        if score >= 0.80:
            return ConfidenceLabel.HIGH
        if score >= 0.50:
            return ConfidenceLabel.MEDIUM
        return ConfidenceLabel.LOW

    def get_high_confidence_claims(self, threshold: float = 0.80) -> list[Claim]:
        return [
            c for c in self._claims.values()
            if self.get_confidence(c.claim_id) >= threshold
            and not self.get_contradicting_edges(c.claim_id)
        ]

    def get_source_distribution(self, claim_id: str) -> dict:
        """Return source URLs supporting a claim, for Skeptic bias detection."""
        sources = []
        claim = self._claims.get(claim_id)
        if claim:
            sources.append({
                "url": claim.source_url,
                "source_type": claim.source_type.value,
                "date": claim.source_date,
            })
        for edge in self.get_supporting_edges(claim_id):
            other = self._claims.get(edge.source_claim_id)
            if other:
                sources.append({
                    "url": other.source_url,
                    "source_type": other.source_type.value,
                    "date": other.source_date,
                })
        return {"claim_id": claim_id, "sources": sources}

    def claim_count(self) -> int:
        return len(self._claims)

    def contradiction_edge_count(self) -> int:
        return sum(
            1 for e in self._edges.values()
            if e.relationship == EdgeRelationship.CONTRADICTS
        )

    # ── Serialization ────────────────────────────────────────────────────────

    def to_node_link_data(self) -> dict:
        return nx.node_link_data(self._graph)

    def to_report_structure(self) -> dict:
        """Structured summary for the Report Generator to consume."""
        claims_by_confidence: dict[str, list[dict]] = defaultdict(list)

        for claim in self._claims.values():
            label = self.get_confidence_label(claim.claim_id).value
            score = self.get_confidence(claim.claim_id)
            supporting = self.get_supporting_edges(claim.claim_id)
            contradicting = self.get_contradicting_edges(claim.claim_id)

            claims_by_confidence[label].append({
                "claim": claim.to_dict(),
                "confidence_score": score,
                "confidence_label": label,
                "supporting_sources": [
                    self._claims[e.source_claim_id].to_dict()
                    for e in supporting
                    if e.source_claim_id in self._claims
                ],
                "contradicting_sources": [
                    self._claims[
                        e.source_claim_id if e.target_claim_id == claim.claim_id else e.target_claim_id
                    ].to_dict()
                    for e in contradicting
                    if (e.source_claim_id if e.target_claim_id == claim.claim_id else e.target_claim_id)
                    in self._claims
                ],
                "source_count": 1 + len(supporting),
                "low_evidence": (1 + len(supporting)) < 2,
            })

        unresolved = self.get_unresolved_contradictions()
        irreducible = self.get_irreducible_contradictions()

        contradictions_report = []
        seen_pairs: set[frozenset] = set()
        for edge in unresolved + irreducible:
            pair = frozenset([edge.source_claim_id, edge.target_claim_id])
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)
            src = self._claims.get(edge.source_claim_id)
            tgt = self._claims.get(edge.target_claim_id)
            if src and tgt:
                contradictions_report.append({
                    "edge_id": edge.edge_id,
                    "position_a": src.to_dict(),
                    "position_b": tgt.to_dict(),
                    "resolution_status": edge.resolution_status.value,
                    "resolution_evidence": edge.resolution_evidence,
                })

        return {
            "claims_by_confidence": dict(claims_by_confidence),
            "unresolved_contradictions": contradictions_report,
            "metadata": {
                "total_claims": self.claim_count(),
                "total_contradiction_edges": self.contradiction_edge_count(),
                "unresolved_contradictions": len(self.get_unresolved_contradictions()),
                "irreducible_contradictions": len(irreducible),
                "iterations_recorded": len(self._iteration_new_nodes),
            },
        }

    def new_edge_id(self) -> str:
        return f"e_{uuid.uuid4().hex[:8]}"
