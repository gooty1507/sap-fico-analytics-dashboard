"""
Generate synthetic SAP FICO data for the analytics dashboard.

Produces four related extracts that mimic what you'd pull from SAP via
FBL3N / FBL1N / FBL5N / KSB1-style reports:

  data/gl_postings.csv        - GL line items (cost-center relevant expense postings)
  data/ap_invoices.csv        - Vendor (accounts payable) invoices
  data/ar_invoices.csv        - Customer (accounts receivable) invoices
  data/cost_center_budget.csv - Monthly budget vs. actual by cost center

Everything is seeded (random.seed / np.random.seed = 42) so re-running this
script reproduces the exact same dataset committed to this repo.
"""

import argparse
import csv
import random
from datetime import date, timedelta
from pathlib import Path

import numpy as np

random.seed(42)
np.random.seed(42)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

TODAY = date(2026, 8, 17)

# These are overridden by main() based on --months / --demo, but keep sane
# defaults so the generator functions can also be imported and called
# directly (e.g. from a notebook) without going through argparse.
NUM_MONTHS = 12
DEMO = False

# ---------------------------------------------------------------------------
# Master data
# ---------------------------------------------------------------------------

COMPANY_CODES = {
    "1000": {"name": "Acme US Inc.", "currency": "USD", "fx_to_usd": 1.00},
    "2000": {"name": "Acme Germany GmbH", "currency": "EUR", "fx_to_usd": 1.08},
    "3000": {"name": "Acme India Pvt Ltd", "currency": "INR", "fx_to_usd": 0.012},
}

GL_ACCOUNTS = [
    ("600000", "Travel & Entertainment"),
    ("605000", "Utilities"),
    ("610000", "Salaries & Wages"),
    ("615000", "IT Services & Software"),
    ("620000", "Office Supplies"),
    ("625000", "Professional Fees"),
    ("630000", "Marketing & Advertising"),
    ("635000", "Repairs & Maintenance"),
    ("640000", "Rent & Facilities"),
]

COST_CENTERS = [
    ("CC-1000-SALES", "US Sales", "1000"),
    ("CC-1000-MKT", "US Marketing", "1000"),
    ("CC-1000-ITOPS", "US IT Operations", "1000"),
    ("CC-1000-HR", "US Human Resources", "1000"),
    ("CC-2000-PROD", "DE Production", "2000"),
    ("CC-2000-RND", "DE Research & Development", "2000"),
    ("CC-3000-SUPPORT", "IN Customer Support", "3000"),
    ("CC-3000-FIN", "IN Finance Shared Services", "3000"),
]

VENDORS = [
    ("V-{:03d}".format(i), name, cc)
    for i, (name, cc) in enumerate(
        [
            ("Global Office Supply Co.", "1000"),
            ("Meridian IT Services", "1000"),
            ("Skyline Facilities Mgmt", "1000"),
            ("Northwind Consulting", "1000"),
            ("Pinnacle Marketing Group", "1000"),
            ("Rheinland Logistics GmbH", "2000"),
            ("Bavaria Component Supply", "2000"),
            ("Deutsche Energie AG", "2000"),
            ("Berlin Software Partners", "2000"),
            ("Ganges Business Solutions", "3000"),
            ("Mumbai Facility Services", "3000"),
            ("Bangalore Tech Vendors", "3000"),
            ("Continental Travel Agency", "1000"),
            ("Apex Legal Advisors", "1000"),
            ("Horizon Telecom", "2000"),
        ],
        start=1,
    )
]

CUSTOMERS = [
    ("C-{:03d}".format(i), name, cc)
    for i, (name, cc) in enumerate(
        [
            ("Summit Retail Group", "1000"),
            ("Cascade Distributors", "1000"),
            ("Liberty Manufacturing", "1000"),
            ("Union Square Traders", "1000"),
            ("Frankfurt Handel AG", "2000"),
            ("Muenchen Vertrieb GmbH", "2000"),
            ("Nordsee Import-Export", "2000"),
            ("Delhi Wholesale Corp", "3000"),
            ("Chennai Retail Partners", "3000"),
            ("Kolkata Trading House", "3000"),
            ("Pacific Rim Traders", "1000"),
            ("Lonestar Industrial", "1000"),
            ("Hamburg Maschinenbau", "2000"),
            ("Hyderabad Digital Corp", "3000"),
        ],
        start=1,
    )
]


def month_range(num_months):
    """Return list of (year, month) tuples for the trailing num_months, ending at TODAY's month."""
    months = []
    y, m = TODAY.year, TODAY.month
    for _ in range(num_months):
        months.append((y, m))
        m -= 1
        if m == 0:
            m = 12
            y -= 1
    return list(reversed(months))


def random_date_in_month(year, month):
    if month == 12:
        next_month = date(year + 1, 1, 1)
    else:
        next_month = date(year, month + 1, 1)
    days_in_month = (next_month - date(year, month, 1)).days
    day = random.randint(1, days_in_month)
    d = date(year, month, day)
    return min(d, TODAY)


