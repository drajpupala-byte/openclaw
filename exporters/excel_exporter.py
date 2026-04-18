"""Excel report generator for tax statement analysis."""

from pathlib import Path
from typing import List, Optional, Dict
from datetime import date
from collections import defaultdict

from openpyxl import Workbook
from openpyxl.styles import (
    Font, PatternFill, Alignment, Border, Side, numbers
)
from openpyxl.utils import get_column_letter
from openpyxl.chart import BarChart, PieChart, Reference
from openpyxl.chart.series import DataPoint

from core.transaction import Transaction
from core.tax_analyzer import TaxAnalyzer

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

CATEGORY_COLORS = {
    "Office Supplies":          "4472C4",
    "Business Meals":           "ED7D31",
    "Technology & Software":    "A9D18E",
    "Business Subscriptions":   "FFD966",
    "Travel & Transportation":  "9DC3E6",
    "Professional Services":    "C9B1D9",
    "Advertising & Marketing":  "F4B942",
    "Utilities & Communications": "70AD47",
    "Amazon Business":          "FF9900",
    "Costco Business":          "005DAA",
    "Insurance":                "FF7575",
    "Rent & Facilities":        "B4A7D6",
    "Shipping & Postage":       "D6ADAD",
    "Banking & Finance":        "ADB9CA",
    "Uncategorized":            "D9D9D9",
}

# ── Style helpers ──────────────────────────────────────────────────────────────

def _fill(hex_color: str) -> PatternFill:
    return PatternFill("solid", fgColor=hex_color)

def _font(bold=False, size=11, color="000000", italic=False) -> Font:
    return Font(bold=bold, size=size, color=color, italic=italic)

def _border(style="thin") -> Border:
    side = Side(style=style)
    return Border(left=side, right=side, top=side, bottom=side)

def _center() -> Alignment:
    return Alignment(horizontal="center", vertical="center", wrap_text=True)

def _left() -> Alignment:
    return Alignment(horizontal="left", vertical="center")

def _money(ws, cell):
    ws[cell].number_format = '"$"#,##0.00'

def _pct(ws, cell):
    ws[cell].number_format = "0%"

HEADER_FILL  = _fill("1F3864")
HEADER_FONT  = _font(bold=True, size=11, color="FFFFFF")
SUBHDR_FILL  = _fill("2F5496")
SUBHDR_FONT  = _font(bold=True, size=10, color="FFFFFF")
TOTAL_FILL   = _fill("D6E4F0")
TOTAL_FONT   = _font(bold=True, size=11)
ALT_FILL     = _fill("F2F7FB")
TITLE_FONT   = _font(bold=True, size=16, color="1F3864")
SECTION_FONT = _font(bold=True, size=12, color="2F5496")

THIN_BORDER  = _border("thin")
MED_BORDER   = _border("medium")


def _auto_width(ws, min_width=10, max_width=60):
    for col_cells in ws.columns:
        length = max(
            len(str(c.value or "")) for c in col_cells
        )
        col_letter = get_column_letter(col_cells[0].column)
        ws.column_dimensions[col_letter].width = min(max(length + 2, min_width), max_width)


def _style_header_row(ws, row: int, cols: int, fill=None, font=None):
    fill = fill or HEADER_FILL
    font = font or HEADER_FONT
    for c in range(1, cols + 1):
        cell = ws.cell(row=row, column=c)
        cell.fill = fill
        cell.font = font
        cell.alignment = _center()
        cell.border = THIN_BORDER


# ── Main Exporter ──────────────────────────────────────────────────────────────

