# Deep Research Agent System — Full Design Document

**Author:** Matt Achachlouei 
**Version:** 1.0  
**Date:** April 2026  
**Track:** Agentic AI Research & Engineering

---

## Table of Contents

1. [Problem Statement & Design Philosophy](#1-problem-statement--design-philosophy)
2. [Requirements Register](#2-requirements-register)
3. [Requirements Traceability Matrix](#3-requirements-traceability-matrix)
4. [Core Insight: Why Everything Else Is Wrong](#4-core-insight-why-everything-else-is-wrong)
5. [Full System Architecture](#5-full-system-architecture)
6. [Component Deep Dives](#6-component-deep-dives)
7. [The Evidence Graph — Core Data Structure](#7-the-evidence-graph--core-data-structure)
8. [Memory & Context Management](#8-memory--context-management)
9. [Tool Design & Failure Handling](#9-tool-design--failure-handling)
10. [Quality, Reliability & Honesty](#10-quality-reliability--honesty)
11. [Evaluation Framework](#11-evaluation-framework)
12. [Architecture Alternatives Considered](#12-architecture-alternatives-considered)
13. [Trade-off Study (The "System Balance")](#13-trade-off-study-the-system-balance)
14. [Production Concerns](#14-production-concerns)
15. [MVP Scope & Prioritization](#15-mvp-scope--prioritization)
16. [Known Weaknesses & Future Work](#16-known-weaknesses--future-work)

---

## 1. Problem Statement & Design Philosophy

### The Task

Build a system that takes a natural language research question and produces a structured, evidence-backed research report. The system must:

- Iteratively investigate the topic using real external sources
- Handle contradictions between sources without papering them over
- Synthesize across multiple research threads
- Produce output that separates claims from evidence and indicates confidence and source agreement

### What Makes This Hard

This is not a retrieval problem. It is an **investigation problem**.

Retrieval assumes you know what you are looking for. Research assumes you do not. The shape of the question changes as evidence accumulates. Early findings reveal what you should have asked. Contradictions reveal where you need to look harder. The system cannot know in advance which sources matter or how many are enough.

Three failure modes define the design space:

**`FM-01` — Premature Synthesis**  
The system finds enough text to write a plausible report and stops. It synthesizes toward the most available evidence, not the most accurate. Minority views disappear. Contradictions get smoothed over. The report sounds confident but represents a subset of what is actually known.

**`FM-02` — Ungrounded Claims**  
The system generates plausible-sounding claims that no source actually supports. Without structural enforcement of source grounding, citations are retrofitted to conclusions rather than derived from evidence.

**`FM-03` — Opaque Confidence**  
The system reports all claims with equal certainty regardless of how contested they are in the literature. The reader cannot distinguish "four independent studies agree" from "one preprint speculated."

### Design Principle

Every architectural decision in this document exists to address at least one of FM-01, FM-02, or FM-03. If a component does not address a requirement, it does not belong in the system.

---

## 2. Requirements Register

All requirements are derived directly from the problem statement and project specification. Every component in this document must satisfy at least one requirement listed here. Requirements not addressed by any component indicate a design gap.

### Failure Mode Requirements

| ID | Requirement | Derived From |
|---|---|---|
| **FM-01** | The system must not produce a final report until the Evidence Graph has reached stability — defined as fewer than K new claim nodes or contradiction edges added across N consecutive search iterations. | Problem Statement §1 |
| **FM-02** | Every claim in the final report must be traceable to at least one source node in the Evidence Graph. Claims without source edges must not appear in any report output. | Problem Statement §1 |
| **FM-03** | Confidence scores for all claims must be derived structurally from Evidence Graph topology — ratio of supporting to contradicting source edges, weighted by credibility. LLM-subjective confidence assignment is not permitted. | Problem Statement §1 |

### Quality Requirements

| ID | Requirement | Derived From |
|---|---|---|
| **QR-01** | The system must detect and explicitly surface all contradiction edges present in the Evidence Graph. Unresolved contradictions must appear in the final report — not be silently resolved toward the majority view. | Task Brief |
| **QR-02** | The system must actively search for disconfirming evidence against HIGH-confidence claims before declaring graph stability. Internal consistency of the graph is not sufficient — the graph must have been adversarially challenged. | Task Brief |
| **QR-03** | The stopping condition must be content-driven. Termination on a fixed iteration count is not permitted. The system halts only when the Evidence Graph meets the FM-01 stability threshold or when the search budget is exhausted. | Task Brief |
| **QR-04** | Every claim object must carry a full provenance chain — source URL, source type, publication date, and credibility weight — preserved from extraction through final report output and never discarded. | Task Brief |
| **QR-05** | Every tool failure must be logged and propagated to report metadata. The system must degrade gracefully — continuing with reduced confidence rather than crashing — when any individual tool or source is unavailable. | Task Brief |

### System Output Requirements

| ID | Requirement | Derived From |
|---|---|---|
| **SR-01** | The system must retrieve evidence from at least one real external data source per research session. Static or synthetic corpora are not sufficient. | Projcet Spec §2.2 |
| **SR-02** | The final report must structurally separate claims from evidence. Claims and their supporting sources must be presented as distinct, linked elements — not interleaved prose. | Project Spec §2.2 |
| **SR-03** | Every claim in the final report must carry an explicit confidence level (HIGH / MEDIUM / LOW / CONTESTED) derived per FM-03. | Project Spec §2.2 |
| **SR-04** | The final report must indicate source agreement for each claim — the count of supporting versus contradicting sources and whether the claim is contested in the literature. | Project Spec §2.2 |

---

## 3. Requirements Traceability Matrix

Each ✓ indicates the component is a primary satisfier of that requirement. A component with no checkmarks in this table does not belong in the system.

| Component | FM-01 | FM-02 | FM-03 | QR-01 | QR-02 | QR-03 | QR-04 | QR-05 | SR-01 | SR-02 | SR-03 | SR-04 |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| Query Architect | ✓ | | | | | | | | | | | |
| Search Agent | ✓ | | | | | | | ✓ | ✓ | | | |
| Claim Extractor | | ✓ | | | | | ✓ | | | | | |
| Graph Manager | ✓ | ✓ | ✓ | ✓ | | ✓ | | | | | | |
| Contradiction Hunter | ✓ | | ✓ | ✓ | | | | | | | | |
| Skeptic | ✓ | | ✓ | ✓ | ✓ | | | | | | | |
| Report Generator | | ✓ | ✓ | ✓ | | | ✓ | | | ✓ | ✓ | ✓ |
| Evidence Graph (data structure) | ✓ | ✓ | ✓ | ✓ | | ✓ | ✓ | | | | | |
| Tool Failure Handling | | | | | | | | ✓ | | | | |

**Coverage check:** All 12 requirements are satisfied by at least one component. No requirement is orphaned. No component has an empty row.

**Traceability gaps flagged for full design:**
- QR-02 is currently satisfied only by the Skeptic. If the Skeptic is removed or degraded, no other component provides adversarial challenge of HIGH-confidence claims. This is a single-point-of-failure for this requirement.
- SR-01 is satisfied only by the Search Agent. If all external sources fail simultaneously, SR-01 cannot be met. QR-05 (graceful degradation) governs behavior in this case.

---

## 4. Core Insight: Why Everything Else Is Wrong

Most research agent systems treat research as a **pipeline**:

```
Query → Search → Summarize → Synthesize → Report
```

This architecture has a fatal structural assumption: that the shape of the answer is knowable before you start searching. It is not.

The pipeline approach:
- Synthesizes toward consensus because the synthesizer sees all evidence at once and gravitates toward the majority view
- Drops contradictions because there is no mechanism to surface them as meaningful signals
- Stops searching when it has enough to write, not when it has enough to be right
- Retrofits citations because the report is written before source grounding is enforced

**The alternative:** Treat research as **graph construction**.

Research is the process of building a graph of claims and the relationships between them. A claim is not just a fact — it is a node in a network of support, contradiction, and qualification. The research is not done when you have enough text. It is done when the graph is stable — when new searches stop changing the structure of what you know.

This reframing solves all three failure modes by construction:
- **Premature synthesis** is prevented because synthesis only occurs when the graph stabilizes
- **Ungrounded claims** are impossible because every node requires a source edge
- **Opaque confidence** is resolved because confidence is structurally derived from the graph topology

---

## 5. Full System Architecture

### High-Level Flow

```
┌─────────────────────────────────────────────────────────────┐
│                      INPUT LAYER                            │
│                  Natural Language Query                      │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                   QUERY ARCHITECT                           │
│  • Disambiguates vague queries                              │
│  • Produces structured Research Brief                       │
│  • Identifies query type: factual / contradictory /         │
│    sparse / multi-dimensional                               │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                  INITIAL SEARCH LAYER                       │
│  • Parallel search across source types                      │
│  • Academic (arXiv, Semantic Scholar)                       │
│  • Web (Tavily / SerpAPI)                                   │
│  • Returns raw documents with metadata                      │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                  CLAIM EXTRACTOR                            │
│  • Extracts atomic factual claims per source                │
│  • Tags each claim: source, date, confidence, domain        │
│  • Deduplicates semantically equivalent claims              │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                   EVIDENCE GRAPH                            │  ← CORE DATA STRUCTURE
│  Nodes: atomic claims (with source provenance)              │
│  Edges: supports / contradicts / qualifies / extends        │
│  State per edge: resolved / unresolved / irreducible        │
└────────────────────────┬────────────────────────────────────┘
                         │
              ┌──────────┴──────────┐
              │                     │
              ▼                     ▼
┌─────────────────────┐  ┌──────────────────────────────────┐
│  GRAPH STABLE?      │  │    CONTRADICTION HUNTER           │
│  (no new nodes or   │  │  • Finds unresolved contradiction │
│   edges after N     │  │    edges in graph                 │
│   iterations)       │  │  • Formulates targeted queries    │
│                     │  │    to resolve each one            │
│  YES → Synthesize   │  │  • Returns to Search Layer        │
│  NO  → Hunt         │  └──────────┬───────────────────────┘
└─────────────────────┘             │
                                    ▼
                    ┌───────────────────────────────────────┐
                    │             SKEPTIC                   │  ← HONESTY GATE
                    │  • Red-teams the current graph        │
                    │  • Detects source/framing bias        │
                    │  • Searches for disconfirming         │
                    │    evidence on HIGH-conf claims       │
                    │  • Forces debate sub-graph if         │
                    │    consensus looks too clean          │
                    │  • Injects challenges back into       │
                    │    graph before stability check       │
                    └───────────────────────────────────────┘
                         │
                [Loop until stable or budget exhausted]
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                  REPORT GENERATOR                           │
│  • Reads directly from stable graph                         │
│  • Claims = nodes, Citations = source edges                 │
│  • Confidence = structural score from graph topology        │
│  • Contradictions = unresolved edges surfaced explicitly    │
│  • Low-evidence areas = nodes with single source            │
└─────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                   OUTPUT LAYER                              │
│  Structured Markdown report with:                           │
│  • Claims separated from evidence                           │
│  • Confidence scores (structurally derived)                 │
│  • Source agreement indicators                              │
│  • Explicit contradiction surfacing                         │
│  • Research metadata                                        │
└─────────────────────────────────────────────────────────────┘
```

### Agent Roles Summary

| Agent | Responsibility | What it reads | What it writes |
|---|---|---|---|
| Query Architect | Turns vague query into Research Brief | Raw query | Structured brief + sub-questions |
| Search Agent(s) | Retrieves raw documents from external sources | Research brief / contradiction queries | Raw documents with metadata |
| Claim Extractor | Extracts atomic claims from documents | Raw documents | Claim objects with source tags |
| Graph Manager | Maintains Evidence Graph, detects edges | New claims | Graph updates (nodes + edges) |
| Contradiction Hunter | Identifies unresolved edges, generates search queries | Graph state | Targeted search queries |
| Skeptic | Red-teams graph, detects bias, searches for disconfirming evidence on high-confidence claims | Graph state + high-confidence nodes | Challenge claims + debate sub-graph edges |
| Report Generator | Synthesizes stable graph into structured report | Stable graph | Final report |

---

## 6. Component Deep Dives

### 6.1 Query Architect

**Satisfies:** `FM-01` `QR-03`

**Responsibility:** Transform a vague natural language query into a structured Research Brief that the rest of the system can execute against.

**Why it exists:**  
Without this component, the Searcher shapes the research by what is easy to find. The query "inference-time compute scaling" without decomposition will retrieve whatever ranks highest on that phrase — likely survey papers that define the landscape rather than primary research that tests it. The Query Architect forces explicit scope definition before any searching begins.

**What it produces:**
```json
{
  "original_query": "Is chain-of-thought prompting effective?",
  "query_type": "contradictory_sources",
  "core_question": "Does chain-of-thought prompting improve LLM reasoning capability, or does it primarily improve output structure?",
  "sub_questions": [
    "What tasks show the strongest evidence of CoT improving accuracy?",
    "What tasks show CoT having no effect or negative effect?",
    "Is CoT benefit correlated with model scale?",
    "What is the mechanism — does CoT change what the model computes or how it presents output?"
  ],
  "scope_boundaries": {
    "include": ["empirical benchmarks", "ablation studies", "mechanistic interpretability work"],
    "exclude": ["opinion pieces", "tutorial content", "non-LLM chain-of-thought"]
  },
  "expected_difficulty": "high",
  "contradiction_likelihood": "high"
}
```

**What happens if you remove it:**  
The system searches reactively. The first search result shapes all subsequent searches. Research scope is determined by what is easy to find, not what the question actually requires. On the CoT test case, the system would likely find 10 sources saying CoT works and write a confident report that misses the entire fault line in the literature.

**Failure mode:**  
If the Query Architect misidentifies the query type — for example, classifying a contradictory-sources question as straightforward — the downstream system allocates insufficient search budget and misses the contradiction-hunting phase entirely. Mitigation: always default to `contradictory_sources` for queries about LLM behaviors, where the literature is reliably contested.

---

### 6.2 Search Agent

**Satisfies:** `FM-01` `QR-05` `SR-01`

**Responsibility:** Retrieve raw documents from external sources given a search query.

**Why parallel search across source types:**  
Single-source search creates an availability bias — the system only knows what one index contains and weighted for. Academic search (arXiv, Semantic Scholar) surfaces peer-reviewed work but misses recent preprints, blog posts with empirical results, and practitioner findings. Web search surfaces recent work but lacks structured metadata. Combining them forces the system to reconcile across source types rather than anchoring to one.

**Source priority hierarchy:**
1. Peer-reviewed papers (highest credibility weight)
2. arXiv preprints (moderate credibility, high recency)
3. Institutional blogs and technical reports (domain-specific credibility)
4. General web sources (lowest credibility, used for recency and coverage)

**Failure handling:**
```
Search attempt → 
  Success → return documents
  Timeout → retry with backoff (max 3 attempts)
  Rate limit → queue with delay
  No results → mark sub-question as low-evidence, log attempt
  All sources fail → flag sub-question as search-failed, include in report metadata
```

**What the Search Agent does NOT do:**  
It does not summarize, interpret, or evaluate what it finds. Its only job is retrieval. Separation of retrieval from interpretation is critical — a combined search-and-interpret agent will retrieve sources that confirm its initial interpretation and stop when it has enough to write.

---

### 6.3 Claim Extractor

**Satisfies:** `FM-02` `QR-04`

**Responsibility:** Transform raw documents into atomic, source-tagged claim objects.

**Why atomic claims:**  
Whole documents cannot be compared for contradiction. A document may contain 20 claims, 18 of which agree with other sources and 2 of which contradict. If documents are compared at the document level, those 2 contradictions are invisible. Atomization makes contradictions findable.

**Claim schema:**
```json
{
  "claim_id": "c_0047",
  "text": "Chain-of-thought prompting improves accuracy on GSM8K by 30% for models above 100B parameters",
  "source_id": "wei_2022_cot",
  "source_url": "https://arxiv.org/abs/2201.11903",
  "source_type": "peer_reviewed",
  "source_date": "2022-01-28",
  "confidence_from_source": 0.85,
  "domain_tags": ["chain_of_thought", "few_shot_prompting", "arithmetic_reasoning"],
  "is_empirical": true,
  "is_speculative": false
}
```

**Deduplication:**  
Semantically equivalent claims from different sources must be merged into a single node with multiple source edges. Without deduplication, the same claim from 5 sources appears to have 5x the support it actually has. Deduplication uses embedding similarity with a threshold — claims with cosine similarity above 0.92 are considered candidates for merge, then verified by an LLM pairwise comparison.

**What breaks here:**  
Claim extraction quality is the most fragile component of the system. The LLM can merge two distinct claims into one (losing a contradiction) or split one claim into two (creating false disagreement). This is the primary failure mode I would address with more time — likely through fine-tuning on claim extraction specifically, with human-labeled examples of correct atomic decomposition.

---

### 6.4 Graph Manager

**Satisfies:** `FM-01` `FM-02` `FM-03` `QR-01` `QR-03`

**Responsibility:** Maintain the Evidence Graph — add nodes, detect and label edges, track graph stability.

**Edge detection:**  
For each new claim added, compare against all existing nodes. LLM call:

```
Given Claim A: [text]
Given Claim B: [text]

Does Claim A:
(a) support Claim B — both assert the same thing
(b) contradict Claim B — they cannot both be true
(c) qualify Claim B — adds nuance or scope limitation
(d) extend Claim B — builds on it as a premise
(e) is unrelated

Return: {relationship: "support"|"contradict"|"qualify"|"extend"|"unrelated", confidence: 0-1}
```

**Graph stability definition:**  
The graph is stable when an iteration of N new searches produces fewer than K new nodes or contradiction edges, where N and K are configurable. Default: stable when fewer than 3 new nodes are added across 5 consecutive searches.

**Why stability rather than count:**  
A fixed search count is arbitrary. Searching 20 times on a sparse topic wastes compute. Stopping after 5 searches on a rich, contested topic misses most of the evidence. The graph encodes what is actually known, and stability is an objective measure of when new searching stops changing it.

---

### 6.5 Contradiction Hunter

**Satisfies:** `FM-01` `FM-03` `QR-01`

**Responsibility:** Find unresolved contradiction edges in the graph and generate targeted search queries to resolve them.

**Why this component is the "wow" of the architecture:**  
Every other research system finds contradictions as a side effect of synthesis. This system finds contradictions and uses them as a primary search signal. When two claims contradict each other, the system does not pick one and move on. It asks: "What additional evidence would resolve this?" and goes to find it.

**Query generation for contradiction resolution:**
```
Given:
Claim A: "CoT improves performance on multi-step reasoning tasks" (Source: Wei 2022)
Claim B: "CoT shows no improvement over direct prompting when controlling for output length" (Source: Kambhampati 2023)

Generate a search query that would find evidence to resolve or explain this contradiction.

Query: "chain-of-thought prompting output length control benchmark comparison 2023 2024"
```

**Resolution outcomes:**
- **Resolved — A wins:** New evidence strongly supports A and explains why B was wrong or limited
- **Resolved — B wins:** New evidence strongly supports B and explains the conditions under which A's finding was overstated
- **Resolved — Both correct in scope:** New evidence shows A and B are both correct but describe different conditions (e.g., model scale dependency)
- **Irreducible:** After N search attempts, the contradiction remains. Mark as explicitly unresolved in the report.

**The irreducible case is not a failure.** Surfacing a genuine unresolved contradiction in the literature is a valid and valuable research output. A report that says "we found no resolution to this contradiction after 5 targeted searches" is more honest and more useful than one that quietly picks a side.

---

### 6.6 Skeptic

**Satisfies:** `FM-01` `FM-03` `QR-01` `QR-02`

**Responsibility:** Red-team the current state of the Evidence Graph immediately after the Contradiction Hunter runs, before the stability check is evaluated. Act as the system's final honesty gate.

**Why it exists:**  
The Contradiction Hunter addresses contradictions the graph has already found. The Skeptic addresses a different failure mode: a graph that converges on a *comfortable but wrong* local consensus because the search strategy never surfaced disconfirming evidence in the first place. A graph can be internally consistent — no unresolved contradiction edges — and still be systematically wrong if all its sources share the same framing bias, institutional origin, or methodological assumption. The Skeptic exists to catch this. It directly addresses the research question: *"How do you prevent agents from converging on a comfortable, wrong answer?"*

**The distinction from the Contradiction Hunter:**  
The Contradiction Hunter is reactive — it responds to contradictions already present in the graph. The Skeptic is proactive — it actively constructs challenges to claims the graph currently treats as settled. The Contradiction Hunter asks "what disagrees with what?" The Skeptic asks "what have we not looked for that would undermine what we think we know?"

**What the Skeptic does:**

*Step 1 — Bias Detection:*  
Scan all source nodes in the graph. Flag if:
- More than 70% of sources supporting a HIGH-confidence claim share the same institutional origin, research group, or publication venue
- All sources supporting a claim were published within a narrow time window (potential recency bias — the field may have moved)
- All sources use the same benchmark or evaluation methodology (potential measurement bias)

*Step 2 — Disconfirmation Search:*  
For every claim rated HIGH confidence (>0.80), generate a targeted search query designed to find evidence against it:

```
Given HIGH-confidence claim: "[claim text]"
Supported by: [source list]

Generate a search query that would find evidence AGAINST this claim,
including null results, failed replications, or scope limitations.

Query: "..."
```

If the search returns new disconfirming evidence, inject it as a new claim node with a `contradicts` edge. This may destabilize the graph — intentionally.

*Step 3 — Debate Sub-Graph (conditional):*  
If a HIGH-confidence claim receives a disconfirming challenge from Step 2, and the challenge cannot be immediately resolved by the existing graph structure, the Skeptic opens a local debate sub-graph: a temporary mini-graph containing the original claim, the challenge, and any qualifying evidence. This sub-graph is resolved by targeted search before the main stability check proceeds. The debate sub-graph is a bounded adversarial mechanism — not a full multi-agent debate loop, which would be expensive and prone to sycophantic convergence.

**What the Skeptic does NOT do:**  
It does not replace or duplicate the Contradiction Hunter. It does not run on every claim — only HIGH-confidence claims warrant adversarial scrutiny. It does not block synthesis indefinitely — if the Skeptic finds no new disconfirming evidence after its pass, it exits cleanly and the stability check proceeds. The Skeptic is a gate, not a bottleneck.

**Trigger conditions:**  
The Skeptic activates on every loop iteration but operates selectively:
- Bias detection: always runs, costs only graph traversal
- Disconfirmation search: only for claims above the HIGH-confidence threshold (>0.80)
- Debate sub-graph: only if disconfirmation search returns genuinely contradicting evidence

**What breaks if you remove it:**  
The system is vulnerable to source monoculture — a graph where all evidence points the same direction not because consensus exists but because dissenting evidence was never retrieved. On topics where the mainstream literature is biased (e.g., positive-result publication bias in ML benchmarks), the Contradiction Hunter finds no contradictions because the sources retrieved all agree. The graph stabilizes. The report sounds confident. It is wrong in ways no structural check will catch, because the error is in what was never searched for.

**Failure mode:**  
The Skeptic's disconfirmation search can itself be biased — it may fail to find genuine disconfirming evidence not because it does not exist but because it is buried, paywalled, or not in the search index. This is the same systematic incompleteness problem that affects the whole system. Mitigation: the Skeptic logs every disconfirmation search attempt and its result. Reports include a `skeptic_coverage` field noting how many HIGH-confidence claims were challenged and whether challenges returned results.

---

### 6.7 Report Generator

**Satisfies:** `FM-02` `FM-03` `QR-01` `QR-04` `SR-02` `SR-03` `SR-04`

**Responsibility:** Traverse the stable Evidence Graph and render it as a structured, human-readable report.

**Why generate from the graph, not from a prompt:**  
If the report is generated by prompting an LLM with all the retrieved text, the LLM can hallucinate, can omit inconvenient contradictions, and can assign confidence subjectively. Generating from the graph means every claim in the report is a node, every citation is a source edge, and every confidence score is structurally derived. Hallucination is structurally prevented — you cannot add a claim to the report that does not exist as a node in the graph.

**Confidence scoring:**
```
Confidence(claim) = supporting_source_count / (supporting_source_count + contradicting_source_count)

Adjusted for source credibility:
Confidence(claim) = Σ(credibility_weight × support) / Σ(credibility_weight × (support + contradict))
```

Where credibility weights are: peer-reviewed = 1.0, preprint = 0.8, institutional blog = 0.6, web = 0.4.

**Report structure:**
```markdown
# Research Report: [Topic]

## Executive Summary
[2-3 sentences: what the evidence shows at the highest level]

## Confidence Legend
HIGH: >0.80 | MEDIUM: 0.50–0.80 | LOW: <0.50 | CONTESTED: active contradiction

## Key Findings

### [Finding 1 — HIGH confidence]
**Claim:** [atomic claim text]
**Confidence:** 0.87 (4 supporting sources, 1 qualifying)
**Source Agreement:** STRONG
**Evidence:**
- [Source A, 2022] — [what it shows]
- [Source B, 2023] — [what it shows]

### [Finding 2 — CONTESTED]
**Claim:** [atomic claim text]
**Confidence:** 0.51 (3 supporting, 3 contradicting)
**Source Agreement:** DIVIDED
**Evidence For:**
- [Source C] — [what it shows]
**Evidence Against:**
- [Source D] — [what it shows]

## Unresolved Contradictions
### Contradiction 1: [Topic]
- **Position A:** [claim + source]
- **Position B:** [claim + source]
- **Resolution attempts:** 4 targeted searches, no resolution found
- **Why it matters:** [implication of the disagreement]
- **Status:** IRREDUCIBLE — both positions have credible empirical support

## Low-Evidence Areas
- [Topic Z]: Only 1 source found. Treat findings here with caution.
- [Topic W]: Sources found but all from same research group. Independent replication lacking.

## Research Metadata
- Total sources retrieved: 31
- Unique claims extracted: 58
- Contradiction edges found: 9
- Contradictions resolved: 6
- Contradictions irreducible: 3
- Graph stability reached: iteration 6
- Total search iterations: 8
```

---

## 7. The Evidence Graph — Core Data Structure

### Schema

```python
@dataclass
class Claim:
    claim_id: str
    text: str
    source_id: str
    source_url: str
    source_type: str          # "peer_reviewed" | "preprint" | "web" | "blog"
    source_date: str
    credibility_weight: float
    domain_tags: list[str]
    is_empirical: bool
    is_speculative: bool

@dataclass
class Edge:
    edge_id: str
    source_claim_id: str
    target_claim_id: str
    relationship: str         # "supports" | "contradicts" | "qualifies" | "extends"
    confidence: float
    resolution_status: str    # "unresolved" | "resolved_for_source" | "resolved_for_target" | "irreducible"
    resolution_evidence: list[str]  # claim_ids that resolved this edge

class EvidenceGraph:
    claims: dict[str, Claim]
    edges: dict[str, Edge]
    
    def add_claim(self, claim: Claim) -> list[Edge]
    def get_unresolved_contradictions(self) -> list[Edge]
    def get_confidence(self, claim_id: str) -> float
    def is_stable(self, threshold_nodes: int, threshold_edges: int) -> bool
    def to_report_structure(self) -> dict
```

### Why a Graph and Not a Table or Vector Store

A table can store claims and sources but cannot represent relationships between claims. A vector store can find similar claims but cannot represent structured logical relationships (support vs. contradiction vs. qualification are fundamentally different). A graph is the natural representation for a network of claims with typed relationships.

**Practical implementation:** For the MVP, `networkx` is sufficient. For production, a property graph database (Neo4j, Amazon Neptune) would handle scale and complex traversal queries.

---

## 8. Memory & Context Management

### The Core Problem

A deep research task accumulates far more text than fits in any model's context window. A single research session might retrieve 30+ documents averaging 3,000 tokens each — 90,000 tokens of raw material, far exceeding typical context limits and certainly too much to pass to a synthesis step.

### Strategy: Compression at Every Stage

**Stage 1 — Document → Claims:**  
Raw documents (3,000 tokens) are compressed to atomic claims (20-50 tokens each, 5-15 per document). A 3,000 token document becomes ~400 tokens of structured claims. Compression ratio: ~7:1.

**Stage 2 — Claims → Graph:**  
The graph is a structured summary of all claims and their relationships. It is far more compact than the claim set and contains the relational information that the claim set alone does not.

**Stage 3 — Graph → Report:**  
The Report Generator reads only the graph, not the original documents. It never needs to hold all 90,000 tokens in context simultaneously.

### What Gets Discarded

Raw documents are stored on disk and are not passed to any LLM after claim extraction. The LLM only ever sees:
- Individual documents during claim extraction (one at a time)
- Pairs of claims during edge detection
- The structured graph during report generation

This means the effective context window burden per LLM call is bounded and predictable regardless of how many sources are retrieved.

### What Must Be Preserved

The full provenance chain: every claim traces back to an exact URL and quote. This is stored in the claim object and never discarded. Without it, citation verification is impossible and the grounding guarantee breaks.

---

## 9. Tool Design & Failure Handling

### Tool Inventory

| Tool | Purpose | Failure mode | Fallback |
|---|---|---|---|
| `web_search(query)` | General web retrieval | Rate limit, no results | Secondary search API |
| `arxiv_search(query)` | Academic paper retrieval | API down, sparse results | Semantic Scholar fallback |
| `fetch_url(url)` | Full document retrieval | 404, paywall, timeout | Use snippet from search result |
| `embed(text)` | Semantic similarity for dedup | API failure | Lexical similarity fallback |
| `llm_call(prompt)` | Claim extraction, edge detection | Timeout, refusal | Retry with simplified prompt |

### Failure Handling Philosophy

**No silent failures.** Every tool failure is logged and propagated to the report metadata. If a sub-question could not be searched because the search API was down, the report says so explicitly. A report with known gaps is more honest than a confident report with unknown gaps.

**Graceful degradation hierarchy:**
```
Tool fails →
  Retry with exponential backoff (max 3 attempts) →
    Fallback to alternative tool →
      Mark sub-question as degraded (lower confidence weight) →
        If critical path: fail loudly with explanation
        If non-critical path: include in low-evidence section
```

**Tool call budgets:**  
Each sub-question has a search budget (default: 5 searches, 20 documents). Budget is allocated based on difficulty score from the Query Architect. Hard questions get more budget. Budget exhaustion is a soft stop — the system reports findings with what it has rather than crashing.

---

## 10. Quality, Reliability & Honesty

### How the System Stays Honest

**Structural honesty — claims require source edges:**  
The Report Generator cannot add a claim to the report without a corresponding node in the graph with at least one source edge. This is enforced structurally, not by prompt instruction. Prompt instructions can be violated. Data structure constraints cannot.

**Quantified uncertainty — confidence is not vibes:**  
Confidence scores are computed from graph topology, not from asking an LLM "how confident are you?" This prevents the well-documented tendency of LLMs to express high confidence regardless of actual evidence quality.

**Contradiction surfacing — disagreement is a signal, not noise:**  
Every unresolved contradiction edge in the graph is included in the report. The system is explicitly designed to surface disagreement rather than resolve it toward the majority view.

**Evidence saturation signaling:**  
When a sub-question has fewer than 2 independent sources, it is flagged as low-evidence regardless of confidence score. A single highly credible source can produce a high confidence score but still warrant a caveat about lack of independent replication.

### How the System Can Still Be Wrong

**Claim extraction errors propagate:**  
If the extractor merges two claims that should be distinct, a real contradiction becomes invisible. This is the primary honesty failure mode.

**Source credibility weights are heuristic:**  
The difference between peer-reviewed (1.0) and preprint (0.8) credibility is an assumption, not a measurement. A wrong preprint from a credible lab can have more effective credibility than a peer-reviewed paper from a low-quality venue.

**Graph stability is not truth stability:**  
The graph can stabilize on an incorrect picture if the search strategy systematically misses a class of evidence (e.g., non-English sources, paywalled papers, very recent work not yet indexed).

---

## 11. Evaluation Framework

### The Core Challenge

There is no ground truth for a research report. A report about chain-of-thought prompting cannot be scored against an answer key. This means evaluation must rely on proxy metrics that correlate with quality.

### Evaluation Dimensions

**1. Citation Accuracy (Automated)**  
For each claim-citation pair in the report, fetch the cited source and verify the claim is supported.

```
Citation_Accuracy = claims_supported_by_cited_source / total_claims
Target: > 0.90
```

**2. Coverage (LLM-as-Judge)**  
Given a list of known sub-topics for the query domain, what fraction does the report address?

```
Coverage = sub_topics_addressed / total_known_sub_topics
Target: > 0.75
```

**3. Contradiction Detection Rate (Synthetic Benchmark)**  
Construct test cases with known contradictions by taking real contradictory papers and verifying the system surfaces the contradiction.

```
Contradiction_Detection = contradictions_surfaced / known_contradictions_in_test_set
Target: > 0.80
```

**4. Confidence Calibration (Empirical)**  
For claims rated HIGH confidence, verify against ground truth (where it exists, e.g., well-established benchmarks). HIGH confidence claims should be correct more often than MEDIUM confidence claims.

**5. Ablation: Contradiction Hunter On vs. Off**  
Run the system on Test Case 2 (CoT — contradictory sources) with and without the Contradiction Hunter. Compare:
- Number of contradictions surfaced
- Citation accuracy
- Coverage of known fault lines in the literature

This is the controlled comparison that isolates the impact of the core architectural decision.

### Self-Evaluation Criteria

The system produces a quality assessment alongside every report:

```json
{
  "query": "...",
  "overall_confidence": 0.71,
  "coverage_estimate": "MEDIUM — 6/8 major sub-topics addressed",
  "contradiction_handling": "3 contradictions found, 2 resolved, 1 irreducible",
  "low_evidence_areas": ["scaling behavior below 7B", "non-English performance"],
  "search_completeness": "PARTIAL — arxiv API degraded during session, 4 searches fell back to web",
  "recommended_follow_up": ["Search specifically for post-2024 work on CoT and model scale"]
}
```

---

## 12. Architecture Alternatives Considered

### 10.1 Naive Pipeline (Rejected)

```
Query → Search → Summarize → Synthesize → Report
```

**Why rejected:** This is the baseline. It has no mechanism for contradiction detection, no structural grounding, and stops searching when it has enough to write rather than when it knows enough to be right. Useful as a baseline comparison but not as a production system.

**When it would be better:** Short-context, well-documented queries with low contradiction likelihood. If someone asks "what is RLHF," a pipeline is faster, cheaper, and produces a perfectly adequate answer.

---

### 10.2 ReAct Loop (Partially Adopted)

```
Think → Search → Observe → Think → Search → Observe → ... → Answer
```

**Why not chosen as primary architecture:** Sequential by nature — cannot parallelize sub-questions. Single context window means research history competes with reasoning space. No explicit contradiction handling. Stopping condition is implicit — the model decides when it "feels done," which correlates poorly with actual evidence sufficiency.

**What we kept from it:** The iterative refinement principle. Our Contradiction Hunter is essentially a ReAct loop applied specifically to contradiction resolution — reason about what is unresolved, act to resolve it, observe the result, repeat.

---

### 10.3 Plan-and-Execute (Partially Adopted)

```
Planner → [Parallel Tasks] → Execute → Merge → Report
```

**Why not chosen as primary:** The plan is fixed upfront and does not adapt. Contradictions discovered during execution cannot trigger replanning. The merge step pushes contradiction discovery to the end, after all searching is complete, leaving no opportunity to resolve contradictions with more searching.

**What we kept from it:** Parallel initial search. The initial broad search runs multiple source types in parallel. This is the plan-and-execute pattern applied to the first phase only.

---

### 10.4 Multi-Agent Debate (Rejected as Primary)

```
Agent A produces report → Agent B critiques → Agent A revises → Consensus
```

**Why rejected:** Debate converges on rhetorically stronger arguments, not evidentially stronger ones. Without new external evidence being introduced during debate, agents are just arguing from their pretrained priors. Sycophantic convergence is a real risk — the less confident agent tends to defer to the more assertive one regardless of evidence quality.

**When it would be useful:** As a post-synthesis step. After the Evidence Graph report is generated, a Critic agent that specifically hunts for unsupported claims, missing caveats, and overconfident conclusions would add value. This is in the full design but not the MVP.

---

### 10.5 Hierarchical Manager-Worker (Rejected)

```
Manager → [Worker 1, Worker 2, Worker 3] → Manager synthesizes
```

**Why rejected:** Workers operate in isolation. Worker 1 cannot inform Worker 2 of what it found. Cross-worker contradictions are invisible until synthesis. The manager is a single point of failure and a bottleneck. Most importantly, this architecture creates information walls exactly where information needs to flow — between research threads on related sub-topics.

---

### 10.6 RAG (Adopted as Component)

**Why not chosen as primary architecture:** Passive retrieval finds what is similar to the query, not what contradicts it. Single-shot, no iteration, no stopping condition, no contradiction handling.

**Why adopted as component:** The Search Agent uses dense retrieval (embedding-based) as one of its retrieval strategies. RAG is the right tool for finding relevant documents. It is the wrong architecture for the system as a whole.

---

### 10.7 Tree of Thoughts (Rejected)

**Why rejected:** Research is graph-shaped, not tree-shaped. Ideas connect across branches. Backtracking in research is not well-defined — a dead end on one sub-question still produces evidence that might be relevant to another. The value function for "promising branch" is hard to define without ground truth. Expensive and fragile in practice.

**Interesting property:** The Contradiction Hunter is conceptually similar to targeted branch expansion in a tree search — when a contradiction is found, the system expands that node with more search. The Evidence Graph gives us the benefits of adaptive exploration without the overhead of a full tree search.

---

## 13. Trade-off Study (The "System Balance")

Every engineering choice involves a sacrifice. Here is the analysis:

| Trade-off | Option A (Simpler/Faster/Cheaper) | Option B (More Powerful, Selected) | Selected & Why |
|---|---|---|---|
| **Latency vs. Accuracy** | Single-pass search: retrieve N documents, synthesize immediately, return report in seconds | Iterative graph-stabilization loop: search, extract, detect contradictions, re-search until stable — takes minutes | **Option B.** Single-pass synthesis directly violates `FM-01` — the system stops when it has enough to write, not enough to be right. The Evidence Graph loop satisfies `FM-01` and `QR-03` by guaranteeing synthesis only occurs when new searches stop changing the known claim structure. Latency is acceptable for a research tool, not a chat interface. |
| **Cost vs. Depth** | Summarize whole documents with one LLM call each; skip pairwise edge detection | Extract atomic claims per document; run pairwise LLM edge classification across the claim set | **Option B.** Document-level summarization violates `FM-02` — citations attach to summaries, not to specific verifiable assertions. Atomic claim extraction with edge detection is the only mechanism that satisfies `FM-02` and `QR-04`: contradictions become findable at the claim level rather than invisible inside aggregated prose. Cost is mitigated by embedding pre-filtering before LLM edge calls. |
| **Flexibility vs. Determinism** | Allow LLM to assign confidence scores subjectively based on its own reasoning ("how confident are you?") | Derive confidence structurally from graph topology: supporting edges divided by total edges, weighted by source credibility | **Option B.** Subjective LLM confidence directly violates `FM-03` — models consistently express high certainty regardless of evidence quality. Structural confidence derived from the Evidence Graph satisfies `FM-03` and `SR-03`: a claim with three supporting sources and two contradicting sources cannot be rated HIGH confidence, regardless of how plausible it sounds. |
| **State Storage** | Retain full raw documents in memory throughout the session; pass them to the synthesis step | Compress documents to atomic claim objects at extraction time; discard raw text from LLM context after that stage | **Option B.** Full document retention makes context window management intractable — 30 documents at 3,000 tokens each exceeds synthesis context limits and forces the LLM to selectively attend, introducing implicit bias that would violate `FM-01` and `FM-02`. Atomic claims achieve ~7:1 compression while preserving the provenance chain required by `QR-04` and the specific assertions needed by the Contradiction Hunter to satisfy `QR-01`. |
| **Search Breadth vs. Precision** | Issue broad keyword queries across a single source type (web only); maximize recall at the cost of relevance | Issue parallel queries across typed source hierarchies (peer-reviewed, preprint, web); follow with contradiction-targeted precision queries | **Option B.** Single-source broad search creates availability bias that directly undermines `QR-01` and `QR-02` — the system anchors on whatever one index surfaces and ranks highest. The Contradiction Hunter (`QR-01`) requires precision queries to target specific disagreements, not general topics. The Skeptic (`QR-02`) requires source diversity to detect institutional or methodological monoculture. Satisfies `SR-01` by diversifying the external data sources used per session. |
| **Orchestration Simplicity vs. Reliability** | Linear sequential pipeline: each step runs once, passes output to the next, no cycles or checkpointing | LangGraph stateful graph with cycles, conditional edges, and checkpoint-based state persistence at every node | **Option B.** A linear pipeline cannot express the iterative loop required by `FM-01` and `QR-03` — contradiction-driven re-search requires cycles back to the Search Agent. LangGraph checkpointing also satisfies `QR-05`: if the system fails mid-session, state is recoverable from the last checkpoint rather than requiring a full restart. Silent failure with no recovery is incompatible with `QR-05`. |
| **Stopping Condition** | Fixed iteration count: run exactly N search rounds regardless of what the graph contains | Graph stability threshold: stop when consecutive iterations produce fewer than K new nodes or contradiction edges | **Option B.** Fixed iteration count violates both `FM-01` (over-searches sparse topics causing wasted compute, under-searches rich contested topics causing premature synthesis) and `QR-03` (termination on a fixed count is explicitly prohibited). Graph stability satisfies `QR-03` and `FM-01`: it encodes the principle that research is done when new evidence stops changing what is known. The Evidence Graph is the single source of truth for this determination. |

These trade-offs are not independent. They compose into a coherent position: the system consistently selects the option that treats the Evidence Graph as the authoritative representation of what is known, and the Contradiction Hunter as the mechanism that drives exploration forward. Every "heavier" choice on the right side of the table exists because the lighter alternative would violate `FM-01` (structural grounding guarantee), `FM-02` (source grounding guarantee), or `FM-03` (confidence calibration guarantee) — the three failure mode requirements that define the architecture's core claim over pipeline alternatives. Where cost or latency is sacrificed, it is sacrificed deliberately, with a specific requirement satisfied in exchange.

---

## 14. Production Concerns

### Latency

A full research session with graph stabilization over 6+ iterations will take minutes, not seconds. This is acceptable for a research tool (not a chat interface) but requires:
- Streaming intermediate results to the user (show claims as they are extracted)
- Progress indicators (iteration N, X nodes in graph, Y contradictions being resolved)
- Async architecture — the user should not be blocked

### Cost

LLM calls dominate cost. Each claim extraction call processes one document. Each edge detection call compares two claims. For a 30-document session with 10 claims per document = 300 claims, edge detection in the naive case is O(n²) = 45,000 comparisons. This is prohibitive.

**Cost mitigation:**
- Batch edge detection — compare new claims only against claims in the same domain cluster
- Use embedding similarity as a cheap pre-filter before LLM edge classification
- Cache claim objects and edge classifications across similar queries

### Reproducibility

Research results should be reproducible. Two runs of the same query should produce substantially similar reports. This requires:
- Pinned search API versions
- Deterministic claim extraction (temperature = 0)
- Serialized graph state saved alongside the report
- Logging of all search queries issued

### Observability

Multi-step systems are hard to debug. Every component writes structured logs:
- Query Architect: structured brief with version
- Search Agent: query issued, source type, results count, latency
- Claim Extractor: document → claims mapping with confidence
- Graph Manager: every node addition, every edge classification
- Contradiction Hunter: contradiction detected, query generated, resolution outcome

Full trace is attached to every report output. Given a bad report, you can trace every decision that produced it.

---

## 15. MVP Scope & Prioritization

### What Is In the MVP

| Component | Included | Reason |
|---|---|---|
| Query Architect | Yes | Critical — prevents scope drift |
| Parallel search (web + arxiv) | Yes | Demonstrates real data sources |
| Claim Extractor | Yes | Core to the architecture |
| Evidence Graph | Yes | The core innovation |
| Contradiction Hunter | Yes | The "wow" component — must demo |
| Skeptic (bias detection + disconfirmation search) | Partial | Bias detection + disconfirmation search included; debate sub-graph deferred to full design |
| Graph stability stopping condition | Yes | Principled stopping — key design point |
| Report Generator with structural confidence | Yes | Required output properties |
| Critic / debate agent | No | Design only |
| Fine-tuned claim extractor | No | Design only |
| Production observability | Partial | Basic logging only |
| Cost optimization (batched edge detection) | No | Naive O(n²) acceptable for MVP scale |
| Streaming UI | No | CLI output acceptable for demo |

### Prioritization Reasoning

The MVP must demonstrate the core idea: **contradiction-driven exploration produces better research than synthesis-first pipelines**. Everything that is in the MVP serves this demonstration. Everything that is out either requires more than 2 days to build properly or is a production concern that does not affect the core idea.

The ablation — pipeline baseline vs. Evidence Graph system on Test Case 2 — is the most important thing to include. It makes the value of the architecture visible and measurable.

---

## 16. Known Weaknesses & Future Work

### Known Weaknesses

**1. Claim Extraction Quality**  
The most fragile component. Merging two distinct claims loses a contradiction. Splitting one claim into two creates a false contradiction. Quality degrades on dense technical text with many implicit assumptions. Mitigation with more time: fine-tune a small model specifically on claim extraction from research papers.

**2. Edge Detection at Scale**  
Naive O(n²) pairwise comparison becomes expensive above ~200 claims. Domain clustering with embedding pre-filtering reduces this, but the clustering itself can create false boundaries that hide cross-domain contradictions.

**3. Search Completeness**  
The graph can stabilize incorrectly if systematic search gaps exist — paywalled papers, non-English sources, very recent work, grey literature. The system does not know what it has not found. Mitigation: source diversity requirements (must search at least N distinct source types before declaring stability).

**4. Credibility Weights Are Heuristic**  
The peer-reviewed / preprint / web credibility hierarchy is an assumption. A wrong paper can be peer-reviewed. A correct finding can live on a blog. These weights should be treated as priors, not facts.

**5. No Temporal Reasoning**  
The system treats a 2019 paper and a 2024 paper with equal weight if they have equal credibility scores. For fast-moving fields (LLM research), recency matters significantly. Full design includes a temporal decay factor in confidence scoring.

### What I Would Build Next

1. **Fine-tuned claim extractor** — the single highest-value improvement
2. **Temporal confidence weighting** — critical for LLM research where the field moves fast
3. **Citation verification agent** — cross-check that each citation actually supports its claim
4. **Process reward model for research quality** — step-level signals rather than outcome-only, enabling RL-based improvement of the search and extraction policies
5. **Streaming interface** — for real usability, users need to see progress
6. **Cross-session memory** — what the system has already learned about a topic should inform future queries on related topics

---

## Appendix: Connection to the Research Landscape

### Search-R1 and RL for Interleaved Search

Search-R1 trains a model to interleave search and reasoning using RL. In a single-agent setting, this is powerful. In a multi-agent setting, the question becomes: do agents share a joint reward signal or optimize independently? Independent optimization risks agents duplicating effort. Joint optimization requires a coordination mechanism.

The Evidence Graph is that coordination mechanism. Agents do not duplicate effort because the graph records what has already been claimed and sourced. The reward signal for the Contradiction Hunter is clear — reducing unresolved edges. This is a well-defined step-level signal of the kind that makes RL training tractable.

### Process Reward Models

The Evidence Graph architecture naturally generates step-level supervision signals:
- Claim extraction quality: does the extracted claim accurately represent the source?
- Edge classification quality: is this actually a contradiction or a qualification?
- Contradiction query quality: does this search query actually resolve the contradiction?

These are intermediate rewards that are more informative than outcome-only reward (is the final report good?). This architecture is designed for future PRM training.

### SCoRe and Self-Correction

SCoRe trains models to correct their own errors. In this system, self-correction is architectural rather than trained — the Contradiction Hunter is a structured self-correction mechanism. When the graph contains an unresolved contradiction, the system is correcting its own incomplete picture through targeted search. The question SCoRe raises — can you train this correction behavior in rather than building it in — is exactly the right next research direction for this system.

---

*Document version 1.0. Architecture reflects ~2 day MVP constraints. Full production design includes components marked as design-only throughout.*