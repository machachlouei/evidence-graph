import pytest

from src.graph.evidence_graph import EvidenceGraph
from src.graph.schemas import (
    Claim,
    ConfidenceLabel,
    Edge,
    EdgeRelationship,
    ResolutionStatus,
    SourceType,
)


def make_claim(cid: str, source_type: SourceType = SourceType.PEER_REVIEWED, credibility: float = 1.0) -> Claim:
    return Claim(
        claim_id=cid,
        text=f"Claim text for {cid}",
        source_id=f"src_{cid}",
        source_url=f"https://example.com/{cid}",
        source_type=source_type,
        source_date="2024-01-01",
        credibility_weight=credibility,
    )


def make_edge(eid: str, src: str, tgt: str, rel: EdgeRelationship, confidence: float = 0.9) -> Edge:
    return Edge(
        edge_id=eid,
        source_claim_id=src,
        target_claim_id=tgt,
        relationship=rel,
        confidence=confidence,
    )


class TestEvidenceGraphBasics:
    def test_add_and_retrieve_claim(self):
        g = EvidenceGraph()
        c = make_claim("c1")
        g.add_claim(c)
        assert g.get_claim("c1") is c
        assert g.claim_count() == 1

    def test_add_and_retrieve_edge(self):
        g = EvidenceGraph()
        g.add_claim(make_claim("c1"))
        g.add_claim(make_claim("c2"))
        e = make_edge("e1", "c1", "c2", EdgeRelationship.SUPPORTS)
        g.add_edge(e)
        assert len(g.all_edges()) == 1

    def test_get_unresolved_contradictions(self):
        g = EvidenceGraph()
        g.add_claim(make_claim("c1"))
        g.add_claim(make_claim("c2"))
        g.add_edge(make_edge("e1", "c1", "c2", EdgeRelationship.CONTRADICTS))
        assert len(g.get_unresolved_contradictions()) == 1

    def test_resolve_contradiction(self):
        g = EvidenceGraph()
        g.add_claim(make_claim("c1"))
        g.add_claim(make_claim("c2"))
        g.add_claim(make_claim("c3"))
        g.add_edge(make_edge("e1", "c1", "c2", EdgeRelationship.CONTRADICTS))
        g.resolve_contradiction("e1", ResolutionStatus.RESOLVED_FOR_SOURCE, ["c3"])
        assert len(g.get_unresolved_contradictions()) == 0

    def test_irreducible_contradiction_not_in_unresolved(self):
        g = EvidenceGraph()
        g.add_claim(make_claim("c1"))
        g.add_claim(make_claim("c2"))
        g.add_edge(make_edge("e1", "c1", "c2", EdgeRelationship.CONTRADICTS))
        g.resolve_contradiction("e1", ResolutionStatus.IRREDUCIBLE, [])
        assert len(g.get_unresolved_contradictions()) == 0
        assert len(g.get_irreducible_contradictions()) == 1


