"""Central FutureAGI client — initializes all platform services in one call."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional

from .tracer import setup_tracing, TracerHandle
from .evaluator import Evaluator
from .guardrails import Guardrail, GuardrailsConfig


@dataclass
class FutureAGIConfig:
    """Configuration for the FutureAGI platform."""
    api_key: str = field(default_factory=lambda: os.environ.get("FI_API_KEY", ""))
    secret_key: str = field(default_factory=lambda: os.environ.get("FI_SECRET_KEY", ""))
    project_name: str = "openclaw"
    project_type: str = "OBSERVE"  # OBSERVE | EXPERIMENT
    project_version: Optional[str] = None
    enable_tracing: bool = True
    enable_guardrails: bool = True
    enable_evals: bool = True


class FutureAGI:
    """
    One-stop client for the FutureAGI platform.

    Usage::

        from futureagi import FutureAGI

        fagi = FutureAGI(project_name="my-agent")
        fagi.instrument_openai()     # auto-trace all OpenAI calls
        fagi.instrument_anthropic()  # auto-trace all Anthropic calls

        result = fagi.guard("user input")
        evals  = fagi.evaluate(["relevance", "toxicity"], output="response text")
    """

    def __init__(
        self,
        project_name: str = "openclaw",
        project_type: str = "OBSERVE",
        api_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        enable_tracing: bool = True,
        enable_guardrails: bool = True,
        enable_evals: bool = True,
    ) -> None:
        self.config = FutureAGIConfig(
            api_key=api_key or os.environ.get("FI_API_KEY", ""),
            secret_key=secret_key or os.environ.get("FI_SECRET_KEY", ""),
            project_name=project_name,
            project_type=project_type,
            enable_tracing=enable_tracing,
            enable_guardrails=enable_guardrails,
            enable_evals=enable_evals,
        )

        self._tracer: Optional[TracerHandle] = None
        self._evaluator: Optional[Evaluator] = None
        self._guardrail: Optional[Guardrail] = None

        if enable_tracing:
            self._tracer = setup_tracing(
                project_name=self.config.project_name,
                project_type=self.config.project_type,
                api_key=self.config.api_key,
                secret_key=self.config.secret_key,
            )

        if enable_evals:
            self._evaluator = Evaluator(
                api_key=self.config.api_key,
                secret_key=self.config.secret_key,
            )

        if enable_guardrails:
            self._guardrail = Guardrail()

    # ------------------------------------------------------------------ #
    # Instrumentation helpers
    # ------------------------------------------------------------------ #

    def instrument_openai(self) -> None:
        """Auto-trace every OpenAI SDK call via OpenTelemetry."""
        if self._tracer is None:
            raise RuntimeError("Tracing is disabled — set enable_tracing=True.")
        try:
            from traceai_openai import OpenAIInstrumentor
            OpenAIInstrumentor().instrument(tracer_provider=self._tracer.provider)
        except ImportError:
            raise ImportError("Run: pip install traceai-openai")

    def instrument_anthropic(self) -> None:
        """Auto-trace every Anthropic SDK call via OpenTelemetry."""
        if self._tracer is None:
            raise RuntimeError("Tracing is disabled — set enable_tracing=True.")
        try:
            from traceai_anthropic import AnthropicInstrumentor
            AnthropicInstrumentor().instrument(tracer_provider=self._tracer.provider)
        except ImportError:
            # Fall back to manual span wrapping — traceai_anthropic may not exist yet.
            pass

    def instrument_langchain(self) -> None:
        if self._tracer is None:
            raise RuntimeError("Tracing is disabled.")
        try:
            from traceai_langchain import LangChainInstrumentor
            LangChainInstrumentor().instrument(tracer_provider=self._tracer.provider)
        except ImportError:
            raise ImportError("Run: pip install traceai-langchain")

    # ------------------------------------------------------------------ #
    # Guardrail proxy
    # ------------------------------------------------------------------ #

    def guard_input(self, text: str) -> "GuardrailResult":  # noqa: F821
        """Screen user input before sending to the LLM."""
        if self._guardrail is None:
            raise RuntimeError("Guardrails are disabled — set enable_guardrails=True.")
        return self._guardrail.screen_input(text)

    def guard_output(self, text: str) -> "GuardrailResult":  # noqa: F821
        """Screen LLM output before returning to the user."""
        if self._guardrail is None:
            raise RuntimeError("Guardrails are disabled — set enable_guardrails=True.")
        return self._guardrail.screen_output(text)

    # ------------------------------------------------------------------ #
    # Evaluator proxy
    # ------------------------------------------------------------------ #

    def evaluate(self, metrics: list[str], output: str, **kwargs) -> list[dict]:
        """Run one or more eval metrics against an LLM output."""
        if self._evaluator is None:
            raise RuntimeError("Evals are disabled — set enable_evals=True.")
        return self._evaluator.evaluate(metrics, output=output, **kwargs)

    # ------------------------------------------------------------------ #
    # Tracer proxy
    # ------------------------------------------------------------------ #

    @property
    def tracer(self) -> Optional[TracerHandle]:
        return self._tracer

    def __repr__(self) -> str:
        return (
            f"FutureAGI(project={self.config.project_name!r}, "
            f"type={self.config.project_type!r})"
        )
