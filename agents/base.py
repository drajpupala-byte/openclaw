"""Base agent with Future AGI tracing, guardrails, and evals wired in."""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

from futureagi import FutureAGI
from futureagi.evaluator import EvalResult
from futureagi.guardrails import GuardrailResult


@dataclass
class AgentResponse:
    """Structured response returned by every BaseAgent."""
    output: str
    input_guard: Optional[GuardrailResult] = None
    output_guard: Optional[GuardrailResult] = None
    evals: list[EvalResult] = field(default_factory=list)
    latency_ms: float = 0.0
    blocked: bool = False
    blocked_reason: str = ""

    def __str__(self) -> str:
        if self.blocked:
            return f"[BLOCKED] {self.blocked_reason}"
        return self.output

    def passed_all_evals(self, threshold: float = 0.7) -> bool:
        return all(e.score >= threshold for e in self.evals)

    def eval_summary(self) -> str:
        if not self.evals:
            return "No evals run."
        lines = [f"  {e.eval_name}: {'✓' if e.passed else '✗'} ({e.score:.2f})" for e in self.evals]
        return "\n".join(lines)


class BaseAgent(ABC):
    """
    Abstract base class for Future AGI-instrumented agents.

    Subclasses override `_run()` with their LLM logic.
    Tracing, guardrails, and evals are applied automatically in `run()`.

    Usage::

        class MyAgent(BaseAgent):
            def _run(self, prompt: str) -> str:
                return my_llm(prompt)

        agent = MyAgent(project_name="my-project")
        response = agent.run("What is 2+2?")
        print(response.output)
        print(response.eval_summary())
    """

    DEFAULT_EVAL_METRICS: list[str] = ["relevance", "toxicity"]

    def __init__(
        self,
        project_name: str = "openclaw",
        eval_metrics: Optional[list[str]] = None,
        enable_guardrails: bool = True,
        enable_evals: bool = True,
        enable_tracing: bool = True,
        fagi: Optional[FutureAGI] = None,
    ) -> None:
        self.fagi = fagi or FutureAGI(
            project_name=project_name,
            enable_tracing=enable_tracing,
            enable_guardrails=enable_guardrails,
            enable_evals=enable_evals,
        )
        self.eval_metrics = eval_metrics or self.DEFAULT_EVAL_METRICS
        self.enable_guardrails = enable_guardrails
        self.enable_evals = enable_evals

    @abstractmethod
    def _run(self, prompt: str) -> str:
        """Override with your LLM call logic. Return the raw text output."""

    def run(self, prompt: str) -> AgentResponse:
        """
        Run the agent with full Future AGI instrumentation:
          1. Guard input
          2. Trace + execute _run()
          3. Guard output
          4. Evaluate output
        """
        t0 = time.monotonic()

        # 1. Input guardrail
        if self.enable_guardrails:
            input_guard = self.fagi.guard_input(prompt)
            if not input_guard.passed:
                return AgentResponse(
                    output="",
                    input_guard=input_guard,
                    blocked=True,
                    blocked_reason=f"Input blocked: {input_guard.blocked_categories}",
                    latency_ms=(time.monotonic() - t0) * 1000,
                )
        else:
            input_guard = None

        # 2. LLM call (wrapped in a trace span)
        try:
            from futureagi.tracer import span
            with span(f"{self.__class__.__name__}.run", {"input_len": len(prompt)}):
                output = self._run(prompt)
        except Exception:
            output = self._run(prompt)

        # 3. Output guardrail
        if self.enable_guardrails:
            output_guard = self.fagi.guard_output(output)
            if not output_guard.passed:
                return AgentResponse(
                    output="",
                    input_guard=input_guard,
                    output_guard=output_guard,
                    blocked=True,
                    blocked_reason=f"Output blocked: {output_guard.blocked_categories}",
                    latency_ms=(time.monotonic() - t0) * 1000,
                )
        else:
            output_guard = None

        # 4. Evaluate
        evals: list[EvalResult] = []
        if self.enable_evals:
            evals = self.fagi.evaluate(
                self.eval_metrics,
                output=output,
                input=prompt,
            )

        return AgentResponse(
            output=output,
            input_guard=input_guard,
            output_guard=output_guard,
            evals=evals,
            latency_ms=(time.monotonic() - t0) * 1000,
        )
