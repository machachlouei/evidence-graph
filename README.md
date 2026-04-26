# Deep Research Agent System

[![CI](https://github.com/machachlouei/evidence-graph/actions/workflows/ci.yml/badge.svg)](https://github.com/machachlouei/evidence-graph/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://github.com/machachlouei/evidence-graph/blob/main/LICENSE.md)

A multi-agent research system that takes a natural language question and produces a structured, evidence-backed report. The core idea: treat research as **graph construction**, not pipeline synthesis.

Instead of searching → summarizing → synthesizing (which papers over contradictions and stops when it has enough to write), this system builds an **Evidence Graph** — claims as nodes, typed relationships as edges — and only synthesizes when the graph is stable. Contradictions are first-class signals that drive targeted re-search, not noise to be smoothed over.

---

## How it works

```
Query → Query Architect → Search (web + arXiv)
      → Claim Extractor → Evidence Graph
      → [stable? → Report Generator]
      → [unstable → Contradiction Hunter → Skeptic → Search → ...]
```

**Query Architect** decomposes the query into sub-questions and sets the search budget based on difficulty.

**Claim Extractor** turns raw documents into atomic, source-tagged claims (one assertion per claim, so contradictions are detectable at the claim level rather than buried inside paragraph summaries).

**Evidence Graph** holds claims as nodes and classifies pairwise relationships: `supports`, `contradicts`, `qualifies`, `extends`. Confidence scores are computed structurally from graph topology — credibility-weighted supporting edges divided by total edges — not by asking an LLM "how confident are you?"

**Contradiction Hunter** finds unresolved `contradicts` edges and generates targeted search queries to resolve each one. The system explicitly pursues contradictions rather than resolving toward the majority view.

**Skeptic** red-teams the graph before each stability check: detects source monoculture (>70% of supporting sources sharing the same type) and generates disconfirmation searches against HIGH-confidence claims.

**Stopping condition** — first of three triggers wins: (1) graph stability (N consecutive iterations all below threshold for new nodes and contradiction edges, AND the Skeptic found nothing new), (2) `max_iterations` hard cap (default 8, safety ceiling), (3) search budget exhausted. Graph stability is the primary intended exit; the cap and budget are guardrails.

---

## Setup

Requires Python 3.11+.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

Copy `.env.example` to `.env` and fill in your API keys:

```bash
cp .env.example .env
```

Required keys:

| Key | Source | Free tier |
|-----|--------|-----------|
| `GOOGLE_API_KEY` | [Google AI Studio](https://aistudio.google.com/apikey) | 20 req/day (Gemini 2.5 Flash Lite) |
| `GROQ_API_KEY` | [Groq Console](https://console.groq.com/) | 14,400 req/day (llama-3.1-8b-instant + llama-3.3-70b-versatile) |
| `TAVILY_API_KEY` | [Tavily](https://tavily.com/) | 1,000 req/month |

Gemini handles quality tasks (claim extraction, report synthesis). Groq handles high-volume edge classification. When Gemini's daily quota is exhausted, the system automatically falls back to Groq for the remainder of the session.

---

## Usage

### Demo — end-to-end test with no web search (~18 LLM calls)

Runs the full pipeline on three pre-written CoT paper fixtures (Wei 2022, Kambhampati 2023, Min 2022). No API quota for Tavily. Uses ~4 Gemini calls and ~14 Groq calls.

```bash
python main.py demo
```

Output: report, graph JSON, and trace written to `outputs/demo/`.

### Research — full system on a live query

```bash
python main.py research "What are the risks of using synthetic data to train LLMs?"
python main.py research "Does RLHF reliably reduce hallucination?" --output outputs/rlhf
```

Runs the full Evidence Graph loop with live web + arXiv search. Budget and iteration cap are set by the Query Architect based on query difficulty.

### Baseline — naive pipeline for comparison

```bash
python main.py baseline "What are the risks of using synthetic data to train LLMs?"
```

Runs the ablation baseline: search → concatenate → single-shot synthesis. No contradiction detection, no iterative loop. Useful as a comparison against the full system.

### Ablation — both systems on the same query

```bash
python main.py ablation
python main.py ablation --query "Your custom query here"
```

Runs the Evidence Graph system and the baseline pipeline on the same query (defaults to the CoT contradictory-sources test case) and writes both reports to `outputs/ablation/`.

---

## Configuration

All loop parameters can be overridden via environment variables:

| Variable | Default | Meaning |
|----------|---------|---------|
| `RESEARCH_MAX_ITERATIONS` | `8` | Hard cap on research loop iterations |
| `RESEARCH_SEARCH_BUDGET` | `40` | Max individual search calls per session |
| `RESEARCH_STABILITY_THRESHOLD_NODES` | `3` | New nodes/iteration below which the graph is considered stable |
| `RESEARCH_STABILITY_THRESHOLD_EDGES` | `2` | New contradiction edges/iteration below which the graph is stable |
| `RESEARCH_STABILITY_WINDOW` | `5` | Consecutive iterations that must all be below threshold |

---

## Output files

Each session writes three files to the output directory:

- `report_<session>_<timestamp>.md` — structured research report with claims grouped by confidence (HIGH / MEDIUM / LOW / CONTESTED), unresolved contradictions surfaced explicitly, low-evidence areas flagged, and a quality self-assessment JSON at the end
- `graph_<session>_<timestamp>.json` — full Evidence Graph in node-link format (networkx-compatible)
- `trace_<session>.json` — structured event log of every search, claim extraction, edge detection, contradiction, and Skeptic action in the session

---

## Tests

```bash
pytest
```

19 unit tests covering the Evidence Graph data structure: node/edge operations, confidence scoring, stability detection, contradiction tracking, and serialization.

---

## Project layout

```
src/
  agents/
    query_architect.py      # Decomposes query into Research Brief
    claim_extractor.py      # Extracts atomic claims from documents
    graph_manager.py        # Adds claims to graph, detects edges
    contradiction_hunter.py # Resolves contradiction edges via targeted search
    skeptic.py              # Bias detection + disconfirmation search
    report_generator.py     # Synthesizes stable graph into report
  graph/
    evidence_graph.py       # Core data structure (networkx DiGraph)
    schemas.py              # Claim, Edge, RawDocument dataclasses + enums
  orchestration/
    workflow.py             # LangGraph stateful loop
    state.py                # ResearchState TypedDict
  tools/
    web_search.py           # Tavily web search
    arxiv_search.py         # arXiv academic search
    fetch_url.py            # Full document retrieval
  utils/
    llm_client.py           # Gemini + Groq routing with quota fallback
    logging.py              # ResearchTrace structured event log
  baseline/
    pipeline.py             # Naive pipeline for ablation comparison
  demo/
    fixtures.py             # Three pre-written CoT paper summaries
    run_demo.py             # Demo runner (no web search)
```
