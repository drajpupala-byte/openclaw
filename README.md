# OpenClaw — Business Statement Tax Analyzer

Automatically parses your bank statements, Amazon order history, and Costco
purchase history, then exports a formatted Excel workbook with monthly
breakdowns and tax deduction summaries.

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Add your statement files to data/statements/
#    (see "How to Export" below)

# 3. Run the analyzer
python main.py --year 2025 --business "Your Business Name"

# 4. Open the report
open data/reports/TaxReport_Your_Business_Name_2025.xlsx
```

---

## Excel Report Sheets

| Sheet | Contents |
|---|---|
| **Dashboard** | Year-at-a-glance: category x month pivot table, KPI summary |
| **All Transactions** | Every expense with category, deductible amount, source |
| **Jan - Dec** | Monthly detail sheets (only months with data are created) |
| **Tax Deductions** | All deductible items + estimated savings at every tax bracket |
| **Amazon** | Amazon-only purchases with monthly totals |
| **Costco** | Costco-only purchases with monthly totals |

---

## How to Export Your Statements

### Amazon Order History
1. Go to **amazon.com -> Returns & Orders -> Order History Reports**
   - URL: https://www.amazon.com/gp/b2b/reports
2. Select **Report Type: Items**, choose your year, click **Request Report**
3. Download the CSV when ready
4. Rename the file to start with **`amazon_`** (e.g. `amazon_2025.csv`)
5. Place in `data/statements/`

### Costco Purchase History
1. Go to **costco.com -> Orders & Returns**
2. Select the year range, click **Export** or look for a download/CSV option
3. Rename the file to start with **`costco_`** (e.g. `costco_2025.csv`)
4. Place in `data/statements/`

### Bank / Credit Card Statements
Most banks let you download a CSV from their website:
- **Chase**: Account -> Download -> CSV
- **Bank of America**: Statements -> Download -> CSV
- **Wells Fargo**: Activity -> Export -> CSV
- **Citi**: Transactions -> Download -> CSV
- **Amex**: Statements -> Download Statement -> CSV
- Any bank PDF statement also works (text-based, not scanned)

Place all CSV/PDF files in `data/statements/`. The filename helps auto-detect
the right parser:

| Filename starts with | Parser used |
|---|---|
| `amazon_` | Amazon order history |
| `costco_` | Costco purchase history |
| anything else | Generic bank/credit-card CSV |

---

## Command-Line Options

```
python main.py [OPTIONS]

Options:
  --year,     -y  INT    Tax year to analyze          (default: current year)
  --input,    -i  PATH   Folder with statement files  (default: ./data/statements)
  --output,   -o  PATH   Folder for Excel report      (default: ./data/reports)
  --business, -b  TEXT   Business name in the report  (default: "My Business")
  --tax-rate, -t  FLOAT  Override tax rate for savings (e.g. 0.24 for 24%)
  --help,     -h         Show this help message
```

---

## Tax Categories (Auto-Detected)

| Category | Deduction Rate | Examples |
|---|---|---|
| Office Supplies | 100% | Staples, Office Depot, paper, ink |
| Technology & Software | 100% | Apple, Microsoft, Adobe, monitors |
| Business Subscriptions | 100% | QuickBooks, Zoom, Slack, LinkedIn |
| Travel & Transportation | 100% | Airlines, hotels, Uber, gas |
| Professional Services | 100% | Accountants, lawyers, consultants |
| Advertising & Marketing | 100% | Google Ads, Facebook Ads, Fiverr |
| Utilities & Communications | 100% | AT&T, Comcast, Verizon |
| **Amazon Business** | 100% | All items from amazon_*.csv |
| **Costco Business** | 100% | All items from costco_*.csv |
| Business Meals | **50%** | Restaurants, catering (IRS rule) |
| Insurance | 100% | Business insurance premiums |
| Rent & Facilities | 100% | Office rent, storage, coworking |
| Shipping & Postage | 100% | FedEx, UPS, USPS, DHL |
| Banking & Finance | 100% | Wire fees, merchant fees |

To add custom keywords, edit `config/categories.json`.

---

## Sample Data

Test the tool immediately with the included samples:

```bash
cp sample_data/*.csv data/statements/
python main.py --year 2025 --business "Demo Business LLC"
```

---

> **Disclaimer**: This tool is for reference and record-keeping only.
> Always consult a licensed CPA or tax professional for official tax advice.
