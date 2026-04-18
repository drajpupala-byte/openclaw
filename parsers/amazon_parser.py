"""
Amazon Order History parser.

How to export:
  1. Go to amazon.com  > Returns & Orders > order history reports
     URL: https://www.amazon.com/gp/b2b/reports
  2. Select report type "Items" or "Orders", choose year, download CSV.

The "Items" report has columns like:
  Order Date, Order ID, Title, Category, ASIN/ISBN, Quantity, Payment Amount, ...

The "Orders" report has columns like:
  Order Date, Order ID, Payment Method, Billing Address, Subtotal, Shipping Charge,
  Tax Before Promotions & Credits, Tax Charged, Promotions, Total Charged, ...
"""

from pathlib import Path
from typing import List, Optional
from datetime import date

import pandas as pd
from dateutil import parser as dateparser

from core.transaction import Transaction
from parsers.base import BaseParser


class AmazonParser(BaseParser):

    def parse(self, filepath: Path) -> List[Transaction]:
        df = self._load(filepath)
        if df is None or df.empty:
            return []

        cols = {c.strip().lower(): c for c in df.columns}

        # Detect report type
        if "title" in cols:
            return self._parse_items_report(df, cols)
        elif "total charged" in cols:
            return self._parse_orders_report(df, cols)
        else:
            return self._parse_generic(df, cols)

    # ------------------------------------------------------------------ parsers

    def _parse_items_report(self, df: pd.DataFrame, cols: dict) -> List[Transaction]:
        transactions = []
        for _, row in df.iterrows():
            try:
                tx_date = self._parse_date(row.get(cols.get("order date", ""), ""))
                if tx_date is None:
                    continue

                title    = str(row.get(cols.get("title", ""), "")).strip()
                category = str(row.get(cols.get("category", ""), "")).strip()
                qty_raw  = str(row.get(cols.get("quantity", ""), "1")).strip()
                qty      = int(float(qty_raw)) if qty_raw not in ("", "nan") else 1

                amount_col = cols.get("payment amount") or cols.get("item total") or cols.get("item subtotal")
                amount = self._parse_amount(row.get(amount_col, "")) if amount_col else None
                if amount is None:
                    continue

                order_id = str(row.get(cols.get("order id", ""), "")).strip()
                desc = f"{title} (x{qty})" if qty > 1 else title
                if category and category != "nan":
                    desc = f"{desc} [{category}]"

                transactions.append(Transaction(
                    date=tx_date,
                    description=desc,
                    amount=-abs(amount),   # expenses are negative
                    source="amazon",
                    category="Amazon Business",
                    deduction_rate=1.0,
                    order_id=order_id,
                ))
            except Exception:
                continue
        return transactions

    def _parse_orders_report(self, df: pd.DataFrame, cols: dict) -> List[Transaction]:
        transactions = []
        for _, row in df.iterrows():
            try:
                tx_date = self._parse_date(row.get(cols.get("order date", ""), ""))
                if tx_date is None:
                    continue

                amount_col = cols.get("total charged") or cols.get("subtotal")
                amount = self._parse_amount(row.get(amount_col, "")) if amount_col else None
                if amount is None:
                    continue

                order_id = str(row.get(cols.get("order id", ""), "")).strip()
                desc = f"Amazon Order {order_id}" if order_id else "Amazon Order"

                transactions.append(Transaction(
                    date=tx_date,
                    description=desc,
                    amount=-abs(amount),
                    source="amazon",
                    category="Amazon Business",
                    deduction_rate=1.0,
                    order_id=order_id,
                ))
            except Exception:
                continue
        return transactions

    def _parse_generic(self, df: pd.DataFrame, cols: dict) -> List[Transaction]:
        """Fallback for unrecognized Amazon CSV layouts."""
        date_candidates = ["order date", "date", "purchase date"]
        amt_candidates  = ["total charged", "total", "amount", "order total", "grand total", "payment amount"]
        desc_candidates = ["title", "description", "item", "product name"]

        date_col = next((cols[c] for c in date_candidates if c in cols), None)
        amt_col  = next((cols[c] for c in amt_candidates  if c in cols), None)
        desc_col = next((cols[c] for c in desc_candidates if c in cols), None)

        if not date_col or not amt_col:
            print(f"    [WARN] Unrecognized Amazon CSV format. Columns: {list(df.columns)}")
            return []

        transactions = []
        for _, row in df.iterrows():
            try:
                tx_date = self._parse_date(row.get(date_col, ""))
                if tx_date is None:
                    continue
                amount = self._parse_amount(row.get(amt_col, ""))
                if amount is None:
                    continue
                desc = str(row.get(desc_col, "Amazon Purchase")).strip() if desc_col else "Amazon Purchase"
                transactions.append(Transaction(
                    date=tx_date,
                    description=desc,
                    amount=-abs(amount),
                    source="amazon",
                    category="Amazon Business",
                    deduction_rate=1.0,
                ))
            except Exception:
                continue
        return transactions

    # ------------------------------------------------------------------ helpers

    def _load(self, filepath: Path) -> Optional[pd.DataFrame]:
        for enc in ["utf-8", "utf-8-sig", "latin-1", "cp1252"]:
            try:
                return pd.read_csv(filepath, encoding=enc, skip_blank_lines=True, on_bad_lines="skip")
            except Exception:
                continue
        return None

    def _parse_date(self, value) -> Optional[date]:
        if pd.isna(value) if hasattr(pd, "isna") else value != value:
            return None
        try:
            return dateparser.parse(str(value)).date()
        except Exception:
            return None

    def _parse_amount(self, value) -> Optional[float]:
        try:
            raw = str(value).replace(",", "").replace("$", "").strip()
            if raw in ("", "nan"):
                return None
            return float(raw)
        except Exception:
            return None
