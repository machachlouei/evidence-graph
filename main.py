#!/usr/bin/env python3
from __future__ import annotations

"""CLI entry point for the Deep Research Agent System."""

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _check_env(required_keys: list[str] | None = None) -> None:
    if required_keys is None:
        required_keys = ["GOOGLE_API_KEY", "GROQ_API_KEY", "TAVILY_API_KEY"]
    missing = [k for k in required_keys if not os.getenv(k)]
    if missing:
        print(f"Error: missing environment variables: {', '.join(missing)}", file=sys.stderr)
        print("Copy .env.example to .env and fill in your API keys.", file=sys.stderr)
        sys.exit(1)


def cmd_research(args: argparse.Namespace) -> None:
    _check_env()  # uses default (all 3 keys)
    from src.orchestration.workflow import run_research

    print(f"Starting research: {args.query!r}")
    print(f"Output directory: {args.output}")
    result = run_research(args.query, output_dir=args.output)
    print(f"\nDone — session {result['session_id']}")
    print(f"  Iterations:  {result['iterations']}")
    print(f"  Claims:      {result['claims']}")
    print(f"  Report:      {result['report_path']}")
    print(f"  Graph:       {result['graph_path']}")
    print(f"  Trace:       {result['trace_path']}")


def cmd_baseline(args: argparse.Namespace) -> None:
    _check_env()
    from src.baseline.pipeline import run_baseline

    print(f"Running baseline pipeline: {args.query!r}")
    result = run_baseline(args.query, output_dir=args.output)
    print(f"\nDone — session {result['session_id']}")
    print(f"  Sources:  {result['sources']}")
    print(f"  Report:   {result['report_path']}")


def cmd_ablation(args: argparse.Namespace) -> None:
    """Run both the full system and baseline on the same query for comparison."""
    _check_env()
    query = args.query or (
        "Is chain-of-thought prompting an effective reasoning strategy for LLMs, "
        "or does it primarily improve output formatting? "
        "The literature disagrees — find the real fault lines and explain what accounts for the conflicting results."
    )
    print("=== ABLATION: Evidence Graph System vs. Naive Pipeline ===")
    print(f"Query: {query!r}\n")

    from src.baseline.pipeline import run_baseline
    from src.orchestration.workflow import run_research

    if args.max_iterations:
        os.environ["RESEARCH_MAX_ITERATIONS"] = str(args.max_iterations)
    if args.search_budget:
        os.environ["RESEARCH_SEARCH_BUDGET"] = str(args.search_budget)

    print("[1/2] Running Evidence Graph system...")
    full = run_research(query, output_dir=f"{args.output}/full_system")

    print("[2/2] Running naive pipeline baseline...")
    base = run_baseline(query, output_dir=f"{args.output}/baseline")

    print("\n=== Results ===")
    print(f"Full system:  {full['iterations']} iterations, {full['claims']} claims → {full['report_path']}")
    print(f"Baseline:     {base['iterations']} iteration, {base['sources']} sources → {base['report_path']}")
    print("\nSee outputs/ for full reports, graph JSON, and traces.")


def cmd_demo(args: argparse.Namespace) -> None:
    _check_env(required_keys=["GOOGLE_API_KEY", "GROQ_API_KEY"])
    from src.demo.run_demo import run_demo

    print("=== DEMO: Evidence Graph System (fixture documents, ~18 LLM calls) ===")
    print("Query: CoT prompting — contradictory sources\n")
    result = run_demo(output_dir=args.output)
    print(f"\nDone — session {result['session_id']}")
    print(f"  Claims extracted:        {result['claims']}")
    print(f"  Nodes in graph:          {result['nodes']}")
    print(f"  Contradiction edges:     {result['contradiction_edges']}")
    print(f"  Unresolved:              {result['unresolved_contradictions']}")
    print(f"  Total LLM calls:         {result['trace_summary']['total_searches'] + result['trace_summary']['total_events']}")
    print(f"  Report: {result['report_path']}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Deep Research Agent System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands:
  demo       End-to-end test using fixtures (~18 LLM calls, no web search)
  research   Run the full Evidence Graph research system on a query
  baseline   Run the naive pipeline baseline
  ablation   Run both on Test Case 2 (CoT contradictory sources) for comparison

Examples:
  python main.py demo
  python main.py research "What are the risks of using synthetic data to train LLMs?"
  python main.py ablation
""",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_demo = sub.add_parser("demo", help="End-to-end test with fixtures (~18 LLM calls)")
    p_demo.add_argument("--output", default="outputs/demo", help="Output directory")
    p_demo.set_defaults(func=cmd_demo)

    p_research = sub.add_parser("research", help="Run full research system")
    p_research.add_argument("query", help="Research question")
    p_research.add_argument("--output", default="outputs", help="Output directory")
    p_research.set_defaults(func=cmd_research)

    p_baseline = sub.add_parser("baseline", help="Run naive pipeline baseline")
    p_baseline.add_argument("query", help="Research question")
    p_baseline.add_argument("--output", default="outputs/baseline", help="Output directory")
    p_baseline.set_defaults(func=cmd_baseline)

    p_ablation = sub.add_parser("ablation", help="Run ablation comparison (Test Case 2)")
    p_ablation.add_argument("--query", default=None, help="Custom query (defaults to Test Case 2)")
    p_ablation.add_argument("--output", default="outputs/ablation", help="Output directory")
    p_ablation.add_argument("--max-iterations", type=int, default=None, dest="max_iterations", help="Override max research iterations")
    p_ablation.add_argument("--search-budget", type=int, default=None, dest="search_budget", help="Override search budget")
    p_ablation.set_defaults(func=cmd_ablation)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
