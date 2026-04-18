#!/usr/bin/env python3
"""
OpenClaw — Business Statement Tax Analyzer
Parses bank, Amazon, and Costco statements, uses AI to categorize transactions,
exports a formatted Excel workbook, and offers a natural-language tax Q&A chat.

Commands:
  analyze   Parse statements and produce the Excel report  (default)
  chat      Interactive AI tax advisor for your expense data

Usage:
  python main.py --year 2025 --business "Acme LLC"
  python main.py --year 2025 --ai-backend claude          # AI categorization
  python main.py chat --year 2025                         # AI Q&A chat
  python main.py chat --year 2025 --ai-backend local      # 100% on-device
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
 / _ \\ _ __  ___ _ _ / __|| | __ _ _ __ __
| (_) | '_ \\/ -_) ' \\ (__| |/ _` | |  V  |
 \\___/| .__/\\___|_||_\\___|_|\\__,_|_|_|_|_|
      |_|     Business Tax Analyzer
{Style.RESET_ALL}"""


def get_file_parser(filepath: Path):
    name = filepath.name.lower()
    if "amazon" in name:
        return AmazonParser()
    if "costco" in name:
        return CostcoParser()
    if filepath.suffix.lower() == ".pdf":
        return PDFParser()
    return GenericCSVParser()


def print_step(msg: str): print(f"{Fore.CYAN}→{Style.RESET_ALL} {msg}")
def print_ok(msg: str):   print(f"{Fore.GREEN}✓{Style.RESET_ALL} {msg}")
def print_warn(msg: str): print(f"{Fore.YELLOW}⚠{Style.RESET_ALL} {msg}")
def print_err(msg: str):  print(f"{Fore.RED}✗{Style.RESET_ALL} {msg}")


# ── Shared: load & parse transactions ─────────────────────────────────────────

def load_transactions(input_dir: Path, year: int, ai_backend: str,
                      local_model: str, business: str):
    """Parse all statement files, run keyword + optional AI categorization."""
    if not input_dir.exists():
        input_dir.mkdir(parents=True, exist_ok=True)
        print_warn(f"Created {input_dir}/ — add your statement files there, then re-run.")
        print()
        print("  Quick-start:")
        print("    Amazon  → rename download as  amazon_2025.csv")
        print("    Costco  → rename download as  costco_2025.csv")
        print("    Bank    → rename download as  chase_2025.csv")
        return None

    files = sorted(
        [p for pat in ("*.csv", "*.CSV", "*.pdf", "*.PDF") for p in input_dir.glob(pat)]
    )
    if not files:
        print_warn(f"No CSV or PDF files found in {input_dir}/")
        print("  See --help for exporting your statements.")
        return None

    print_step(f"Found {len(files)} file(s) in {input_dir}/")

    analyzer = TaxAnalyzer()
    all_txns = []
    amazon_count = costco_count = 0

    for filepath in files:
        fp = get_file_parser(filepath)
        label = fp.__class__.__name__.replace("Parser", "")
        print_step(f"Parsing [{label:10s}] {filepath.name}")
        try:
            txns       = fp.parse(filepath)
            year_txns  = [t for t in txns if t.year == year]
            categorized = analyzer.categorize_transactions(year_txns)
            all_txns.extend(categorized)
            amazon_count += sum(1 for t in categorized if t.source == "amazon")
            costco_count += sum(1 for t in categorized if t.source == "costco")
            print_ok(f"  {len(year_txns):4d} transactions for {year}")
        except Exception as exc:
            print_err(f"  Failed: {exc}")

    if not all_txns:
        print_warn(f"No transactions found for {year}. Check file dates or --year.")
        return None

    # ── AI enhancement (optional) ──────────────────────────────────────────────
    if ai_backend:
        from core.ai_categorizer import AICategorizer
        print_step(f"Running AI categorizer ({ai_backend.upper()}"
                   + (f" / {local_model}" if ai_backend == "local" else "") + ") …")
        try:
            cat = AICategorizer(backend=ai_backend, local_model=local_model)
            all_txns = cat.enhance(all_txns)
        except Exception as exc:
            print_warn(f"AI categorizer skipped: {exc}")

    return all_txns, amazon_count, costco_count


# ── Command: analyze ──────────────────────────────────────────────────────────

