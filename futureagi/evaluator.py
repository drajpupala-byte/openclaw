"""Evaluation helpers wrapping fi.evals."""

from __future__ import annotations

from typing import Any, Optional


# 50+ built-in metrics supported by Future AGI
AVAILABLE_METRICS = [
    # Heuristic (fast, no LLM needed)
    "contains", "one_line", "is_json", "length_check",
    # Quality (LLM-as-Judge)
    "relevance", "faithfulness", "groundedness", "coherence",
    "summarization_quality", "completeness",
    # Safety
    "toxicity", "violence", "harmful_content", "hate_speech",
    # Bias
    "gender_bias", "cultural_bias",
    # Tone
    "tone", "formality",
]


class EvalResult:
    """Result from a single evaluation metric."""

    def __init__(
        self,
        eval_name: str,
        score: float,
        passed: bool,
        reason: str = "",
        latency_ms: float = 0.0,
    ) -> None:
        self.eval_name = eval_name
        self.score = score
        self.passed = passed
        self.reason = reason
        self.latency_ms = latency_ms

    def __repr__(self) -> str:
        status = "PASS" if self.passed else "FAIL"
        return f"EvalResult({self.eval_name}: {status}, score={self.score:.2f})"


class Evaluator:
    """Wrapper around fi.evals for running LLM evaluations."""

    def __init__(
        self,
        api_key: str = "",
        secret_key: str = "",
        default_model: str = "turing_flash",
    ) -> None:
        self.api_key = api_key
        self.secret_key = secret_key
        self.default_model = default_model
        self._client: Optional[Any] = self._init_client()

    def _init_client(self) -> Optional[Any]:
        try:
            from fi.evals import Evaluator as FIEvaluator
            if self.api_key and self.secret_key:
                return FIEvaluator(
                    fi_api_key=self.api_key,
                    fi_secret_key=self.secret_key,
                )
            return FIEvaluator()
        except ImportError:
            return None

    def evaluate(
        self,
        metrics: list[str],
        output: str,
        input: Optional[str] = None,
        context: Optional[str] = None,
        model: Optional[str] = None,
        **kwargs,
    ) -> list[EvalResult]:
        """
        Run one or more metrics against an LLM output.

        Args:
            metrics:  List of metric names (e.g. ["relevance", "toxicity"]).
            output:   The LLM response to evaluate.
            input:    Original user input (required for relevance / faithfulness).
            context:  Retrieved context (required for groundedness / faithfulness).
            model:    Override the judge model (default: turing_flash).

        Returns:
            List of EvalResult objects, one per metric.
        """
        if self._client is None:
            return self._mock_evaluate(metrics, output)

        results = []
        judge = model or self.default_model

        for metric in metrics:
            try:
                eval_input: dict[str, Any] = {"output": output}
                if input is not None:
                    eval_input["input"] = input
                if context is not None:
                    eval_input["context"] = context

                raw = self._client.evaluate(
                    eval_templates=metric,
                    inputs=eval_input,
                    model_name=judge,
                )
                results.append(EvalResult(
                    eval_name=metric,
                    score=getattr(raw, "score", 0.0),
                    passed=getattr(raw, "passed", True),
                    reason=getattr(raw, "reason", ""),
                    latency_ms=getattr(raw, "latency_ms", 0.0),
                ))
            except Exception as exc:
                results.append(EvalResult(
                    eval_name=metric,
                    score=0.0,
                    passed=False,
                    reason=f"Eval error: {exc}",
                ))

        return results

    def _mock_evaluate(self, metrics: list[str], output: str) -> list[EvalResult]:
        """Fallback when fi.evals is not installed — returns placeholder results."""
        return [
            EvalResult(
                eval_name=m,
                score=0.0,
                passed=True,
                reason="fi.evals not installed — install futureagi to run real evals",
            )
            for m in metrics
        ]


def evaluate(
    metrics: list[str],
    output: str,
    input: Optional[str] = None,
    context: Optional[str] = None,
    model: str = "turing_flash",
) -> list[EvalResult]:
    """
    Module-level convenience function (mirrors fi.evals.evaluate).

    Usage::

        from futureagi import evaluate

        results = evaluate(["relevance", "toxicity"], output=response, input=query)
        for r in results:
            print(r)
    """
    ev = Evaluator()
    return ev.evaluate(metrics, output=output, input=input, context=context, model=model)


def batch_evaluate(
    records: list[dict],
    metrics: list[str],
    model: str = "turing_flash",
) -> list[list[EvalResult]]:
    """
    Evaluate multiple output records at once.

    Each record dict must have an "output" key; "input" and "context" are optional.
    Returns a list of EvalResult lists aligned with the input records.
    """
    ev = Evaluator()
    return [
        ev.evaluate(
            metrics,
            output=rec["output"],
            input=rec.get("input"),
            context=rec.get("context"),
            model=model,
        )
        for rec in records
    ]