class TestConfidenceScoring:
    def test_single_claim_full_confidence(self):
        g = EvidenceGraph()
        g.add_claim(make_claim("c1"))
        assert g.get_confidence("c1") == 1.0

    def test_supporting_source_increases_confidence(self):
        g = EvidenceGraph()
        g.add_claim(make_claim("c1"))
        g.add_claim(make_claim("c2"))
        g.add_edge(make_edge("e1", "c2", "c1", EdgeRelationship.SUPPORTS))
        conf = g.get_confidence("c1")
        assert conf == 1.0  # both are peer_reviewed weight 1.0 → 2/2

    def test_contradicting_source_lowers_confidence(self):
        g = EvidenceGraph()
        g.add_claim(make_claim("c1", credibility=1.0))
        g.add_claim(make_claim("c2", credibility=1.0))
        g.add_edge(make_edge("e1", "c2", "c1", EdgeRelationship.CONTRADICTS))
        conf = g.get_confidence("c1")
        assert conf == 0.5  # c1 weight 1.0 / (c1 1.0 + c2 1.0)

    def test_credibility_weighting(self):
        g = EvidenceGraph()
        g.add_claim(make_claim("c1", SourceType.PEER_REVIEWED, 1.0))
        g.add_claim(make_claim("c2", SourceType.WEB, 0.4))
        g.add_edge(make_edge("e1", "c2", "c1", EdgeRelationship.CONTRADICTS))
        conf = g.get_confidence("c1")
        # c1=1.0 support / (c1=1.0 + c2=0.4) = 1.0/1.4 ≈ 0.7143
        assert abs(conf - round(1.0 / 1.4, 4)) < 1e-4

    def test_confidence_label_high(self):
        g = EvidenceGraph()
        g.add_claim(make_claim("c1"))
        assert g.get_confidence_label("c1") == ConfidenceLabel.HIGH

    def test_confidence_label_contested(self):
        g = EvidenceGraph()
        g.add_claim(make_claim("c1"))
        g.add_claim(make_claim("c2"))
        g.add_edge(make_edge("e1", "c2", "c1", EdgeRelationship.CONTRADICTS))
        assert g.get_confidence_label("c1") == ConfidenceLabel.CONTESTED

    def test_confidence_label_low(self):
        g = EvidenceGraph()
        g.add_claim(make_claim("c1", credibility=1.0))
        for i in range(4):
            cid = f"contra_{i}"
            g.add_claim(make_claim(cid, credibility=1.0))
            edge = make_edge(f"e_{i}", cid, "c1", EdgeRelationship.CONTRADICTS)
            g.add_edge(edge)
            g.resolve_contradiction(f"e_{i}", ResolutionStatus.RESOLVED_FOR_SOURCE, [])
        # no unresolved contradictions, but score is 1/(1+4)=0.2 → LOW
        assert g.get_confidence_label("c1") == ConfidenceLabel.LOW


class TestStability:
    def test_not_stable_with_insufficient_window(self):
        g = EvidenceGraph()
        g.record_iteration(10, 5)
        assert not g.is_stable(threshold_nodes=3, threshold_edges=2, window=5)

    def test_stable_when_window_below_threshold(self):
        g = EvidenceGraph()
        for _ in range(5):
            g.record_iteration(1, 0)
        assert g.is_stable(threshold_nodes=3, threshold_edges=2, window=5)

    def test_not_stable_with_spike(self):
        g = EvidenceGraph()
        for i in range(4):
            g.record_iteration(1, 0)
        g.record_iteration(5, 3)  # spike in last window entry
        assert not g.is_stable(threshold_nodes=3, threshold_edges=2, window=5)


class TestSerialization:
    def test_to_node_link_data_roundtrip(self):
        g = EvidenceGraph()
        g.add_claim(make_claim("c1"))
        g.add_claim(make_claim("c2"))
        g.add_edge(make_edge("e1", "c1", "c2", EdgeRelationship.SUPPORTS))
        data = g.to_node_link_data()
        assert "nodes" in data
        assert "edges" in data or "links" in data  # key renamed in networkx 3.4

    def test_to_report_structure_keys(self):
        g = EvidenceGraph()
        g.add_claim(make_claim("c1"))
        report = g.to_report_structure()
        assert "claims_by_confidence" in report
        assert "unresolved_contradictions" in report
        assert "metadata" in report

    def test_high_confidence_shows_in_report(self):
        g = EvidenceGraph()
        g.add_claim(make_claim("c1"))
        report = g.to_report_structure()
        assert "HIGH" in report["claims_by_confidence"]

    def test_low_evidence_flag(self):
        g = EvidenceGraph()
        g.add_claim(make_claim("c1"))
        report = g.to_report_structure()
        high_claims = report["claims_by_confidence"]["HIGH"]
        assert high_claims[0]["low_evidence"] is True  # only 1 source
