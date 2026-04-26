from __future__ import annotations

import json
import uuid
from typing import Optional

from src.graph.schemas import CREDIBILITY_WEIGHTS, Claim, RawDocument, SourceType
from src.utils.llm_client import chat
from src.utils.logging import ResearchTrace


EXTRACTION_SYSTEM = """\
You are a precise claim extractor for a research system. Your job is to decompose a source document into atomic factual claims.

Rules for atomic claims:
1. Each claim must be a single, self-contained assertion — no compound sentences with "and" joining two separate facts.
2. Each claim must be specific and falsifiable — not vague opinions or summaries.
3. Each claim must be directly stated or clearly implied by the document — no inferences beyond what the text supports.
4. Separate empirical findings from speculative statements.
5. If two claims say the same thing, produce only one.
6. Do NOT merge claims that make distinct assertions even if they are related — keep them separate so contradictions remain detectable.

Return a JSON array of objects. Each object must have exactly these fields:
- "text": the claim as a complete sentence
- "is_empirical": true if based on measurement/experiment, false otherwise
- "is_speculative": true if the document marks it as uncertain/future work
- "domain_tags": array of 1-3 short topic tags (e.g. ["chain_of_thought", "arithmetic_reasoning"])

Return only the JSON array. No markdown fences, no explanation."""


def extract_claims(doc: RawDocument, trace: Optional[ResearchTrace] = None) -> list[Claim]:
    """Extract atomic claims from a document. Returns [] on LLM failure."""
    prompt = f"""Document title: {doc.title}
Source URL: {doc.url}
Publication date: {doc.publication_date}

Document content:
{doc.content[:6000]}

Extract all atomic factual claims from this document following the system instructions."""

    try:
        raw = chat(EXTRACTION_SYSTEM, prompt, max_tokens=2048)

        # Strip accidental markdown fences
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            # Groq sometimes returns unquoted string values — repair and retry
            from json_repair import repair_json
            parsed = json.loads(repair_json(raw))
    except Exception as e:
        if trace:
            trace.tool_error("claim_extractor", "llm_call", str(e))
        return []

    credibility = CREDIBILITY_WEIGHTS.get(doc.source_type, 0.4)
    claims = []
    for item in parsed[:8]:  # cap at 8 claims per doc; beyond this marginal claims add noise
        if not isinstance(item, dict) or not item.get("text"):
            continue
        claim_id = f"c_{uuid.uuid4().hex[:8]}"
        claims.append(Claim(
            claim_id=claim_id,
            text=item["text"].strip(),
            source_id=doc.doc_id,
            source_url=doc.url,
            source_type=doc.source_type,
            source_date=doc.publication_date,
            credibility_weight=credibility,
            domain_tags=item.get("domain_tags", []),
            is_empirical=bool(item.get("is_empirical", False)),
            is_speculative=bool(item.get("is_speculative", False)),
        ))

    if trace:
        trace.claims_extracted(doc.doc_id, len(claims))

    return claims