def cmd_analyze(args):
    input_dir  = Path(args.input)
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"  Business   : {Fore.WHITE}{args.business}{Style.RESET_ALL}")
    print(f"  Tax Year   : {Fore.WHITE}{args.year}{Style.RESET_ALL}")
    print(f"  Input      : {Fore.WHITE}{input_dir}{Style.RESET_ALL}")
    print(f"  Output     : {Fore.WHITE}{output_dir}{Style.RESET_ALL}")
    if args.ai_backend:
        label = args.ai_backend.upper()
        if args.ai_backend == "local":
            label += f" ({args.local_model})"
        print(f"  AI Backend : {Fore.MAGENTA}{label}{Style.RESET_ALL}")
    print()

    result = load_transactions(input_dir, args.year, args.ai_backend,
                               args.local_model, args.business)
    if result is None:
        return 1
    all_txns, amazon_count, costco_count = result

    # Excel report
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

    # Summary
    expenses   = [t for t in all_txns if t.is_expense]
    total_exp  = sum(abs(t.amount)       for t in expenses)
    total_ded  = sum(t.deductible_amount for t in expenses)
    amazon_amt = sum(abs(t.amount) for t in expenses if t.source == "amazon")
    costco_amt = sum(abs(t.amount) for t in expenses if t.source == "costco")
    tax_rate   = args.tax_rate or 0.24
    savings    = total_ded * tax_rate

    print()
    print(f"{Fore.CYAN}{'─'*52}{Style.RESET_ALL}")
    print(f"  {Fore.WHITE}ANNUAL SUMMARY{Style.RESET_ALL}")
    print(f"{'─'*52}")
    print(f"  Total Transactions  : {len(expenses):>8,}")
    print(f"  Total Expenses      : {Fore.RED}${total_exp:>12,.2f}{Style.RESET_ALL}")
    print(f"  Total Deductible    : {Fore.GREEN}${total_ded:>12,.2f}{Style.RESET_ALL}")
    print(f"  Est. Tax Savings    : {Fore.YELLOW}${savings:>12,.2f}{Style.RESET_ALL}  (at {int(tax_rate*100)}%)")
    if amazon_amt:
        print(f"  Amazon Purchases    : {Fore.YELLOW}${amazon_amt:>12,.2f}{Style.RESET_ALL}  ({amazon_count} orders)")
    if costco_amt:
        print(f"  Costco Purchases    : {Fore.CYAN}${costco_amt:>12,.2f}{Style.RESET_ALL}  ({costco_count} transactions)")
    print(f"{'─'*52}")
    print()
    print_ok(f"Report saved: {out_file}")
    print()
    print(f"  {Fore.WHITE}Sheets:{Style.RESET_ALL} Dashboard · All Transactions · Jan–Dec · Tax Deductions · Amazon · Costco")
    print()
    print(f"  {Fore.MAGENTA}Tip:{Style.RESET_ALL} Run  python main.py chat --year {args.year}  to ask AI questions about this data.")
    print()
    print(f"  {Fore.YELLOW}NOTE:{Style.RESET_ALL} Consult a licensed CPA for official tax advice.")
    print()
    return 0


# ── Command: chat ─────────────────────────────────────────────────────────────

def cmd_chat(args):
    from core.chat_interface import TaxChatInterface

    input_dir = Path(args.input)

    print(f"  Business   : {Fore.WHITE}{args.business}{Style.RESET_ALL}")
    print(f"  Tax Year   : {Fore.WHITE}{args.year}{Style.RESET_ALL}")
    backend_label = args.ai_backend.upper()
    if args.ai_backend == "local":
        backend_label += f" ({args.local_model})"
    print(f"  AI Backend : {Fore.MAGENTA}{backend_label}{Style.RESET_ALL}")
    print()

    result = load_transactions(input_dir, args.year, None, args.local_model, args.business)
    if result is None:
        return 1
    all_txns, _, _ = result

    chat = TaxChatInterface(
        transactions=all_txns,
        year=args.year,
        business_name=args.business,
        backend=args.ai_backend,
        local_model=args.local_model,
    )
    chat.repl()
    return 0


# ── Argument parser ───────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="openclaw",
        description="OpenClaw — Business Statement Tax Analyzer with AI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
COMMANDS
  (default)   Parse statements and build the Excel report
  chat        Interactive AI Q&A about your expenses

AI BACKENDS
  --ai-backend claude   Uses Anthropic Claude API (needs ANTHROPIC_API_KEY)
  --ai-backend local    Uses a local Ollama model — 100% on-device, zero cloud
                        Install Ollama: https://ollama.com
                        Pull a model:  ollama pull llama3.2

EXAMPLES
  python main.py --year 2025 --business "Acme LLC"
  python main.py --year 2025 --ai-backend claude
  python main.py --year 2025 --ai-backend local --local-model gemma3
  python main.py chat --year 2025
  python main.py chat --year 2025 --ai-backend local --local-model qwen2.5

FILE CONVENTIONS (auto-detect parser)
  amazon_*.csv  → Amazon Order History
  costco_*.csv  → Costco Purchase History
  *.csv / *.pdf → Generic bank / credit-card statement
        """,
    )

    sub = ap.add_subparsers(dest="command")

    # shared flags helper
    def add_common(p):
        p.add_argument("--year",        "-y", type=int,   default=datetime.now().year,
                       help="Tax year to analyze (default: current year)")
        p.add_argument("--input",       "-i", type=str,   default="./data/statements",
                       help="Folder containing statement files")
        p.add_argument("--business",    "-b", type=str,   default="My Business",
                       help="Business name shown in the report")
        p.add_argument("--ai-backend",  "-A", type=str,   default=None,
                       choices=["claude", "local"],
                       help="AI backend for smart categorization / chat")
        p.add_argument("--local-model", "-m", type=str,   default="llama3.2",
                       help="Ollama model name when using --ai-backend local")

    # analyze (default)
    p_analyze = sub.add_parser("analyze", help="Parse statements and export Excel report")
    add_common(p_analyze)
    p_analyze.add_argument("--output",   "-o", type=str,   default="./data/reports",
                           help="Folder for the Excel report")
    p_analyze.add_argument("--tax-rate", "-t", type=float, default=None,
                           help="Override federal tax rate (e.g. 0.24 for 24%%)")

    # chat
    p_chat = sub.add_parser("chat", help="AI Q&A about your tax data")
    add_common(p_chat)
    # default ai-backend for chat is claude if not specified
    p_chat.set_defaults(ai_backend="claude")

    # top-level flags (when no subcommand given → behave as analyze)
    add_common(ap)
    ap.add_argument("--output",   "-o", type=str,   default="./data/reports")
    ap.add_argument("--tax-rate", "-t", type=float, default=None)

    return ap


def main():
    print(BANNER)
    ap = build_parser()
    args = ap.parse_args()

    if args.command == "chat":
        return cmd_chat(args)
    else:
        # "analyze" or no subcommand
        return cmd_analyze(args)


if __name__ == "__main__":
    sys.exit(main())
