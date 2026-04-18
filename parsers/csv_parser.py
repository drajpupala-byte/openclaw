"""Generic CSV bank/credit-card statement parser with auto-column detection."""

from pathlib import Path
from typing import List, Optional
from datetime import date

import pandas as pd
from dateutil import parser as dateparser

from core.transaction import Transaction
from parsers.base import BaseParser

# Candidate column name sets (lowercase)
DATE_COLS   = {"date", "transaction date", "trans date", "posting date", "post date", "value date"}
DESC_COLS   = {"description", "merchant", "payee", "memo", "details", "transaction description",
               "transaction detail", "name", "narrative", "particulars"}
AMOUNT_COLS = {"amount", "transaction amount", "debit amount", "credit amount",
               "withdrawal", "deposit", "debit", "credit"}
DEBIT_COLS  = {"debit", "withdrawal", "debit amount", "withdrawals"}
CREDIT_COLS = {"credit", "deposit", "credit amount", "deposits"}


def _find_col(columns: List[str], candidates: set) -> Optional[str]:
    for col in columns:
        if col.strip().lower() in candidates:
            return col
    return None


class GenericCSVParser(BaseParser):
    """
    Handles most bank and credit-card CSV exports.
    Supports:
      - Single 'Amount' column (negative = debit)
      - Separate 'Debit' / 'Credit' columns
    """

    def parse(self, filepath: Path) -> List[Transaction]:
        df = self._load(filepath)
        if df is None or df.empty:
            return []

        cols_lower = [c.strip().lower() for c in df.columns]
        col_map = dict(zip(cols_lower, df.columns))   # lowercase -> original

        date_col = _find_col(cols_lower, DATE_COLS)
        desc_col = _find_col(cols_lower, DESC_COLS)

        # Resolve amount columns
        amount_col  = _find_col(cols_lower, AMOUNT_COLS - DEBIT_COLS - CREDIT_COLS)
        debit_col   = _find_col(cols_lower, DEBIT_COLS)
        credit_col  = _find_col(cols_lower, CREDIT_COLS)

        if not date_col or not desc_col:
            print(f"    [WARN] Cannot detect date/description columns in {filepath.name}")
            print(f"    Columns found: {list(df.columns)}")
            return []

        transactions = []
        source = self._guess_source(filepath.name)

        for _, row in df.iterrows():
            try:
                tx_date = self._parse_date(row[col_map[date_col]])
                if tx_date is None:
                    continue
                description = str(row[col_map[desc_col]]).strip()
                amount = self._resolve_amount(row, col_map, amount_col, debit_col, credit_col)
                if amount is None:
                    continue

                transactions.append(Transaction(
                    date=tx_date,
                    description=description,
                    amount=amount,
                    source=source,
                ))
            except Exception:
                continue

        return transactions

    # ------------------------------------------------------------------ helpers

    def _load(self, filepath: Path) -> Optional[pd.DataFrame]:
        encodings = ["utf-8", "utf-8-sig", "latin-1", "cp1252"]
        for enc in encodings:
            try:
                df = pd.read_csv(filepath, encoding=enc, skip_blank_lines=True, on_bad_lines="skip")
                df.columns = [str(c).strip() for c in df.columns]
                return df
            except Exception:
                continue
        return None

    def _parse_date(self, value) -> Optional[date]:
        if pd.isna(value):
            return None
        try:
            return dateparser.parse(str(value)).date()
        except Exception:
            return None

    def _resolve_amount(self, row, col_map, amount_col, debit_col, credit_col) -> Optional[float]:
        try:
            if amount_col and col_map.get(amount_col):
                raw = str(row[col_map[amount_col]]).replace(",", "").replace("$", "").strip()
                if raw in ("", "nan"):
                    return None
                return float(raw)

            # Separate debit / credit columns
            debit = 0.0
            credit = 0.0
            if debit_col and col_map.get(debit_col):
                raw = str(row[col_map[debit_col]]).replace(",", "").replace("$", "").strip()
                if raw not in ("", "nan"):
                    debit = abs(float(raw))
            if credit_col and col_map.get(credit_col):
                raw = str(row[col_map[credit_col]]).replace(",", "").replace("$", "").strip()
                if raw not in ("", "nan"):
                    credit = abs(float(raw))
            # Debit = money out (negative), credit = money in (positive)
            if debit > 0:
                return -debit
            if credit > 0:
                return credit
        except Exception:
            pass
        return None

    def _guess_source(self, filename: str) -> str:
        name = filename.lower()
        if "chase" in name:
            return "chase"
        if "bofa" in name or "bank_of_america" in name:
            return "bofa"
        if "wells" in name:
            return "wells_fargo"
        if "citi" in name:
            return "citi"
        if "amex" in name or "american_express" in name:
            return "amex"
        if "discover" in name:
            return "discover"
        if "capital_one" in name or "capitalone" in name:
            return "capital_one"
        return "bank"
