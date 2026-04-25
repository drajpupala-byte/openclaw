"""
SmartAssistant — Claude-powered Q&A agent instrumented with Future AGI.

Showcase agent demonstrating the full self-improvement loop:
  trace → guard → evaluate → optimize
"""

from __future__ import annotations

import os
from typing import Optional

from .base import BaseAgent, AgentResponse


DEFAULT_SYSTEM_PROMPT = """\
You are a concise, helpful assistant. Answer questions clearly and accurately.
- Keep responses under 200 words unless more detail is explicitly requested.
- Cite uncertainty honestly rather than hallucinating.
- Never produce harmful, hateful, or dangerous content.\
"""


class SmartAssistant(BaseAgent):
    """
    A Claude-powered assistant with Future AGI observability built in.

    Every call is:
      • Traced          → visible in Future AGI's dashboard
      • Guardrail-checked (input & output)
      • Evaluated       → relevance + toxicity scored automatically

    Usage::

        from agents import SmartAssistant

        agent = SmartAssistant(project_name="my-project")
        response = agent.run("Explain transformer attention in one paragraph.")

        print(response.output)
        print(response.eval_summary())
        print(f"Latency: {response.latency_ms:.0f}ms")
    """

    DEFAULT_EVAL_METRICS = ["relevance", "toxicity", "coherence"]

    def __init__(
        self,
        project_name: str = "openclaw-assistant",
        model: str = "claude-haiku-4-5-20251001",
        system_prompt: Optional[str] = None,
        max_tokens: int = 1024,
        eval_metrics: Optional[list[str]] = None,
        enable_guardrails: bool = True,
        enable_evals: bool = True,
        enable_tracing: bool = True,
        anthropic_api_key: Optional[str] = None,
    ) -> None:
        super().__init__(
            project_name=project_name,
            eval_metrics=eval_metrics or self.DEFAULT_EVAL_METRICS,
            enable_guardrails=enable_guardrails,
            enable_evals=enable_evals,
            enable_tracing=enable_tracing,
        )
        self.model = model
        self.system_prompt = system_prompt or DEFAULT_SYSTEM_PROMPT
        self.max_tokens = max_tokens
        self._api_key = anthropic_api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self._client = self._build_client()

        # Wire up Anthropic tracing if available
        try:
            self.fagi.instrument_anthropic()
        except Exception:
            pass

    def _build_client(self):
        try:
            import anthropic
            return anthropic.Anthropic(api_key=self._api_key)
        except ImportError:
            return None

    def _run(self, prompt: str) -> str:
        if self._client is None:
            raise ImportError(
                "anthropic package not installed. Run: pip install anthropic"
            )
        message = self._client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=self.system_prompt,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text

    # ------------------------------------------------------------------ #
    # Conversation helper
    # ------------------------------------------------------------------ #

    def chat(self, messages: list[dict]) -> AgentResponse:
        """
        Multi-turn conversation interface.

        Args:
            messages: List of {"role": "user"|"assistant", "content": str} dicts.

        The last message must be from the user. Input/output guards run on
        the last user message and the final assistant response respectively.
        """
        if not messages or messages[-1]["role"] != "user":
            raise ValueError("Last message must be from the user.")

        last_user_msg = messages[-1]["content"]

        # Re-use run() for guardrails + evals — call _chat_raw() for the actual LLM call
        import time
        t0 = time.monotonic()

        from futureagi.guardrails import GuardrailResult

        # Input guard on last user message
        if self.enable_guardrails:
            input_guard = self.fagi.guard_input(last_user_msg)
            if not input_guard.passed:
                from .base import AgentResponse
                return AgentResponse(
                    output="",
                    input_guard=input_guard,
                    blocked=True,
                    blocked_reason=f"Input blocked: {input_guard.blocked_categories}",
                    latency_ms=(time.monotonic() - t0) * 1000,
                )
        else:
            input_guard = None

        output = self._chat_raw(messages)

        if self.enable_guardrails:
            output_guard = self.fagi.guard_output(output)
            if not output_guard.passed:
                from .base import AgentResponse
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

        evals = (
            self.fagi.evaluate(self.eval_metrics, output=output, input=last_user_msg)
            if self.enable_evals else []
        )

        from .base import AgentResponse
        return AgentResponse(
            output=output,
            input_guard=input_guard,
            output_guard=output_guard,
            evals=evals,
            latency_ms=(time.monotonic() - t0) * 1000,
        )

    def _chat_raw(self, messages: list[dict]) -> str:
        if self._client is None:
            raise ImportError("anthropic package not installed.")
        message = self._client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=self.system_prompt,
            messages=messages,
        )
        return message.content[0].text
