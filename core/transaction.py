from dataclasses import dataclass, field
from datetime import date


@dataclass
class Transaction:
    date: date
    description: str
    amount: float          # negative = expense, positive = income/credit
    source: str            # 'bank', 'credit_card', 'amazon', 'costco'
    category: str = "Uncategorized"
    deduction_rate: float = 0.0
    notes: str = ""
    order_id: str = ""     # for Amazon/Costco order tracking

    @property
    def is_expense(self) -> bool:
        return self.amount < 0

    @property
    def is_deductible(self) -> bool:
        return self.deduction_rate > 0 and self.is_expense

    @property
    def deductible_amount(self) -> float:
        if self.is_deductible:
            return abs(self.amount) * self.deduction_rate
        return 0.0

    @property
    def month(self) -> int:
        return self.date.month

    @property
    def year(self) -> int:
        return self.date.year
