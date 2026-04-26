from __future__ import annotations

"""Three pre-written document fixtures representing the real CoT literature fault lines.

Doc 1 (pro-CoT)    — Wei et al. 2022: CoT significantly improves reasoning on large models
Doc 2 (anti-CoT)   — Kambhampati et al. 2023: CoT doesn't improve reasoning, just formatting
Doc 3 (nuanced)    — Min et al. 2022: label correctness in CoT matters less than structure

These are faithful summaries of real papers. Using fixtures eliminates all search calls
so the demo only uses ~18 LLM calls total (extraction + edge detection + report).
"""

from src.graph.schemas import RawDocument, SourceType

FIXTURES: list[RawDocument] = [
    RawDocument(
        doc_id="demo_doc_1",
        url="https://arxiv.org/abs/2201.11903",
        title="Chain-of-Thought Prompting Elicits Reasoning in Large Language Models (Wei et al., 2022)",
        source_type=SourceType.PEER_REVIEWED,
        publication_date="2022-01-28",
        search_query="demo",
        content="""\
Chain-of-thought (CoT) prompting generates a series of intermediate reasoning steps as part of
the LLM's output before it produces a final answer. This paper demonstrates that CoT prompting
significantly improves performance on arithmetic, commonsense, and symbolic reasoning benchmarks.

Key findings:
- CoT prompting with PaLM 540B achieves state-of-the-art accuracy on GSM8K (math word problems),
  surpassing even fine-tuned GPT-3 with a verifier.
- Performance gains from CoT are strongly correlated with model scale: models below ~100B
  parameters show little or no benefit, while models above 100B show dramatic improvements.
- CoT is an emergent capability — it cannot be induced in smaller models simply by prompting.
- The technique requires no task-specific fine-tuning and works via few-shot exemplars that
  include reasoning steps.
- On commonsense benchmarks (StrategyQA, ARC) and symbolic tasks, CoT similarly outperforms
  standard few-shot prompting by large margins.

Conclusion: Chain-of-thought prompting is a genuine reasoning improvement for sufficiently
large language models, not merely a formatting change.
""",
    ),
    RawDocument(
        doc_id="demo_doc_2",
        url="https://arxiv.org/abs/2305.04388",
        title="Can LLMs Reason? A Study on the Role of Chain-of-Thought in Reasoning (Kambhampati et al., 2023)",
        source_type=SourceType.PREPRINT,
        publication_date="2023-05-07",
        search_query="demo",
        content="""\
This paper critically examines whether chain-of-thought prompting enables genuine multi-step
reasoning in LLMs or primarily serves as an output formatting mechanism that improves scores
through surface-level pattern matching.

Key findings:
- When output length is controlled for — ensuring standard prompting produces outputs of
  comparable length to CoT outputs — the accuracy advantage of CoT narrows substantially
  or disappears on several benchmarks.
- LLMs performing CoT frequently produce reasoning chains that are logically invalid but still
  arrive at correct answers, suggesting the chain is post-hoc rationalization rather than
  causal reasoning.
- On planning and constraint-satisfaction tasks that require genuine logical deduction, CoT
  provides no reliable improvement over direct prompting.
- The correlation between model size and CoT benefit observed by Wei et al. may reflect
  larger models' ability to produce fluent, plausible-sounding text, not deeper reasoning.
- CoT appears to help primarily on tasks where pattern matching on the reasoning format is
  sufficient — not on tasks that require novel logical inference.

Conclusion: CoT primarily improves output structure and exploits training distribution biases.
It does not represent genuine step-by-step reasoning of the kind humans perform.
""",
    ),
    RawDocument(
        doc_id="demo_doc_3",
        url="https://arxiv.org/abs/2202.12837",
        title="Rethinking the Role of Demonstrations: What Makes In-Context Learning Work? (Min et al., 2022)",
        source_type=SourceType.PEER_REVIEWED,
        publication_date="2022-02-25",
        search_query="demo",
        content="""\
This paper investigates what aspects of in-context learning demonstrations — including CoT
exemplars — actually drive performance. The study systematically ablates different components
of the demonstrations.

Key findings:
- The correctness of the reasoning steps in CoT demonstrations matters less than previously
  assumed: replacing correct reasoning steps with random or incorrect steps retains 80-90%
  of CoT performance on several benchmarks.
- What matters most is: (1) the format of the demonstration, (2) the relevance of the
  demonstration to the input domain, and (3) the label space being correct.
- This suggests CoT's benefit comes partly from cueing the model to produce structured outputs,
  not from the logical validity of the example reasoning chains.
- However, on tasks requiring precise arithmetic calculation (multi-digit multiplication,
  complex GSM8K problems), correct intermediate steps do matter — random steps degrade
  performance significantly.
- The result is task-dependent: CoT works as genuine reasoning scaffolding for arithmetic,
  but as a format cue for many commonsense and NLI tasks.

Conclusion: CoT's mechanism is heterogeneous — it is genuine reasoning scaffolding for
arithmetic tasks but primarily a format/structure signal for other task types.
""",
    ),
]