class ExcelExporter:

    def export(
        self,
        transactions: List[Transaction],
        year: int,
        business_name: str,
        output_path: Path,
        tax_rate_override: Optional[float] = None,
    ):
        self.wb = Workbook()
        self.wb.remove(self.wb.active)   # remove default sheet

        self.year = year
        self.business = business_name
        self.transactions = transactions
        self.analyzer = TaxAnalyzer()

        # Pre-compute summaries
        expenses    = [t for t in transactions if t.is_expense]
        annual_sum  = self.analyzer.annual_summary(transactions)
        monthly_sum = self.analyzer.monthly_summary(transactions)
        categories  = sorted(annual_sum.keys())

        self._build_dashboard(annual_sum, monthly_sum, categories, tax_rate_override)
        self._build_all_transactions(expenses)
        for m in range(1, 13):
            month_txns = [t for t in expenses if t.month == m]
            if month_txns:
                self._build_month_sheet(m, month_txns)
        self._build_deductions(expenses, annual_sum, tax_rate_override)
        self._build_source_sheet("Amazon", "amazon", expenses)
        self._build_source_sheet("Costco", "costco", expenses)

        self.wb.save(output_path)

    # ── Dashboard ──────────────────────────────────────────────────────────────

    def _build_dashboard(self, annual_sum, monthly_sum, categories, tax_rate_override):
        ws = self.wb.create_sheet("Dashboard")
        ws.sheet_view.showGridLines = False

        # Title banner
        ws.merge_cells("A1:P2")
        ws["A1"] = f"{self.business.upper()} — BUSINESS TAX REPORT {self.year}"
        ws["A1"].font = TITLE_FONT
        ws["A1"].fill = _fill("EBF3FB")
        ws["A1"].alignment = _center()

        # Summary KPIs
        total_exp   = sum(v["total"]      for v in annual_sum.values())
        total_ded   = sum(v["deductible"] for v in annual_sum.values())
        tax_rate    = tax_rate_override or 0.24
        est_savings = total_ded * tax_rate

        ws.merge_cells("A4:D4")
        ws["A4"] = "ANNUAL SUMMARY"
        ws["A4"].font = SECTION_FONT

        kpis = [
            ("Total Business Expenses",   total_exp,   "C17375"),
            ("Total Deductible Amount",    total_ded,   "70AD47"),
            (f"Est. Tax Savings ({int(tax_rate*100)}%)", est_savings, "4472C4"),
        ]
        for i, (label, value, color) in enumerate(kpis, start=5):
            col_start = i * 0           # offset each KPI box horizontally
            ws.merge_cells(f"A{i}:B{i}")
            ws[f"A{i}"] = label
            ws[f"A{i}"].font = _font(bold=True, size=11)
            ws[f"A{i}"].fill = _fill("F2F7FB")
            ws[f"A{i}"].alignment = _left()
            ws[f"C{i}"] = value
            ws[f"C{i}"].number_format = '"$"#,##0.00'
            ws[f"C{i}"].font = _font(bold=True, size=12, color=color)
            ws[f"C{i}"].alignment = _center()

        # Monthly category pivot table
        start_row = 10
        ws.cell(start_row, 1, "CATEGORY BREAKDOWN BY MONTH").font = SECTION_FONT
        ws.merge_cells(f"A{start_row}:P{start_row}")

        hdr_row = start_row + 1
        ws.cell(hdr_row, 1, "Category")
        for m in range(1, 13):
            ws.cell(hdr_row, m + 1, MONTHS[m - 1])
        ws.cell(hdr_row, 14, "TOTAL")
        ws.cell(hdr_row, 15, "DEDUCTIBLE")
        ws.cell(hdr_row, 16, "EST. SAVINGS")
        _style_header_row(ws, hdr_row, 16)

        row = hdr_row + 1
        for i, cat in enumerate(categories):
            color = CATEGORY_COLORS.get(cat, "D9D9D9")
            fill  = _fill(color) if i % 2 == 0 else ALT_FILL

            ws.cell(row, 1, cat).font = _font(bold=True, size=10)
            ws.cell(row, 1).fill = fill
            ws.cell(row, 1).border = THIN_BORDER

            row_total = 0.0
            row_ded   = 0.0
            for m in range(1, 13):
                val = monthly_sum.get(m, {}).get(cat, {}).get("total", 0.0)
                ded = monthly_sum.get(m, {}).get(cat, {}).get("deductible", 0.0)
                cell = ws.cell(row, m + 1, val if val else "")
                cell.number_format = '"$"#,##0.00'
                cell.fill = fill
                cell.border = THIN_BORDER
                cell.alignment = _center()
                row_total += val
                row_ded   += ded

            for c, val in [(14, row_total), (15, row_ded), (16, row_ded * tax_rate)]:
                cell = ws.cell(row, c, val)
                cell.number_format = '"$"#,##0.00'
                cell.font = _font(bold=True, size=10)
                cell.fill = TOTAL_FILL
                cell.border = THIN_BORDER
                cell.alignment = _center()

            row += 1

        # Totals row
        ws.cell(row, 1, "TOTAL").font = TOTAL_FONT
        ws.cell(row, 1).fill = HEADER_FILL
        ws.cell(row, 1).font = _font(bold=True, color="FFFFFF")
        ws.cell(row, 1).border = THIN_BORDER

        for m in range(1, 13):
            month_total = sum(
                monthly_sum.get(m, {}).get(cat, {}).get("total", 0.0)
                for cat in categories
            )
            cell = ws.cell(row, m + 1, month_total if month_total else "")
            cell.number_format = '"$"#,##0.00'
            cell.font = _font(bold=True, color="FFFFFF")
            cell.fill = HEADER_FILL
            cell.border = THIN_BORDER
            cell.alignment = _center()

        for c, val in [(14, total_exp), (15, total_ded), (16, est_savings)]:
            cell = ws.cell(row, c, val)
            cell.number_format = '"$"#,##0.00'
            cell.font = _font(bold=True, color="FFFFFF")
            cell.fill = HEADER_FILL
            cell.border = THIN_BORDER
            cell.alignment = _center()

        _auto_width(ws)
        ws.column_dimensions["A"].width = 28
        ws.freeze_panes = f"B{hdr_row + 1}"

    # ── All Transactions ───────────────────────────────────────────────────────

    def _build_all_transactions(self, expenses: List[Transaction]):
        ws = self.wb.create_sheet("All Transactions")
        ws.sheet_view.showGridLines = False

        headers = ["Date", "Description", "Amount", "Category", "Deductible Amt",
                   "Deduction %", "Source", "Order ID", "Notes"]
        for c, h in enumerate(headers, 1):
            cell = ws.cell(1, c, h)
            cell.fill = HEADER_FILL
            cell.font = HEADER_FONT
            cell.alignment = _center()
            cell.border = THIN_BORDER

        for i, t in enumerate(sorted(expenses, key=lambda x: x.date), 2):
            fill = ALT_FILL if i % 2 == 0 else _fill("FFFFFF")
            color = CATEGORY_COLORS.get(t.category, "D9D9D9")

            row_data = [
                t.date, t.description, abs(t.amount), t.category,
                t.deductible_amount, t.deduction_rate, t.source, t.order_id, t.notes
            ]
            for c, val in enumerate(row_data, 1):
                cell = ws.cell(i, c, val)
                cell.border = THIN_BORDER
                cell.alignment = _left()
                if c == 1:
                    cell.number_format = "MM/DD/YYYY"
                    cell.alignment = _center()
                elif c in (3, 5):
                    cell.number_format = '"$"#,##0.00'
                    cell.alignment = _center()
                elif c == 6:
                    cell.number_format = "0%"
                    cell.alignment = _center()
                elif c == 4:
                    cell.fill = _fill(color)
                    cell.font = _font(bold=False, size=10)
                    continue
                cell.fill = fill

        ws.auto_filter.ref = f"A1:{get_column_letter(len(headers))}1"
        ws.freeze_panes = "A2"
        _auto_width(ws)
        ws.column_dimensions["B"].width = 45

    # ── Monthly Sheet ──────────────────────────────────────────────────────────

    def _build_month_sheet(self, month: int, transactions: List[Transaction]):
        ws = self.wb.create_sheet(MONTHS[month - 1])
        ws.sheet_view.showGridLines = False

        # Month header
        ws.merge_cells("A1:G1")
        ws["A1"] = f"{MONTHS[month-1].upper()} {self.year} — {self.business}"
        ws["A1"].font = TITLE_FONT
        ws["A1"].fill = _fill("EBF3FB")
        ws["A1"].alignment = _center()

        headers = ["Date", "Description", "Amount", "Category", "Deductible", "Ded. %", "Source"]
        for c, h in enumerate(headers, 1):
            cell = ws.cell(2, c, h)
            cell.fill = HEADER_FILL
            cell.font = HEADER_FONT
            cell.alignment = _center()
            cell.border = THIN_BORDER

        sorted_txns = sorted(transactions, key=lambda x: x.date)
        for i, t in enumerate(sorted_txns, 3):
            fill = ALT_FILL if i % 2 == 0 else _fill("FFFFFF")
            color = CATEGORY_COLORS.get(t.category, "D9D9D9")
            row_data = [t.date, t.description, abs(t.amount), t.category,
                        t.deductible_amount, t.deduction_rate, t.source]
            for c, val in enumerate(row_data, 1):
                cell = ws.cell(i, c, val)
                cell.border = THIN_BORDER
                if c == 1:
                    cell.number_format = "MM/DD/YYYY"
                    cell.alignment = _center()
                    cell.fill = fill
                elif c in (3, 5):
                    cell.number_format = '"$"#,##0.00'
                    cell.alignment = _center()
                    cell.fill = fill
                elif c == 6:
                    cell.number_format = "0%"
                    cell.alignment = _center()
                    cell.fill = fill
                elif c == 4:
                    cell.fill = _fill(color)
                    cell.font = _font(size=10)
                    cell.alignment = _left()
                else:
                    cell.fill = fill
                    cell.alignment = _left()

        # Totals row
        total_row = len(sorted_txns) + 3
        ws.cell(total_row, 1, "MONTHLY TOTAL").font = TOTAL_FONT
        ws.cell(total_row, 1).fill = TOTAL_FILL
        ws.cell(total_row, 1).border = THIN_BORDER

        total_amt = sum(abs(t.amount) for t in transactions)
        total_ded = sum(t.deductible_amount for t in transactions)
        for c, val in [(3, total_amt), (5, total_ded)]:
            cell = ws.cell(total_row, c, val)
            cell.number_format = '"$"#,##0.00'
            cell.font = TOTAL_FONT
            cell.fill = TOTAL_FILL
            cell.border = THIN_BORDER
            cell.alignment = _center()

        ws.auto_filter.ref = f"A2:{get_column_letter(len(headers))}2"
        ws.freeze_panes = "A3"
        _auto_width(ws)
        ws.column_dimensions["B"].width = 45

    # ── Tax Deductions Summary ─────────────────────────────────────────────────

    def _build_deductions(self, expenses, annual_sum, tax_rate_override):
        ws = self.wb.create_sheet("Tax Deductions")
        ws.sheet_view.showGridLines = False

        ws.merge_cells("A1:F1")
        ws["A1"] = f"TAX DEDUCTIONS SUMMARY — {self.year}"
        ws["A1"].font = TITLE_FONT
        ws["A1"].fill = _fill("EBF3FB")
        ws["A1"].alignment = _center()

        ws.merge_cells("A2:F2")
        ws["A2"] = "⚠ DISCLAIMER: This report is for reference only. Consult a licensed CPA or tax professional for official tax advice."
        ws["A2"].font = _font(italic=True, size=9, color="7F7F7F")
        ws["A2"].alignment = _center()

        # Category deduction table
        headers = ["Category", "# Transactions", "Total Spent", "Deduction Rate",
                   "Deductible Amount", "Notes"]
        for c, h in enumerate(headers, 1):
            cell = ws.cell(4, c, h)
            cell.fill = HEADER_FILL
            cell.font = HEADER_FONT
            cell.alignment = _center()
            cell.border = THIN_BORDER

        row = 5
        for i, (cat, data) in enumerate(sorted(annual_sum.items())):
            if data["deductible"] == 0:
                continue
            color = CATEGORY_COLORS.get(cat, "D9D9D9")
            fill  = _fill(color)
            note  = "50% deductible (IRS)" if "Meals" in cat else ""

            row_data = [cat, data["count"], data["total"],
                        None, data["deductible"], note]
            for c, val in enumerate(row_data, 1):
                cell = ws.cell(row, c, val)
                cell.border = THIN_BORDER
                if c == 1:
                    cell.fill = fill
                    cell.font = _font(bold=True, size=10)
                    cell.alignment = _left()
                elif c == 2:
                    cell.alignment = _center()
                elif c == 3:
                    cell.number_format = '"$"#,##0.00'
                    cell.alignment = _center()
                elif c == 4:
                    # Deduction rate formula derived from data
                    rate = data["deductible"] / data["total"] if data["total"] else 0
                    cell.value = rate
                    cell.number_format = "0%"
                    cell.alignment = _center()
                elif c == 5:
                    cell.number_format = '"$"#,##0.00'
                    cell.font = _font(bold=True, size=10, color="1F7A1F")
                    cell.alignment = _center()
                else:
                    cell.font = _font(italic=True, size=9, color="7F7F7F")
                    cell.alignment = _left()
            row += 1

        # Grand total
        total_ded = sum(d["deductible"] for d in annual_sum.values())
        ws.cell(row, 1, "GRAND TOTAL").font = TOTAL_FONT
        ws.cell(row, 1).fill = HEADER_FILL
        ws.cell(row, 1).font = _font(bold=True, color="FFFFFF")
        ws.cell(row, 1).border = THIN_BORDER
        cell = ws.cell(row, 5, total_ded)
        cell.number_format = '"$"#,##0.00'
        cell.font = _font(bold=True, size=12, color="FFFFFF")
        cell.fill = HEADER_FILL
        cell.border = THIN_BORDER
        cell.alignment = _center()
        row += 2

        # Tax savings at different brackets
        ws.cell(row, 1, "ESTIMATED TAX SAVINGS BY BRACKET").font = SECTION_FONT
        ws.merge_cells(f"A{row}:F{row}")
        row += 1

        brackets = [0.10, 0.12, 0.22, 0.24, 0.32, 0.35, 0.37]
        hdrs = ["Tax Bracket", "Federal Savings", "Self-Employment (15.3%)"]
        for c, h in enumerate(hdrs, 1):
            cell = ws.cell(row, c, h)
            cell.fill = SUBHDR_FILL
            cell.font = SUBHDR_FONT
            cell.alignment = _center()
            cell.border = THIN_BORDER
        row += 1

        override = tax_rate_override
        for rate in brackets:
            savings  = total_ded * rate
            se_sav   = total_ded * 0.153 * 0.5
            highlight = override and abs(rate - override) < 0.001
            fill = _fill("D6E4F0") if highlight else _fill("FFFFFF")

            ws.cell(row, 1, f"{int(rate*100)}% Bracket").fill = fill
            ws.cell(row, 1).border = THIN_BORDER
            ws.cell(row, 1).alignment = _center()

            cell = ws.cell(row, 2, savings)
            cell.number_format = '"$"#,##0.00'
            cell.fill = _fill("E2F0D9") if highlight else fill
            cell.font = _font(bold=highlight, color="1F7A1F")
            cell.border = THIN_BORDER
            cell.alignment = _center()

            cell = ws.cell(row, 3, se_sav)
            cell.number_format = '"$"#,##0.00'
            cell.fill = fill
            cell.border = THIN_BORDER
            cell.alignment = _center()
            row += 1

        # Deductible transactions list
        row += 1
        ws.cell(row, 1, "ALL DEDUCTIBLE TRANSACTIONS").font = SECTION_FONT
        ws.merge_cells(f"A{row}:F{row}")
        row += 1

        ded_headers = ["Date", "Description", "Amount", "Category", "Deductible Amt", "Source"]
        for c, h in enumerate(ded_headers, 1):
            cell = ws.cell(row, c, h)
            cell.fill = HEADER_FILL
            cell.font = HEADER_FONT
            cell.alignment = _center()
            cell.border = THIN_BORDER
        row += 1

        for i, t in enumerate(sorted([t for t in expenses if t.is_deductible],
                                      key=lambda x: x.date)):
            fill = ALT_FILL if i % 2 == 0 else _fill("FFFFFF")
            color = CATEGORY_COLORS.get(t.category, "D9D9D9")
            for c, val in enumerate([t.date, t.description, abs(t.amount),
                                      t.category, t.deductible_amount, t.source], 1):
                cell = ws.cell(row, c, val)
                cell.border = THIN_BORDER
                if c == 1:
                    cell.number_format = "MM/DD/YYYY"
                    cell.alignment = _center()
                    cell.fill = fill
                elif c in (3, 5):
                    cell.number_format = '"$"#,##0.00'
                    cell.alignment = _center()
                    cell.fill = fill
                elif c == 4:
                    cell.fill = _fill(color)
                    cell.font = _font(size=10)
                else:
                    cell.fill = fill
                    cell.alignment = _left()
            row += 1

        ws.freeze_panes = "A5"
        _auto_width(ws)
        ws.column_dimensions["A"].width = 28
        ws.column_dimensions["B"].width = 45

    # ── Source-Specific Sheet (Amazon / Costco) ────────────────────────────────

    def _build_source_sheet(self, title: str, source_tag: str, expenses: List[Transaction]):
        source_txns = [t for t in expenses if t.source == source_tag]
        if not source_txns:
            return

        ws = self.wb.create_sheet(title)
        ws.sheet_view.showGridLines = False

        color = "FF9900" if source_tag == "amazon" else "005DAA"
        total_amt = sum(abs(t.amount) for t in source_txns)
        total_ded = sum(t.deductible_amount for t in source_txns)

        ws.merge_cells("A1:F1")
        ws["A1"] = f"{title.upper()} BUSINESS PURCHASES — {self.year}"
        ws["A1"].font = _font(bold=True, size=16, color=color)
        ws["A1"].fill = _fill("EBF3FB")
        ws["A1"].alignment = _center()

        # KPI summary
        ws["A3"] = "Total Purchases:"
        ws["A3"].font = _font(bold=True, size=12)
        ws["B3"] = total_amt
        ws["B3"].number_format = '"$"#,##0.00'
        ws["B3"].font = _font(bold=True, size=12, color="C00000")

        ws["A4"] = "Total Deductible:"
        ws["A4"].font = _font(bold=True, size=12)
        ws["B4"] = total_ded
        ws["B4"].number_format = '"$"#,##0.00'
        ws["B4"].font = _font(bold=True, size=12, color="1F7A1F")

        ws["A5"] = "# Transactions:"
        ws["A5"].font = _font(bold=True)
        ws["B5"] = len(source_txns)
        ws["B5"].alignment = _center()

        # Monthly breakdown
        ws["A7"] = "MONTHLY TOTALS"
        ws["A7"].font = SECTION_FONT
        monthly_headers = ["Month", "Total Spent", "# Orders"]
        for c, h in enumerate(monthly_headers, 1):
            cell = ws.cell(8, c, h)
            cell.fill = _fill(color)
            cell.font = _font(bold=True, color="FFFFFF")
            cell.alignment = _center()
            cell.border = THIN_BORDER

        monthly = defaultdict(lambda: {"total": 0.0, "count": 0})
        for t in source_txns:
            monthly[t.month]["total"] += abs(t.amount)
            monthly[t.month]["count"] += 1

        for row, m in enumerate(range(1, 13), 9):
            data = monthly.get(m, {"total": 0.0, "count": 0})
            fill = ALT_FILL if m % 2 == 0 else _fill("FFFFFF")
            ws.cell(row, 1, MONTHS[m - 1]).fill = fill
            ws.cell(row, 1).border = THIN_BORDER
            ws.cell(row, 1).alignment = _center()

            cell = ws.cell(row, 2, data["total"] if data["total"] else "")
            cell.number_format = '"$"#,##0.00'
            cell.fill = fill
            cell.border = THIN_BORDER
            cell.alignment = _center()

            cell = ws.cell(row, 3, data["count"] if data["count"] else "")
            cell.fill = fill
            cell.border = THIN_BORDER
            cell.alignment = _center()

        # Detailed transactions
        detail_start = 22
        ws.cell(detail_start, 1, "ALL TRANSACTIONS").font = SECTION_FONT
        ws.merge_cells(f"A{detail_start}:F{detail_start}")
        detail_start += 1

        headers = ["Date", "Description", "Amount", "Deductible Amt", "Order ID", "Notes"]
        for c, h in enumerate(headers, 1):
            cell = ws.cell(detail_start, c, h)
            cell.fill = _fill(color)
            cell.font = _font(bold=True, color="FFFFFF")
            cell.alignment = _center()
            cell.border = THIN_BORDER
        detail_start += 1

        for i, t in enumerate(sorted(source_txns, key=lambda x: x.date)):
            fill_row = ALT_FILL if i % 2 == 0 else _fill("FFFFFF")
            for c, val in enumerate([t.date, t.description, abs(t.amount),
                                      t.deductible_amount, t.order_id, t.notes], 1):
                cell = ws.cell(detail_start + i, c, val)
                cell.fill = fill_row
                cell.border = THIN_BORDER
                if c == 1:
                    cell.number_format = "MM/DD/YYYY"
                    cell.alignment = _center()
                elif c in (3, 4):
                    cell.number_format = '"$"#,##0.00'
                    cell.alignment = _center()
                else:
                    cell.alignment = _left()

        ws.auto_filter.ref = f"A{detail_start-1}:{get_column_letter(len(headers))}{detail_start-1}"
        ws.freeze_panes = f"A{detail_start}"
        _auto_width(ws)
        ws.column_dimensions["B"].width = 50