# ---------------------------------------------------------------------------
# 1. GL postings
# ---------------------------------------------------------------------------

def generate_gl_postings():
    months = month_range(NUM_MONTHS)
    rows = []
    doc_counter = 5000001

    min_accounts, max_accounts = (2, 4) if DEMO else (4, len(GL_ACCOUNTS))
    max_postings = 1 if DEMO else 3

    for (year, month) in months:
        for cc_code, cc_desc, company_code in COST_CENTERS:
            # Each cost center posts several transactions per month per account,
            # weighted so not every account is used every month.
            n_accounts_used = random.randint(min_accounts, max_accounts)
            accounts_used = random.sample(GL_ACCOUNTS, n_accounts_used)
            for gl_account, gl_desc in accounts_used:
                n_postings = random.randint(1, max_postings)
                for _ in range(n_postings):
                    currency = COMPANY_CODES[company_code]["currency"]
                    fx = COMPANY_CODES[company_code]["fx_to_usd"]

                    base_amounts = {
                        "610000": (8000, 22000),
                        "640000": (4000, 12000),
                        "615000": (1500, 9000),
                        "630000": (1000, 8000),
                        "625000": (800, 7000),
                        "600000": (300, 3500),
                        "605000": (500, 2500),
                        "620000": (150, 1800),
                        "635000": (200, 4000),
                    }
                    lo, hi = base_amounts.get(gl_account, (200, 3000))
                    amount = round(np.random.uniform(lo, hi), 2)

                    rows.append(
                        {
                            "document_number": doc_counter,
                            "posting_date": random_date_in_month(year, month).isoformat(),
                            "company_code": company_code,
                            "company_name": COMPANY_CODES[company_code]["name"],
                            "cost_center": cc_code,
                            "cost_center_desc": cc_desc,
                            "gl_account": gl_account,
                            "gl_account_desc": gl_desc,
                            "document_type": "SA",
                            "amount": amount,
                            "currency": currency,
                            "amount_usd": round(amount * fx, 2),
                        }
                    )
                    doc_counter += 1

    return rows


# ---------------------------------------------------------------------------
# 2. AP invoices (vendor / accounts payable)
# ---------------------------------------------------------------------------

def generate_ap_invoices():
    months = month_range(NUM_MONTHS)
    rows = []
    inv_counter = 1900000001

    lo, hi = (4, 7) if DEMO else (18, 28)
    for (year, month) in months:
        n_invoices = random.randint(lo, hi)
        for _ in range(n_invoices):
            vendor_id, vendor_name, company_code = random.choice(VENDORS)
            currency = COMPANY_CODES[company_code]["currency"]
            fx = COMPANY_CODES[company_code]["fx_to_usd"]

            invoice_date = random_date_in_month(year, month)
            terms_days = random.choice([30, 45, 60])
            due_date = invoice_date + timedelta(days=terms_days)
            amount = round(np.random.uniform(500, 45000), 2)

            # Payment behavior: most invoices older than terms get paid;
            # recent invoices are more likely still open.
            days_since_invoice = (TODAY - invoice_date).days
            pay_probability = min(0.95, 0.15 + days_since_invoice / 120)
            is_paid = random.random() < pay_probability

            if is_paid:
                max_delay = max(terms_days + 25, terms_days + 5)
                pay_offset = random.randint(5, max_delay)
                payment_date = invoice_date + timedelta(days=pay_offset)
                if payment_date > TODAY:
                    payment_date = TODAY
                status = "Paid"
                payment_date_str = payment_date.isoformat()
            else:
                payment_date_str = ""
                status = "Overdue" if due_date < TODAY else "Open"

            rows.append(
                {
                    "invoice_number": inv_counter,
                    "vendor_id": vendor_id,
                    "vendor_name": vendor_name,
                    "company_code": company_code,
                    "invoice_date": invoice_date.isoformat(),
                    "due_date": due_date.isoformat(),
                    "payment_terms_days": terms_days,
                    "amount": amount,
                    "currency": currency,
                    "amount_usd": round(amount * fx, 2),
                    "status": status,
                    "payment_date": payment_date_str,
                }
            )
            inv_counter += 1

    return rows


# ---------------------------------------------------------------------------
# 3. AR invoices (customer / accounts receivable)
# ---------------------------------------------------------------------------

