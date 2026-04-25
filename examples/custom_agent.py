"""
Example: Building your own agent on top of BaseAgent.

Shows how to wire any LLM (OpenAI, local, etc.) into the
Future AGI tracing + eval + guardrail stack in ~20 lines.

Run:
    python examples/custom_agent.py
"""

from __future__ import annotations

import os

from agents.base import BaseAgent, AgentResponse


class OpenAIAgent(BaseAgent):
    """Drop-in BaseAgent subclass using OpenAI's chat completions."""

    def __init__(self, model: str = "gpt-4o-mini", **kwargs) -> None:
        super().__init__(**kwargs)
        self.model = model
        try:
            import openai
            self._client = openai.OpenAI(api_key=os.environ.get("OPENAI_API_KEY", ""))
            self.fagi.instrument_openai()  # auto-trace all calls
        except ImportError:
            self._client = None

    def _run(self, prompt: str) -> str:
        if self._client is None:
            raise ImportError("Run: pip install openai")
        completion = self._client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=512,
        )
        return completion.choices[0].message.content


class EchoAgent(BaseAgent):
    """Trivial agent that echoes the prompt — useful for testing the stack."""

    def _run(self, prompt: str) -> str:
        return f"Echo: {prompt}"


def main():
    print("Testing EchoAgent with full FutureAGI stack\n")

    agent = EchoAgent(
        project_name="echo-demo",
        eval_metrics=["contains", "one_line"],
    )

    prompts = [
        "Hello, world!",
        "What time is it?",
        "How do I hack into a system?",  # should be blocked by guardrails
    ]

    for p in prompts:
        print(f"Input:  {p}")
        response = agent.run(p)
        print(f"Output: {response}")
        if not response.blocked:
            print(f"Evals:\n{response.eval_summary()}")
        print(f"Latency: {response.latency_ms:.1f}ms\n")


if __name__ == "__main__":
    main()
