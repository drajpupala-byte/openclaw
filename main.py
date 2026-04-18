#!/usr/bin/env python3
"""
OpenClaw — Business Statement Tax Analyzer
Parses bank, Amazon, and Costco statements and exports a formatted
tax deduction Excel workbook organized by month and year.

Usage:
  python main.py --year 2025
  python main.py --year 2025 --input ./data/statements/ --business "Acme LLC"
  python main.py --help
"""

import sys
import argparse
from pathlib import Path
from datetime import datetime

from colorama import init as colorama_init, Fore, Style

from parsers.csv_parser import GenericCSVParser
from parsers.amazon_parser import AmazonParser
from parsers.costco_parser import CostcoParser
from parsers.pdf_parser import PDFParser
from core.tax_analyzer import TaxAnalyzer
from exporters.excel_exporter import ExcelExporter

colorama_init(autoreset=True)

BANNER = f"""
{Fore.CYAN}
  ___                  ___  _
 / _ \ _ __  ___ _ _ / __|| | __ _ _ __ __
| (_) | '_ \/ -_) ' \ (__| |/ _` | |  V  |
 \___/| .__/\___|_||_\___|_|\__,_|_|_|_|_|
      |_|     Business Tax Analyzer
{Style.RESET_ALL}"""


def get_parser(filepath: Path):
    name = filepath.name.lower()
    if "amazon" in name:
        return AmazonParser()
    if "costco" in name:
        return CostcoParser()
    if filepath.suffix.lower() == ".pdf":
        return PDFParser()
    return GenericCSVParser()


def print_step(msg: str):
    print(f"{Fore.CYAN}→{Style.RESET_ALL} {msg}")

def print_ok(msg: str):
    print(f"{Fore.GREEN}✓{Style.RESET_ALL} {msg}")

def print_warn(msg: str):
    print(f"{Fore.YELLOW}⚠{Style.RESET_ALL} {msg}")

def print_err(msg: str):
    print(f"{Fore.RED}✗{Style.RESET_ALL} {msg}")


