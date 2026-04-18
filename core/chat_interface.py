"""
Natural-language Q&A interface for your tax data.
Backed by Claude API or a local Ollama model.

  python main.py chat --year 2025
  python main.py chat --year 2025 --ai-backend local --local-model gemma3
"""

import sys
from collections import defaultdict
from typing import List

from core.transaction import Transaction

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

SYSTEM_PROMPT_TEMPLATE = """You are a helpful business tax advisor.
You have access to the following financial summary for {business} ({year}):

{summary}

Answer questions clearly and concisely. Use dollar amounts where relevant.
When tax advice is involved, remind the user to consult a licensed CPA.
If a question cannot be answered from the data provided, say so."""


def _build_summary(transactions: List[Transaction], year: int, business: str) -> str:
    expenses = [t for t in transactions if t.is_expense]
    total_exp = sum(abs(t.amount) for t in expenses)
    total_ded = sum(t.deductible_amount for t in expenses)

    # Category totals
    by_cat: dict = defaultdict(lambda: {"total": 0.0, "count": 0})
    for t in expenses:
        by_cat[t.category]["total"]  += abs(t.amount)
        by_cat[t.category]["count"]  += 1

    # Monthly totals
    monthly: dict = defaultdict(float)
    for t in expenses:
        monthly[t.month] += abs(t.amount)

    # Source totals
    by_src: dict = defaultdict(float)
    for t in expenses:
        by_src[t.source] += abs(t.amount)

    lines = [
        f"Business: {business}",
        f"Tax Year: {year}",
        f"Total Expenses: ${total_exp:,.2f}",
        f"Total Deductible: ${total_ded:,.2f}",
        f"Estimated Tax Savings (24% bracket): ${total_ded * 0.24:,.2f}",
        "",
        "Expenses by Category:",
    ]
    for cat, data in sorted(by_cat.items(), key=lambda x: -x[1]["total"]):
        lines.append(f"  {cat}: ${data['total']:,.2f}  ({data['count']} transactions)")

    lines += ["", "Monthly Totals:"]
    for m in range(1, 13):
        if monthly[m]:
            lines.append(f"  {MONTHS[m-1]}: ${monthly[m]:,.2f}")

    lines += ["", "By Source:"]
    for src, amt in sorted(by_src.items(), key=lambda x: -x[1]):
        lines.append(f"  {src}: ${amt:,.2f}")

    return "\n".join(lines)


class TaxChatInterface:
    """Interactive or single-shot Q&A using Claude or a local LLM."""

    def __init__(
        self,
        transactions: List[Transaction],
        year: int,
        business_name: str,
        backend: str = "claude",
        local_model: str = "llama3.2",
    ):
        self.transactions = transactions
        self.year = year
        self.business_name = business_name
        self.backend = backend.lower()
        self.local_model = local_model
        self._client = None
        self._history: List[dict] = []   # for multi-turn context

        self._summary = _build_summary(transactions, year, business_name)
        self._system = SYSTEM_PROMPT_TEMPLATE.format(
            business=business_name,
            year=year,
            summary=self._summary,
        )

    # ── public ─────────────────────────────────────────────────────────────────

    def ask(self, question: str) -> str:
        """Single question → answer string."""
        self._history.append({"role": "user", "content": question})
        answer = self._dispatch()
        self._history.append({"role": "assistant", "content": answer})
        return answer

    def repl(self):
        """Run an interactive REPL until the user types 'exit' or Ctrl-C."""
        print()
        print("=" * 60)
        print(f" OpenClaw AI Tax Advisor — {self.business_name} {self.year}")
        print(f" Backend : {self.backend.upper()}"
              + (f" ({self.local_model})" if self.backend == "local" else ""))
        print("=" * 60)
        print(" Ask anything about your expenses and tax deductions.")
        print(' Type "exit" or press Ctrl-C to quit.\n')
        print(f" Loaded {len([t for t in self.transactions if t.is_expense])} expense transactions.\n")

        while True:
            try:
                question = input(" You: ").strip()
            except (KeyboardInterrupt, EOFError):
                print("\n Goodbye!")
                break

            if not question:
                continue
            if question.lower() in ("exit", "quit", "q", "bye"):
                print(" Goodbye!")
                break

            try:
                answer = self.ask(question)
                print(f"\n Advisor: {answer}\n")
            except Exception as exc:
                print(f"\n [Error] {exc}\n")

    # ── backend dispatch ───────────────────────────────────────────────────────

    def _dispatch(self) -> str:
        if self.backend == "claude":
            return self._ask_claude()
        elif self.backend == "local":
            return self._ask_ollama()
        return "Unknown backend. Use --ai-backend claude or local."

    # ── Claude API ─────────────────────────────────────────────────────────────

    def _ask_claude(self) -> str:
        if self._client is None:
            try:
                import anthropic
                self._client = anthropic.Anthropic()
            except ImportError:
                raise RuntimeError("anthropic package not installed. Run: pip install anthropic")

        response = self._client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=512,
            system=self._system,
            messages=self._history,
        )
        return response.content[0].text.strip()

    # ── Local Ollama ───────────────────────────────────────────────────────────

    def _ask_ollama(self) -> str:
        try:
            import ollama
        except ImportError:
            raise RuntimeError("ollama package not installed. Run: pip install ollama")

        messages = [{"role": "system", "content": self._system}] + self._history
        response = ollama.chat(model=self.local_model, messages=messages)
        return response["message"]["content"].strip()
