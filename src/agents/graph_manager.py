from __future__ import annotations

import json
from typing import Optional

import numpy as np

from src.graph.evidence_graph import EvidenceGraph
from src.graph.schemas import Claim, Edge, EdgeRelationship, ResolutionStatus
from src.utils.llm_client import chat
from src.utils.logging import ResearchTrace

_embed_model: Optional[object] = None  # sentence_transformers.SentenceTransformer


def _get_embed_model():
    global _embed_model
    if _embed_model is None:
        from sentence_transformers import SentenceTransformer
        _embed_model = SentenceTransformer("all-MiniLM-L6-v2")
    return _embed_model


# ── Embedding helpers ────────────────────────────────────────────────────────

def _embed(text: str) -> np.ndarray:
    model = _get_embed_model()
    return model.encode(text, normalize_embeddings=True)


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b))


DEDUP_THRESHOLD = 0.92      # above this → candidate for merge
EDGE_CANDIDATE_THRESHOLD = 0.70  # raised from 0.55; at 2.4s/call only semantically
                                  # close pairs are worth classifying
MAX_EDGE_CANDIDATES = 5     # top-K most similar claims per new claim; keeps edge
                             # detection O(5n) regardless of graph size

# ── Edge classification ──────────────────────────────────────────────────────

EDGE_SYSTEM = """\
You are a precise relationship classifier for a research claim graph.

Given two research claims, determine the relationship from Claim A's perspective toward Claim B:

- "supports": Both claims assert the same thing or A provides evidence for B
- "contradicts": The claims cannot both be true — they make conflicting assertions
- "qualifies": A adds a scope limitation, condition, or nuance to B without contradicting it
- "extends": A builds on B as a premise, adding a new assertion
- "unrelated": The claims are about different topics or have no logical relationship

Be strict about "contradicts" — use it only when the claims make genuinely incompatible assertions, not just when they emphasize different aspects.

Return exactly this JSON:
{"relationship": "<one of the five values>", "confidence": <float 0.0-1.0>}

No explanation. No markdown."""


def _classify_edge(
    claim_a: Claim,
    claim_b: Claim,
    trace: Optional[ResearchTrace] = None,
) -> tuple[EdgeRelationship | None, float]:
    """Use LLM to classify the relationship between two claims. Returns (None, 0) on failure."""
    prompt = f"""Claim A: {claim_a.text}

Claim B: {claim_b.text}

Classify the relationship of Claim A toward Claim B."""

    try:
        raw = chat(EDGE_SYSTEM, prompt, max_tokens=64, task_type="edge")
        if raw.startswith("```"):
            raw = raw.split("```")[1].lstrip("json").strip()
        parsed = json.loads(raw)
        rel_str = parsed.get("relationship", "unrelated")
        confidence = float(parsed.get("confidence", 0.0))

        try:
            rel = EdgeRelationship(rel_str)
        except ValueError:
            rel = None

        return rel, confidence
    except RuntimeError:
        # Daily quota exhausted — re-raise so the workflow surfaces it clearly
        raise
    except Exception as e:
        if trace:
            trace.tool_error("graph_manager", "edge_classify", str(e))
        return None, 0.0


# ── Main interface ───────────────────────────────────────────────────────────

def add_claims_to_graph(
    new_claims: list[Claim],
    graph: EvidenceGraph,
    trace: Optional[ResearchTrace] = None,
) -> tuple[int, int]:
    """Add new claims to the Evidence Graph, detecting edges against existing claims.

    Returns (nodes_added, contradiction_edges_added).
    Embedding pre-filter is applied before every LLM edge classification call to
    keep the O(n²) cost tractable at MVP scale.
    """
    existing = graph.all_claims()
    nodes_added = 0
    contradiction_edges_added = 0

    # Compute embeddings for existing claims (cached on Claim object)
    for c in existing:
        if c.embedding is None:
            c.embedding = _embed(c.text).tolist()

    for new_claim in new_claims:
        # Check for semantic duplicates against existing claims
        new_emb = _embed(new_claim.text)
        new_claim.embedding = new_emb.tolist()

        is_duplicate = False
        for existing_claim in existing:
            if existing_claim.embedding is None:
                continue
            sim = _cosine_similarity(new_emb, np.array(existing_claim.embedding))
            if sim >= DEDUP_THRESHOLD:
                # Treat as duplicate — skip adding, but could merge source edges in full design
                is_duplicate = True
                break

        if is_duplicate:
            continue

        graph.add_claim(new_claim)
        nodes_added += 1

        # Edge detection: embedding pre-filter then top-K by similarity.
        # Taking all claims above threshold is O(n²) × 2.4s/call = hours at scale.
        # Top-K keeps it O(n) and targets the most semantically relevant pairs.
        scored = [
            (c, _cosine_similarity(new_emb, np.array(c.embedding)))
            for c in existing
            if c.embedding is not None
        ]
        candidates = [
            c for c, sim in sorted(scored, key=lambda x: x[1], reverse=True)
            if sim >= EDGE_CANDIDATE_THRESHOLD
        ][:MAX_EDGE_CANDIDATES]

        if trace and candidates:
            trace.log("graph_manager", "edge_candidates", {
                "new_claim": new_claim.claim_id,
                "candidates": len(candidates),
                "existing_total": len(existing),
            })

        for existing_claim in candidates:
            rel, conf = _classify_edge(new_claim, existing_claim, trace)
            if rel is None:
                continue
            if conf < 0.60:
                continue  # low-confidence classification → skip to avoid noise

            edge = Edge(
                edge_id=graph.new_edge_id(),
                source_claim_id=new_claim.claim_id,
                target_claim_id=existing_claim.claim_id,
                relationship=rel,
                confidence=conf,
            )
            graph.add_edge(edge)

            if trace:
                trace.edge_detected(
                    new_claim.claim_id, existing_claim.claim_id, rel.value, conf
                )

            if rel == EdgeRelationship.CONTRADICTS:
                contradiction_edges_added += 1

        # Update existing list for next iteration
        existing.append(new_claim)

    return nodes_added, contradiction_edges_added
