"""
Example: Optimize the SmartAssistant's system prompt with Future AGI / GEPA.

The optimization loop:
  1. Start with an initial system prompt
  2. Run the agent on a small eval dataset
  3. Score responses (relevance + coherence)
  4. GEPA evolves the prompt over N iterations
  5. Return the best-scoring prompt

Run:
    pip install agent-opt   # or: pip install gepa
    python examples/optimize_agent.py
"""

from __future__ import annotations

import os

from agents import SmartAssistant
from futureagi import optimize_prompt, evaluate


# ------------------------------------------------------------------ #
# Evaluation dataset — input/output pairs for scoring the agent
# ------------------------------------------------------------------ #

EVAL_DATASET = [
    {
        "input": "Explain RAG in one sentence.",
        "expected_keywords": ["retrieval", "augmented", "generation", "context"],
    },
    {
        "input": "What is a transformer in deep learning?",
        "expected_keywords": ["attention", "encoder", "decoder", "sequence"],
    },
    {
        "input": "Name two benefits of prompt caching.",
        "expected_keywords": ["latency", "cost", "speed", "token"],
    },
    {
        "input": "What is chain-of-thought prompting?",
        "expected_keywords": ["step", "reasoning", "intermediate", "think"],
    },
    {
        "input": "How does RLHF improve LLMs?",
        "expected_keywords": ["human", "feedback", "reward", "fine-tuning"],
    },
]


def score_prompt(system_prompt: str) -> float:
    """
    Score a system prompt by running the agent on the eval dataset
    and averaging relevance + keyword coverage.
    """
    agent = SmartAssistant(
        system_prompt=system_prompt,
        enable_guardrails=False,  # skip during optimization for speed
        enable_evals=False,
    )

    scores = []
    for item in EVAL_DATASET:
        try:
            response = agent.run(item["input"])
            if response.blocked:
                scores.append(0.0)
                continue

            # Simple keyword coverage score
            output_lower = response.output.lower()
            hits = sum(1 for kw in item["expected_keywords"] if kw in output_lower)
            keyword_score = hits / len(item["expected_keywords"])

            # FutureAGI relevance eval
            eval_results = evaluate(
                ["relevance"],
                output=response.output,
                input=item["input"],
            )
            relevance_score = eval_results[0].score if eval_results else 0.5

            scores.append(0.5 * keyword_score + 0.5 * relevance_score)
        except Exception as e:
            print(f"  Scoring error: {e}")
            scores.append(0.0)

    return sum(scores) / len(scores) if scores else 0.0


def main():
    initial_prompt = """\
You are a helpful AI assistant. Answer questions accurately and concisely.\
"""

    print("Initial prompt:")
    print(f"  {initial_prompt}")
    print(f"\nBaseline score: {score_prompt(initial_prompt):.3f}")
    print("\nRunning GEPA optimization (10 iterations)...\n")

    result = optimize_prompt(
        initial_prompt=initial_prompt,
        evaluator_fn=score_prompt,
        algorithm="gepa",
        max_iterations=10,
    )

    print("=" * 60)
    print("Optimization complete")
    print("=" * 60)
    print(f"Algorithm:    {result.algorithm}")
    print(f"Iterations:   {result.iterations}")
    print(f"Best score:   {result.best_score:.3f}")
    print(f"\nOptimized prompt:\n{result.best_prompt}")


if __name__ == "__main__":
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("Set ANTHROPIC_API_KEY before running this example.")
    else:
        main()
