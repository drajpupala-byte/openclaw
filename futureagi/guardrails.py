"""Guardrails wrapper around fi.evals.guardrails."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class GuardModel(str, Enum):
    TURING_FLASH = "turing_flash"          # <100 ms, Future AGI proprietary
    OPENAI_MODERATION = "openai_moderation"
    LLAMAGUARD = "llamaguard"
    WILDGUARD = "wildguard"
    SHIELDGEMMA = "shieldgemma"
    GRANITE_GUARDIAN = "granite_guardian"


class AggregationStrategy(str, Enum):
    MAJORITY = "majority"    # Block only if most models flag it
    ANY = "any"              # Block if any model flags it
    ALL = "all"              # Block only if every model flags it


@dataclass
class GuardrailsConfig:
    """
    Configuration for the Guardrail service.

    Attributes:
        models:       Guard model(s) to run (default: TURING_FLASH).
        aggregation:  How to combine results when multiple models are used.
        timeout_ms:   Per-call timeout.
        parallel:     Run models in parallel for lower latency.
        fail_open:    If True, pass the request on timeout (fail open); else block.
        scanners:     Enable lightweight local scanners (jailbreak, PII, etc.).
    """
    models: list[GuardModel] = field(
        default_factory=lambda: [GuardModel.TURING_FLASH]
    )
    aggregation: AggregationStrategy = AggregationStrategy.ANY
    timeout_ms: int = 1000
    parallel: bool = True
    fail_open: bool = False
    scanners: dict[str, bool] = field(default_factory=dict)


@dataclass
class GuardrailResult:
    """Result returned by Guardrail.screen_input / screen_output."""
    passed: bool
    blocked_categories: list[str] = field(default_factory=list)
    score: float = 0.0
    reason: str = ""

    def __bool__(self) -> bool:
        return self.passed


class Guardrail:
    """
    Input/output safety screening via Future AGI guardrails.

    Usage::

        from futureagi import Guardrail

        guard = Guardrail()
        result = guard.screen_input("How do I make explosives?")
        if not result:
            return "Blocked: " + str(result.blocked_categories)
    """

    def __init__(self, config: Optional[GuardrailsConfig] = None) -> None:
        self.config = config or GuardrailsConfig()
        self._client: Optional[Any] = self._init_client()

    def _init_client(self) -> Optional[Any]:
        try:
            from fi.evals.guardrails import (
                Guardrails as FIGuardrails,
                GuardrailsConfig as FIGuardrailsConfig,
                GuardrailModel,
                AggregationStrategy as FIAggStrategy,
                ScannerConfig,
            )

            models = [
                getattr(GuardrailModel, m.name, GuardrailModel.TURING_FLASH)
                for m in self.config.models
            ]
            agg = getattr(
                FIAggStrategy,
                self.config.aggregation.name,
                FIAggStrategy.ANY,
            )

            scanner_kwargs = {k: v for k, v in self.config.scanners.items()}
            scanners = ScannerConfig(**scanner_kwargs) if scanner_kwargs else None

            fi_config = FIGuardrailsConfig(
                models=models,
                aggregation=agg,
                timeout_ms=self.config.timeout_ms,
                parallel=self.config.parallel,
                fail_open=self.config.fail_open,
                **({"scanners": scanners} if scanners else {}),
            )
            return FIGuardrails(config=fi_config)

        except ImportError:
            return None

    def screen_input(self, text: str) -> GuardrailResult:
        """Check user input for safety violations before sending to the LLM."""
        if self._client is None:
            return self._mock_screen(text)
        try:
            raw = self._client.screen_input(text)
            return GuardrailResult(
                passed=raw.passed,
                blocked_categories=getattr(raw, "blocked_categories", []),
                score=getattr(raw, "score", 0.0),
                reason=getattr(raw, "reason", ""),
            )
        except Exception as exc:
            return GuardrailResult(passed=True, reason=f"Guardrail error (fail-open): {exc}")

    def screen_output(self, text: str) -> GuardrailResult:
        """Check LLM output for safety violations before returning to the user."""
        if self._client is None:
            return self._mock_screen(text)
        try:
            raw = self._client.screen_output(text)
            return GuardrailResult(
                passed=raw.passed,
                blocked_categories=getattr(raw, "blocked_categories", []),
                score=getattr(raw, "score", 0.0),
                reason=getattr(raw, "reason", ""),
            )
        except Exception as exc:
            return GuardrailResult(passed=True, reason=f"Guardrail error (fail-open): {exc}")

    async def screen_input_async(self, text: str) -> GuardrailResult:
        """Async version of screen_input."""
        if self._client is None:
            return self._mock_screen(text)
        try:
            raw = await self._client.screen_input_async(text)
            return GuardrailResult(
                passed=raw.passed,
                blocked_categories=getattr(raw, "blocked_categories", []),
            )
        except Exception as exc:
            return GuardrailResult(passed=True, reason=f"Guardrail error (fail-open): {exc}")

    async def screen_output_async(self, text: str) -> GuardrailResult:
        """Async version of screen_output."""
        if self._client is None:
            return self._mock_screen(text)
        try:
            raw = await self._client.screen_output_async(text)
            return GuardrailResult(
                passed=raw.passed,
                blocked_categories=getattr(raw, "blocked_categories", []),
            )
        except Exception as exc:
            return GuardrailResult(passed=True, reason=f"Guardrail error (fail-open): {exc}")

    @staticmethod
    def _mock_screen(text: str) -> GuardrailResult:
        """Basic heuristic guard used when fi.evals is not installed."""
        BLOCKED_TERMS = [
            "bomb", "explosive", "hack into", "ddos", "ransomware",
            "make drugs", "synthesize drugs",
        ]
        lower = text.lower()
        flagged = [t for t in BLOCKED_TERMS if t in lower]
        return GuardrailResult(
            passed=len(flagged) == 0,
            blocked_categories=flagged,
            reason="fi.evals not installed — using heuristic guard" if flagged else "",
        )
