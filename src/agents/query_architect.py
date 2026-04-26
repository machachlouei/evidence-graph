from __future__ import annotations

import json
from typing import Optional

from src.utils.llm_client import chat
from src.utils.logging import ResearchTrace


SYSTEM = """\
You are a research strategist. Transform a user's natural language research question into a structured Research Brief that a multi-agent research system will execute.

Query types:
- "factual": Well-documented, low contradiction likelihood. Example: "What is RLHF?"
- "contradictory_sources": Literature actively disagrees on this. Example: "Does CoT improve reasoning?"
- "sparse_emerging": Few sources exist, field is new. Example: "Inference-time compute scaling"
- "multi_dimensional": Multiple distinct sub-domains. Example: "Map the multi-agent LLM landscape"

For contradiction likelihood, default to "high" for any question about LLM capabilities, prompting techniques, or training methods — these fields are reliably contested.

Return exactly this JSON (no markdown, no explanation):
{
  "original_query": "<exact user query>",
  "query_type": "<factual|contradictory_sources|sparse_emerging|multi_dimensional>",
  "core_question": "<the sharpened, unambiguous version of the question>",
  "sub_questions": ["<specific sub-question 1>", "..."],
  "scope_boundaries": {
    "include": ["<topic or source type to include>"],
    "exclude": ["<topic or source type to exclude>"]
  },
  "expected_difficulty": "<low|medium|high>",
  "contradiction_likelihood": "<low|medium|high>",
  "max_iterations": <integer 4-12>,
  "search_budget": <integer 20-60>
}

Sub-questions should be specific enough to drive individual search queries.
max_iterations: 4 for factual, 8 for contradictory_sources, 6 for sparse_emerging, 10 for multi_dimensional.
search_budget: scale with difficulty (20 for low, 40 for medium, 60 for high)."""


def build_research_brief(query: str, trace: Optional[ResearchTrace] = None) -> dict:
    """Turn a raw query into a structured Research Brief."""
    try:
        raw = chat(SYSTEM, f"Research question: {query}", max_tokens=1024)
        if raw.startswith("```"):
            raw = raw.split("```")[1].lstrip("json").strip()
        brief = json.loads(raw)
    except Exception as e:
        if trace:
            trace.tool_error("query_architect", "llm_call", str(e))
        # Fallback brief so the system can continue
        brief = {
            "original_query": query,
            "query_type": "contradictory_sources",
            "core_question": query,
            "sub_questions": [query],
            "scope_boundaries": {"include": [], "exclude": []},
            "expected_difficulty": "medium",
            "contradiction_likelihood": "high",
            "max_iterations": 8,
            "search_budget": 40,
        }

    # Convert sub-questions into initial search queries
    sub_questions = brief.get("sub_questions", [brief["core_question"]])
    brief["initial_search_queries"] = [
        {
            "query": sq,
            "source_types": ["web", "arxiv"],
            "priority": "high",
            "reason": "initial_coverage",
        }
        for sq in sub_questions
    ]

    return brief
