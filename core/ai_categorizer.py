"""
AI-powered transaction categorizer.
Uses Claude API (cloud) or a local Ollama model (100% on-device) to categorize
transactions that keyword matching couldn't identify.
"""

import json
from typing import List, Optional

from core.transaction import Transaction

CATEGORIES = [
    "Office Supplies",
    "Business Meals",
    "Technology & Software",
    "Business Subscriptions",
    "Travel & Transportation",
    "Professional Services",
    "Advertising & Marketing",
    "Utilities & Communications",
    "Amazon Business",
    "Costco Business",
    "Insurance",
    "Rent & Facilities",
    "Shipping & Postage",
    "Banking & Finance",
    "Personal",
    "Uncategorized",
]

DEDUCTION_RATES = {
    "Business Meals": 0.5,
    "Personal": 0.0,
}

SYSTEM_PROMPT = (
    "You are a business expense categorizer for US tax purposes. "
    "Given a bank transaction description, reply with ONLY the single best category "
    "from this list (exact spelling):\n\n"
    + "\n".join(f"- {c}" for c in CATEGORIES)
    + "\n\nReply with the category name only. No explanation."
)

# How many uncategorized items to batch before flushing (keeps token usage low)
BATCH_SIZE = 20


class AICategorizer:
    """
    Wraps either the Anthropic Claude API or a local Ollama model.

    Usage:
        cat = AICategorizer(backend="claude")   # needs ANTHROPIC_API_KEY
        cat = AICategorizer(backend="local",    # needs ollama running
                            local_model="llama3.2")
    """

    def __init__(self, backend: str = "claude", local_model: str = "llama3.2"):
        self.backend = backend.lower()
        self.local_model = local_model
        self._client = None   # lazy-init

    # ── public API ─────────────────────────────────────────────────────────────

    def enhance(self, transactions: List[Transaction]) -> List[Transaction]:
        """Re-categorize any Uncategorized transactions using the AI backend."""
        uncategorized = [t for t in transactions if t.category == "Uncategorized" and t.is_expense]
        if not uncategorized:
            return transactions

        print(f"    AI: categorizing {len(uncategorized)} uncategorized transaction(s) …")
        improved = 0

        for t in uncategorized:
            cat = self._classify(t.description)
            if cat and cat != "Uncategorized":
                t.category = cat
                t.deduction_rate = DEDUCTION_RATES.get(cat, 1.0 if cat != "Personal" else 0.0)
                improved += 1

        print(f"    AI: resolved {improved} / {len(uncategorized)} transactions")
        return transactions

    # ── backend dispatch ───────────────────────────────────────────────────────

    def _classify(self, description: str) -> Optional[str]:
        try:
            if self.backend == "claude":
                return self._classify_claude(description)
            elif self.backend == "local":
                return self._classify_ollama(description)
        except Exception as exc:
            print(f"    AI warning: {exc}")
        return None

    # ── Claude API ─────────────────────────────────────────────────────────────

    def _classify_claude(self, description: str) -> Optional[str]:
        if self._client is None:
            try:
                import anthropic
                self._client = anthropic.Anthropic()
            except ImportError:
                raise RuntimeError("anthropic package not installed. Run: pip install anthropic")

        response = self._client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=30,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": description}],
        )
        return self._clean(response.content[0].text)

    # ── Local Ollama ───────────────────────────────────────────────────────────

    def _classify_ollama(self, description: str) -> Optional[str]:
        try:
            import ollama
        except ImportError:
            raise RuntimeError("ollama package not installed. Run: pip install ollama")

        response = ollama.chat(
            model=self.local_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": description},
            ],
        )
        return self._clean(response["message"]["content"])

    # ── helpers ────────────────────────────────────────────────────────────────

    @staticmethod
    def _clean(raw: str) -> Optional[str]:
        """Return the category if it exactly matches our list, else None."""
        text = raw.strip().strip('"').strip("'")
        # Exact match
        if text in CATEGORIES:
            return text
        # Case-insensitive fallback
        lower = text.lower()
        for cat in CATEGORIES:
            if cat.lower() == lower:
                return cat
        return None