def generate_ar_invoices():
    months = month_range(NUM_MONTHS)
    rows = []
    inv_counter = 2900000001

    lo, hi = (3, 6) if DEMO else (15, 24)
    for (year, month) in months:
        n_invoices = random.randint(lo, hi)
        for _ in range(n_invoices):
            customer_id, customer_name, company_code = random.choice(CUSTOMERS)
            currency = COMPANY_CODES[company_code]["currency"]
            fx = COMPANY_CODES[company_code]["fx_to_usd"]

            invoice_date = random_date_in_month(year, month)
            terms_days = random.choice([30, 45, 60, 90])
            due_date = invoice_date + timedelta(days=terms_days)
            amount = round(np.random.uniform(1000, 60000), 2)

            days_since_invoice = (TODAY - invoice_date).days
            pay_probability = min(0.92, 0.10 + days_since_invoice / 150)
            is_paid = random.random() < pay_probability

            if is_paid:
                max_delay = max(terms_days + 35, terms_days + 5)
                pay_offset = random.randint(5, max_delay)
                payment_date = invoice_date + timedelta(days=pay_offset)
                if payment_date > TODAY:
                    payment_date = TODAY
                status = "Paid"
                payment_date_str = payment_date.isoformat()
            else:
                payment_date_str = ""
                status = "Overdue" if due_date < TODAY else "Open"

            rows.append(
                {
                    "invoice_number": inv_counter,
                    "customer_id": customer_id,
                    "customer_name": customer_name,
                    "company_code": company_code,
                    "invoice_date": invoice_date.isoformat(),
                    "due_date": due_date.isoformat(),
                    "payment_terms_days": terms_days,
                    "amount": amount,
                    "currency": currency,
                    "amount_usd": round(amount * fx, 2),
                    "status": status,
                    "payment_date": payment_date_str,
                }
            )
            inv_counter += 1

    return rows


# ---------------------------------------------------------------------------
# 4. Cost center budget vs. actual
# ---------------------------------------------------------------------------

def generate_cost_center_budget(gl_rows):
    months = month_range(NUM_MONTHS)

    actuals = {}
    for row in gl_rows:
        pd = date.fromisoformat(row["posting_date"])
        key = (row["cost_center"], pd.year, pd.month)
        actuals[key] = actuals.get(key, 0.0) + row["amount_usd"]

    rows = []
    for cc_code, cc_desc, company_code in COST_CENTERS:
        # Give each cost center a baseline monthly budget, with mild
        # month-to-month variation, deliberately not perfectly matching actuals
        # so the dashboard has real variance to show.
        baseline = np.random.uniform(18000, 42000)
        for (year, month) in months:
            seasonal = 1.0 + 0.08 * np.sin((month / 12.0) * 2 * np.pi)
            budget = round(baseline * seasonal * np.random.uniform(0.95, 1.05), 2)
            actual = round(actuals.get((cc_code, year, month), 0.0), 2)
            variance = round(actual - budget, 2)
            variance_pct = round((variance / budget) * 100, 1) if budget else 0.0

            rows.append(
                {
                    "cost_center": cc_code,
                    "cost_center_desc": cc_desc,
                    "company_code": company_code,
                    "period": f"{year:04d}-{month:02d}",
                    "budget_amount_usd": budget,
                    "actual_amount_usd": actual,
                    "variance_usd": variance,
                    "variance_pct": variance_pct,
                }
            )

    return rows


def write_csv(path, rows, fieldnames):
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main():
    global NUM_MONTHS, DEMO

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--months", type=int, default=12,
        help="Number of trailing months of data to generate (default: 12)",
    )
    parser.add_argument(
        "--demo", action="store_true",
        help="Generate a smaller dataset (fewer postings/invoices per month) "
             "so the CSVs stay easy to browse directly on GitHub. This is "
             "what's committed to data/ in this repo.",
    )
    args = parser.parse_args()

    NUM_MONTHS = args.months
    DEMO = args.demo

    gl_rows = generate_gl_postings()
    ap_rows = generate_ap_invoices()
    ar_rows = generate_ar_invoices()
    budget_rows = generate_cost_center_budget(gl_rows)

    write_csv(
        DATA_DIR / "gl_postings.csv",
        gl_rows,
        [
            "document_number", "posting_date", "company_code", "company_name",
            "cost_center", "cost_center_desc", "gl_account", "gl_account_desc",
            "document_type", "amount", "currency", "amount_usd",
        ],
    )
    write_csv(
        DATA_DIR / "ap_invoices.csv",
        ap_rows,
        [
            "invoice_number", "vendor_id", "vendor_name", "company_code",
            "invoice_date", "due_date", "payment_terms_days", "amount",
            "currency", "amount_usd", "status", "payment_date",
        ],
    )
    write_csv(
        DATA_DIR / "ar_invoices.csv",
        ar_rows,
        [
            "invoice_number", "customer_id", "customer_name", "company_code",
            "invoice_date", "due_date", "payment_terms_days", "amount",
            "currency", "amount_usd", "status", "payment_date",
        ],
    )
    write_csv(
        DATA_DIR / "cost_center_budget.csv",
        budget_rows,
        [
            "cost_center", "cost_center_desc", "company_code", "period",
            "budget_amount_usd", "actual_amount_usd", "variance_usd", "variance_pct",
        ],
    )

    print(f"GL postings:        {len(gl_rows)} rows")
    print(f"AP invoices:         {len(ap_rows)} rows")
    print(f"AR invoices:         {len(ar_rows)} rows")
    print(f"Cost center budget:  {len(budget_rows)} rows")


if __name__ == "__main__":
    main()
