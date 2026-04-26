from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class SourceType(str, Enum):
    PEER_REVIEWED = "peer_reviewed"
    PREPRINT = "preprint"
    INSTITUTIONAL_BLOG = "institutional_blog"
    WEB = "web"


CREDIBILITY_WEIGHTS: dict[SourceType, float] = {
    SourceType.PEER_REVIEWED: 1.0,
    SourceType.PREPRINT: 0.8,
    SourceType.INSTITUTIONAL_BLOG: 0.6,
    SourceType.WEB: 0.4,
}


class EdgeRelationship(str, Enum):
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    QUALIFIES = "qualifies"
    EXTENDS = "extends"


class ResolutionStatus(str, Enum):
    UNRESOLVED = "unresolved"
    RESOLVED_FOR_SOURCE = "resolved_for_source"
    RESOLVED_FOR_TARGET = "resolved_for_target"
    RESOLVED_SCOPE = "resolved_scope"  # both correct in different conditions
    IRREDUCIBLE = "irreducible"


class ConfidenceLabel(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    CONTESTED = "CONTESTED"


@dataclass
class Claim:
    claim_id: str
    text: str
    source_id: str
    source_url: str
    source_type: SourceType
    source_date: str
    credibility_weight: float
    domain_tags: list[str] = field(default_factory=list)
    is_empirical: bool = False
    is_speculative: bool = False
    embedding: Optional[list[float]] = field(default=None, repr=False)

    def to_dict(self) -> dict:
        return {
            "claim_id": self.claim_id,
            "text": self.text,
            "source_id": self.source_id,
            "source_url": self.source_url,
            "source_type": self.source_type.value,
            "source_date": self.source_date,
            "credibility_weight": self.credibility_weight,
            "domain_tags": self.domain_tags,
            "is_empirical": self.is_empirical,
            "is_speculative": self.is_speculative,
        }


@dataclass
class Edge:
    edge_id: str
    source_claim_id: str
    target_claim_id: str
    relationship: EdgeRelationship
    confidence: float
    resolution_status: ResolutionStatus = ResolutionStatus.UNRESOLVED
    resolution_evidence: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "edge_id": self.edge_id,
            "source_claim_id": self.source_claim_id,
            "target_claim_id": self.target_claim_id,
            "relationship": self.relationship.value,
            "confidence": self.confidence,
            "resolution_status": self.resolution_status.value,
            "resolution_evidence": self.resolution_evidence,
        }


@dataclass
class RawDocument:
    doc_id: str
    url: str
    title: str
    content: str
    source_type: SourceType
    publication_date: str
    search_query: str
