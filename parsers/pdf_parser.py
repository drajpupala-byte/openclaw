"""
PDF bank statement parser using pdfplumber.
Extracts transactions from text-based PDFs (not scanned images).
"""

import re
from pathlib import Path
from typing import List, Optional
from datetime import date

from dateutil import parser as dateparser

from core.transaction import Transaction
from parsers.base import BaseParser

# Pattern: date + description + optional debit/credit + amount
# Examples:
#   01/15/2025  AMAZON.COM         123.45
#   Jan 15      Costco Wholesale  -250.00
TX_PATTERN = re.compile(
    r"(\d{1,2}[/\-]\d{1,2}[/\-]?\d{0,4}|[A-Z][a-z]{2}\s+\d{1,2})\s+"
    r"([A-Za-z0-9\s&\*\.\,\#\-\'\/]+?)\s+"
    r"([\-\+]?\$?[\d,]+\.\d{2})",
    re.MULTILINE
)


class PDFParser(BaseParser):

    def parse(self, filepath: Path) -> List[Transaction]:
        try:
            import pdfplumber
        except ImportError:
            print("    [WARN] pdfplumber not installed. Run: pip install pdfplumber")
            return []

        transactions = []
        source = self._guess_source(filepath.name)

        try:
            with pdfplumber.open(filepath) as pdf:
                year_hint = self._detect_year(pdf)
                for page in pdf.pages:
                    text = page.extract_text() or ""
                    transactions.extend(self._extract_from_text(text, source, year_hint))
        except Exception as e:
            print(f"    [WARN] Could not parse PDF {filepath.name}: {e}")

        return transactions

    def _extract_from_text(self, text: str, source: str, year_hint: int) -> List[Transaction]:
        transactions = []
        for match in TX_PATTERN.finditer(text):
            date_str, desc, amount_str = match.groups()
            tx_date = self._parse_date(date_str.strip(), year_hint)
            if tx_date is None:
                continue
            amount = self._parse_amount(amount_str)
            if amount is None:
                continue
            desc = " ".join(desc.split())   # normalize whitespace
            transactions.append(Transaction(
                date=tx_date,
                description=desc,
                amount=amount,
                source=source,
            ))
        return transactions

    def _detect_year(self, pdf) -> int:
        """Try to detect the statement year from the first page."""
        import datetime
        try:
            text = pdf.pages[0].extract_text() or ""
            years = re.findall(r"\b(20\d{2})\b", text)
            if years:
                return int(years[0])
        except Exception:
            pass
        return datetime.date.today().year

    def _parse_date(self, value: str, year_hint: int) -> Optional[date]:
        try:
            # Append year if missing
            if not re.search(r"\d{4}", value):
                value = f"{value}/{year_hint}"
            return dateparser.parse(value).date()
        except Exception:
            return None

    def _parse_amount(self, value: str) -> Optional[float]:
        try:
            return float(value.replace(",", "").replace("$", ""))
        except Exception:
            return None

    def _guess_source(self, filename: str) -> str:
        name = filename.lower()
        for bank in ["chase", "bofa", "wells_fargo", "citi", "amex", "discover", "capital_one"]:
            if bank.replace("_", "") in name.replace("_", ""):
                return bank
        return "bank"
