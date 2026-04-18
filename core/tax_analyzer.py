import json
from pathlib import Path
from typing import List
from collections import defaultdict

from core.transaction import Transaction

CONFIG_PATH = Path(__file__).parent.parent / "config" / "categories.json"


class TaxAnalyzer:
    def __init__(self):
        with open(CONFIG_PATH) as f:
            self.config = json.load(f)
        self.categories = self.config["categories"]
        self._build_keyword_index()

    def _build_keyword_index(self):
        """Build a fast lookup: keyword -> (category, deduction_rate)."""
        self.keyword_map = {}
        for cat_name, cat_data in self.categories.items():
            rate = cat_data["deduction_rate"]
            for kw in cat_data["keywords"]:
                self.keyword_map[kw.lower()] = (cat_name, rate)

    def categorize(self, transaction: Transaction) -> Transaction:
        """Assign category and deduction rate based on description."""
        desc = transaction.description.lower()

        # Source-based shortcut for Amazon/Costco dedicated parsers
        if transaction.source == "amazon":
            transaction.category = "Amazon Business"
            transaction.deduction_rate = self.categories["Amazon Business"]["deduction_rate"]
            return transaction
        if transaction.source == "costco":
            transaction.category = "Costco Business"
            transaction.deduction_rate = self.categories["Costco Business"]["deduction_rate"]
            return transaction

        # Keyword matching — longest match wins
        best_match = None
        best_len = 0
        for kw, (cat, rate) in self.keyword_map.items():
            if kw in desc and len(kw) > best_len:
                best_match = (cat, rate)
                best_len = len(kw)

        if best_match:
            transaction.category = best_match[0]
            transaction.deduction_rate = best_match[1]

        return transaction

    def categorize_transactions(self, transactions: List[Transaction]) -> List[Transaction]:
        return [self.categorize(t) for t in transactions]

    def monthly_summary(self, transactions: List[Transaction]) -> dict:
        """Return dict: month -> {category -> {total, deductible}}."""
        summary = defaultdict(lambda: defaultdict(lambda: {"total": 0.0, "deductible": 0.0}))
        for t in transactions:
            if t.is_expense:
                summary[t.month][t.category]["total"] += abs(t.amount)
                summary[t.month][t.category]["deductible"] += t.deductible_amount
        return summary

    def annual_summary(self, transactions: List[Transaction]) -> dict:
        """Return dict: category -> {total, deductible, count}."""
        summary = defaultdict(lambda: {"total": 0.0, "deductible": 0.0, "count": 0})
        for t in transactions:
            if t.is_expense:
                summary[t.category]["total"] += abs(t.amount)
                summary[t.category]["deductible"] += t.deductible_amount
                summary[t.category]["count"] += 1
        return summary

    def estimate_tax_savings(self, deductible_total: float, gross_income: float = 0) -> dict:
        """Estimate federal tax savings at common brackets."""
        brackets = [0.10, 0.12, 0.22, 0.24, 0.32, 0.35, 0.37]
        se_rate = self.config["tax_brackets_2025"]["self_employment_rate"]
        savings = {}
        for rate in brackets:
            savings[f"{int(rate*100)}%"] = deductible_total * rate
        savings["Self-Employment (15.3%)"] = deductible_total * se_rate * 0.5
        return savings
