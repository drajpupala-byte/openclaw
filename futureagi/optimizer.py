"""Prompt optimization helpers wrapping agent-opt / GEPA."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional


class OptimizationAlgorithm(str):
    RANDOM = "random"
    BAYESIAN = "bayesian"
    PROTEGI = "protegi"
    META_PROMPT = "meta_prompt"
    PROMPT_WIZARD = "prompt_wizard"
    GEPA = "gepa"              # Genetic-Pareto — best overall performance


@dataclass
class OptimizationResult:
    best_prompt: str
    best_score: float
    iterations: int
    algorithm: str
    history: list[dict]


def optimize_prompt(
    initial_prompt: str,
    evaluator_fn: Callable[[str], float],
    dataset: Optional[list[dict]] = None,
    algorithm: str = OptimizationAlgorithm.GEPA,
    inference_model: str = "gpt-4o-mini",
    teacher_model: str = "gpt-4o",
    max_iterations: int = 10,
) -> OptimizationResult:
    """
    Optimize a prompt template using Future AGI's agent-opt library.

    Args:
        initial_prompt:  Starting prompt string (may contain {variables}).
        evaluator_fn:    Function that takes a candidate prompt and returns a float score.
        dataset:         Optional list of dicts to evaluate against.
        algorithm:       Optimization algorithm to use (default: GEPA).
        inference_model: Model used to generate candidate prompts.
        teacher_model:   Model used for reflective feedback (GEPA / Meta-Prompt).
        max_iterations:  Max optimization rounds.

    Returns:
        OptimizationResult with the best prompt and its score.

    Example::

        from futureagi import optimize_prompt

        def score(prompt: str) -> float:
            # run your agent with this prompt and return 0-1 quality score
            return evaluate(["relevance"], output=run_agent(prompt))[0].score

        result = optimize_prompt("Summarize this: {text}", score)
        print(result.best_prompt)
    """
    try:
        return _optimize_with_agent_opt(
            initial_prompt=initial_prompt,
            evaluator_fn=evaluator_fn,
            dataset=dataset,
            algorithm=algorithm,
            inference_model=inference_model,
            teacher_model=teacher_model,
            max_iterations=max_iterations,
        )
    except ImportError:
        return _optimize_with_gepa(
            initial_prompt=initial_prompt,
            evaluator_fn=evaluator_fn,
            max_iterations=max_iterations,
            algorithm=algorithm,
        )


def _optimize_with_agent_opt(
    initial_prompt: str,
    evaluator_fn: Callable[[str], float],
    dataset: Optional[list[dict]],
    algorithm: str,
    inference_model: str,
    teacher_model: str,
    max_iterations: int,
) -> OptimizationResult:
    """Use agent-opt (if installed) for optimization."""
    from agent_opt import LiteLLMGenerator, Evaluator, DataMapper

    algo_map = {
        OptimizationAlgorithm.RANDOM: _import("agent_opt", "RandomSearchOptimizer"),
        OptimizationAlgorithm.BAYESIAN: _import("agent_opt", "BayesianSearchOptimizer"),
        OptimizationAlgorithm.PROTEGI: _import("agent_opt", "ProTeGiOptimizer"),
        OptimizationAlgorithm.META_PROMPT: _import("agent_opt", "MetaPromptOptimizer"),
        OptimizationAlgorithm.PROMPT_WIZARD: _import("agent_opt", "PromptWizardOptimizer"),
        OptimizationAlgorithm.GEPA: _import("agent_opt", "GEPAOptimizer"),
    }

    OptimizerClass = algo_map.get(algorithm, algo_map[OptimizationAlgorithm.GEPA])

    class _FnEvaluator(Evaluator):
        def evaluate(self, prompt, **_):
            return evaluator_fn(prompt)

    optimizer = OptimizerClass(
        inference_model=inference_model,
        teacher_model=teacher_model,
        max_iterations=max_iterations,
    )

    generator = LiteLLMGenerator(
        model=inference_model,
        prompt_template=initial_prompt,
    )

    result = optimizer.optimize(
        generator=generator,
        evaluator=_FnEvaluator(),
        dataset=dataset or [],
        initial_prompts=[initial_prompt],
    )

    return OptimizationResult(
        best_prompt=getattr(result, "best_prompt", initial_prompt),
        best_score=getattr(result, "best_score", 0.0),
        iterations=max_iterations,
        algorithm=algorithm,
        history=getattr(result, "history", []),
    )


def _optimize_with_gepa(
    initial_prompt: str,
    evaluator_fn: Callable[[str], float],
    max_iterations: int,
    algorithm: str,
) -> OptimizationResult:
    """Use the gepa package directly (if agent-opt is not installed)."""
    from gepa import optimize_anything

    best_prompt = optimize_anything(
        initial_artifact=initial_prompt,
        evaluator=evaluator_fn,
        num_iterations=max_iterations,
    )
    return OptimizationResult(
        best_prompt=best_prompt,
        best_score=evaluator_fn(best_prompt),
        iterations=max_iterations,
        algorithm=algorithm,
        history=[],
    )


def _import(module: str, attr: str) -> Any:
    import importlib
    mod = importlib.import_module(module)
    return getattr(mod, attr)