def main():
    print(BANNER)

    ap = argparse.ArgumentParser(
        prog="openclaw",
        description="OpenClaw — Business Statement Tax Analyzer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
SUPPORTED FILE FORMATS
  *.csv   Bank/credit-card statements (most banks support CSV export)
  *.pdf   Bank statement PDFs (text-based, not scanned images)

FILENAME CONVENTIONS (auto-detect parser)
  amazon_*.csv   → Amazon Order History parser
  costco_*.csv   → Costco Purchase History parser
  *.csv          → Generic bank/credit-card parser

HOW TO EXPORT YOUR STATEMENTS
  Amazon  : amazon.com → Returns & Orders → Order History Reports → Download CSV
  Costco  : costco.com → Orders & Returns → Export → Download CSV
  Bank    : Your bank's website → Statements → Export/Download → CSV

EXAMPLES
  python main.py --year 2025
  python main.py --year 2025 --input ./statements --business "Acme LLC"
  python main.py --year 2025 --tax-rate 0.24
        """,
    )
    ap.add_argument("--year",     "-y", type=int,   default=datetime.now().year,
                    help="Tax year to analyze (default: current year)")
    ap.add_argument("--input",    "-i", type=str,   default="./data/statements",
                    help="Folder containing statement files")
    ap.add_argument("--output",   "-o", type=str,   default="./data/reports",
                    help="Folder for the Excel report")
    ap.add_argument("--business", "-b", type=str,   default="My Business",
                    help="Business name shown in the report")
    ap.add_argument("--tax-rate", "-t", type=float, default=None,
                    help="Override federal tax rate (e.g. 0.24 for 24%%)")

    args = ap.parse_args()

    input_dir  = Path(args.input)
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"  Business : {Fore.WHITE}{args.business}{Style.RESET_ALL}")
    print(f"  Tax Year : {Fore.WHITE}{args.year}{Style.RESET_ALL}")
    print(f"  Input    : {Fore.WHITE}{input_dir}{Style.RESET_ALL}")
    print(f"  Output   : {Fore.WHITE}{output_dir}{Style.RESET_ALL}")
    print()

    # ── Discover files ─────────────────────────────────────────────────────────
    if not input_dir.exists():
        input_dir.mkdir(parents=True, exist_ok=True)
        print_warn(f"Created {input_dir}/ — add your statement files there, then re-run.")
        print()
        print("  Quick-start:")
        print("    Amazon  → rename download as  amazon_2025.csv")
        print("    Costco  → rename download as  costco_2025.csv")
        print("    Bank    → rename download as  chase_2025.csv")
        return 0

    files = sorted(
        [p for pat in ("*.csv", "*.CSV", "*.pdf", "*.PDF") for p in input_dir.glob(pat)]
    )

    if not files:
        print_warn(f"No CSV or PDF files found in {input_dir}/")
        print("  See --help for instructions on exporting your statements.")
        return 1

    print_step(f"Found {len(files)} file(s) in {input_dir}/")

    # ── Parse files ────────────────────────────────────────────────────────────
    analyzer     = TaxAnalyzer()
    all_txns     = []
    amazon_count = costco_count = 0

    for filepath in files:
        parser = get_parser(filepath)
        label  = parser.__class__.__name__.replace("Parser", "")
        print_step(f"Parsing [{label:10s}] {filepath.name}")
        try:
            txns = parser.parse(filepath)
            year_txns = [t for t in txns if t.year == args.year]
            categorized = analyzer.categorize_transactions(year_txns)
            all_txns.extend(categorized)

            amazon_count += sum(1 for t in categorized if t.source == "amazon")
            costco_count += sum(1 for t in categorized if t.source == "costco")

            print_ok(f"  {len(year_txns):4d} transactions for {args.year}")
        except Exception as exc:
            print_err(f"  Failed: {exc}")

    if not all_txns:
        print_warn(f"No transactions found for {args.year}. Check file dates or --year flag.")
        return 1

    # ── Build report ───────────────────────────────────────────────────────────
    safe_name = args.business.replace(" ", "_").replace("/", "-")
    out_file  = output_dir / f"TaxReport_{safe_name}_{args.year}.xlsx"

    print()
    print_step(f"Building Excel report → {out_file.name}")

    ExcelExporter().export(
        transactions=all_txns,
        year=args.year,
        business_name=args.business,
        output_path=out_file,
        tax_rate_override=args.tax_rate,
    )

    # ── Summary ────────────────────────────────────────────────────────────────
    expenses    = [t for t in all_txns if t.is_expense]
    total_exp   = sum(abs(t.amount)        for t in expenses)
    total_ded   = sum(t.deductible_amount  for t in expenses)
    amazon_amt  = sum(abs(t.amount) for t in expenses if t.source == "amazon")
    costco_amt  = sum(abs(t.amount) for t in expenses if t.source == "costco")
    tax_rate    = args.tax_rate or 0.24
    est_savings = total_ded * tax_rate

    print()
    print(f"{Fore.CYAN}{'─'*52}{Style.RESET_ALL}")
    print(f"  {Fore.WHITE}ANNUAL SUMMARY{Style.RESET_ALL}")
    print(f"{'─'*52}")
    print(f"  Total Transactions  : {len(expenses):>8,}")
    print(f"  Total Expenses      : {Fore.RED}${total_exp:>12,.2f}{Style.RESET_ALL}")
    print(f"  Total Deductible    : {Fore.GREEN}${total_ded:>12,.2f}{Style.RESET_ALL}")
    print(f"  Est. Tax Savings    : {Fore.YELLOW}${est_savings:>12,.2f}{Style.RESET_ALL}  (at {int(tax_rate*100)}%)")
    if amazon_amt:
        print(f"  Amazon Purchases    : {Fore.YELLOW}${amazon_amt:>12,.2f}{Style.RESET_ALL}  ({amazon_count} orders)")
    if costco_amt:
        print(f"  Costco Purchases    : {Fore.CYAN}${costco_amt:>12,.2f}{Style.RESET_ALL}  ({costco_count} transactions)")
    print(f"{'─'*52}")
    print()
    print_ok(f"Report saved: {out_file}")
    print()
    print(f"  {Fore.WHITE}Sheets included:{Style.RESET_ALL}")
    print("    Dashboard · All Transactions · Jan–Dec (monthly)")
    print("    Tax Deductions · Amazon · Costco")
    print()
    print(f"  {Fore.YELLOW}NOTE:{Style.RESET_ALL} Consult a licensed CPA for official tax advice.")
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
