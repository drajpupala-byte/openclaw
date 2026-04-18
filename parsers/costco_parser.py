"""
Costco Purchase History parser.

How to export from Costco:
  Option A (Website):
    1. Go to costco.com > Orders & Returns
    2. Select year range > click "Export" or "Download CSV"
    3. Save file as costco_YYYY.csv

  Option B (Costco Anywhere Visa by Citi):
    1. Log in at cardbenefits.citi.com or accountonline.citibank.com
    2. Download statement CSV; name it "costco_YYYY.csv"

  Option C (Warehouse receipts):
    - Warehouse purchases appear in costco.com purchase history
      if you're a member and showed your card at checkout.

Typical Costco CSV columns (online orders):
  Order Date, Order Number, Shipping Address, Order Total, Item Description, Item Price, Qty

Typical Costco warehouse history columns:
  Date, Warehouse, Description, Amount
"""

from pathlib import Path
from typing import List, Optional
from datetime import date

import pandas as pd
from dateutil import parser as dateparser

from core.transaction import Transaction
from parsers.base import BaseParser


class CostcoParser(BaseParser):

    def parse(self, filepath: Path) -> List[Transaction]:
        df = self._load(filepath)
        if df is None or df.empty:
            return []

        cols = {c.strip().lower(): c for c in df.columns}

        if "order number" in cols or "item description" in cols:
            return self._parse_online_order(df, cols)
        elif "warehouse" in cols:
            return self._parse_warehouse(df, cols)
        else:
            return self._parse_generic(df, cols)

    # ------------------------------------------------------------------ parsers

    def _parse_online_order(self, df: pd.DataFrame, cols: dict) -> List[Transaction]:
        """Costco.com online order history."""
        transactions = []
        for _, row in df.iterrows():
            try:
                date_col  = cols.get("order date") or cols.get("date")
                tx_date   = self._parse_date(row.get(date_col, "")) if date_col else None
                if tx_date is None:
                    continue

                # Try item-level price first, fall back to order total
                amt_col = cols.get("item price") or cols.get("order total") or cols.get("total")
                amount  = self._parse_amount(row.get(amt_col, "")) if amt_col else None
                if amount is None:
                    continue

                desc_col = cols.get("item description") or cols.get("description") or cols.get("product")
                desc = str(row.get(desc_col, "Costco Purchase")).strip() if desc_col else "Costco Purchase"
                qty_col = cols.get("qty") or cols.get("quantity")
                if qty_col:
                    qty_raw = str(row.get(qty_col, "1")).strip()
                    qty = int(float(qty_raw)) if qty_raw not in ("", "nan") else 1
                    if qty > 1:
                        desc = f"{desc} (x{qty})"

                order_col = cols.get("order number") or cols.get("order id")
                order_id = str(row.get(order_col, "")).strip() if order_col else ""

                transactions.append(Transaction(
                    date=tx_date,
                    description=desc,
                    amount=-abs(amount),
                    source="costco",
                    category="Costco Business",
                    deduction_rate=1.0,
                    order_id=order_id,
                ))
            except Exception:
                continue
        return transactions

    def _parse_warehouse(self, df: pd.DataFrame, cols: dict) -> List[Transaction]:
        """Costco warehouse purchase history."""
        transactions = []
        for _, row in df.iterrows():
            try:
                date_col = cols.get("date") or cols.get("transaction date")
                tx_date  = self._parse_date(row.get(date_col, "")) if date_col else None
                if tx_date is None:
                    continue

                amt_col = cols.get("amount") or cols.get("total") or cols.get("transaction amount")
                amount  = self._parse_amount(row.get(amt_col, "")) if amt_col else None
                if amount is None:
                    continue

                warehouse = str(row.get(cols.get("warehouse", ""), "")).strip()
                desc_col  = cols.get("description") or cols.get("item")
                item_desc = str(row.get(desc_col, "")).strip() if desc_col else ""
                desc = f"Costco {warehouse} - {item_desc}" if warehouse and item_desc else \
                       f"Costco {warehouse}" if warehouse else "Costco Warehouse Purchase"

                transactions.append(Transaction(
                    date=tx_date,
                    description=desc,
                    amount=-abs(amount),
                    source="costco",
                    category="Costco Business",
                    deduction_rate=1.0,
                ))
            except Exception:
                continue
        return transactions

    def _parse_generic(self, df: pd.DataFrame, cols: dict) -> List[Transaction]:
        """Fallback for unrecognized Costco CSV formats."""
        date_candidates = ["date", "order date", "transaction date", "purchase date"]
        amt_candidates  = ["amount", "total", "order total", "item price", "transaction amount"]
        desc_candidates = ["description", "item description", "item", "product", "merchant"]

        date_col = next((cols[c] for c in date_candidates if c in cols), None)
        amt_col  = next((cols[c] for c in amt_candidates  if c in cols), None)
        desc_col = next((cols[c] for c in desc_candidates if c in cols), None)

        if not date_col or not amt_col:
            print(f"    [WARN] Unrecognized Costco CSV format. Columns: {list(df.columns)}")
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
                desc = str(row.get(desc_col, "Costco Purchase")).strip() if desc_col else "Costco Purchase"
                transactions.append(Transaction(
                    date=tx_date,
                    description=desc,
                    amount=-abs(amount),
                    source="costco",
                    category="Costco Business",
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
