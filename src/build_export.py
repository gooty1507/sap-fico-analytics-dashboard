"""
Build a clean, multi-sheet Excel workbook from the raw SAP FICO extracts,
ready to import straight into Power BI or Tableau as a data source.

Usage:
    python src/build_export.py
    python src/build_export.py --data-dir data --out exports/sap_fico_analytics_export.xlsx

The raw CSVs in data/ are already tidy, but this script:
  - computes AP/AR aging buckets and days-to-pay / days-overdue,
  - adds a period (year-month) column to GL postings for easy pivoting,
  - builds a one-sheet KPI summary so the workbook is useful on its own,
  - writes everything to a single .xlsx with one table per sheet.
"""

import argparse
from datetime import date
from pathlib import Path

import pandas as pd

TODAY = date(2026, 8, 17)

AGING_BUCKETS = [
    (0, 30, "0-30 days"),
    (31, 60, "31-60 days"),
    (61, 90, "61-90 days"),
    (91, float("inf"), "90+ days"),
]


def aging_bucket(days_overdue):
    if days_overdue <= 0:
        return "Not yet due"
    for lo, hi, label in AGING_BUCKETS:
        if lo <= days_overdue <= hi:
            return label
    return "90+ days"


def build_aging(df, id_col, party_col):
    df = df.copy()
    df["due_date"] = pd.to_datetime(df["due_date"])
    df["invoice_date"] = pd.to_datetime(df["invoice_date"])

    as_of = pd.Timestamp(TODAY)
    df["days_overdue"] = (as_of - df["due_date"]).dt.days.clip(lower=0)
    df.loc[df["status"] == "Paid", "days_overdue"] = 0
    df["aging_bucket"] = df.apply(
        lambda r: "Paid" if r["status"] == "Paid" else aging_bucket(r["days_overdue"]),
        axis=1,
    )

    paid_mask = df["status"] == "Paid"
    df["days_to_pay"] = pd.NA
    if paid_mask.any():
        payment_date = pd.to_datetime(df.loc[paid_mask, "payment_date"])
        df.loc[paid_mask, "days_to_pay"] = (
            payment_date - df.loc[paid_mask, "invoice_date"]
        ).dt.days

    return df


def build_kpi_summary(gl, ap, ar, budget):
    total_gl_spend = gl["amount_usd"].sum()

    ap_outstanding = ap.loc[ap["status"] != "Paid", "amount_usd"].sum()
    ap_overdue = ap.loc[ap["status"] == "Overdue", "amount_usd"].sum()
    ar_outstanding = ar.loc[ar["status"] != "Paid", "amount_usd"].sum()
    ar_overdue = ar.loc[ar["status"] == "Overdue", "amount_usd"].sum()

    ap_paid = ap[ap["status"] == "Paid"]
    ar_paid = ar[ar["status"] == "Paid"]
    avg_ap_days_to_pay = ap_paid["days_to_pay"].mean() if len(ap_paid) else float("nan")
    avg_ar_days_to_pay = ar_paid["days_to_pay"].mean() if len(ar_paid) else float("nan")

    cc_latest = budget.sort_values("period").groupby("cost_center").tail(1)
    cost_centers_over_budget = int((cc_latest["variance_usd"] > 0).sum())
    total_cost_centers = cc_latest["cost_center"].nunique()

    rows = [
        ("Total GL spend (USD, trailing period)", round(total_gl_spend, 2)),
        ("AP outstanding (USD)", round(ap_outstanding, 2)),
        ("AP overdue (USD)", round(ap_overdue, 2)),
        ("AR outstanding (USD)", round(ar_outstanding, 2)),
        ("AR overdue (USD)", round(ar_overdue, 2)),
        ("Avg days to pay vendors (AP)", round(avg_ap_days_to_pay, 1)),
        ("Avg days to collect from customers (AR)", round(avg_ar_days_to_pay, 1)),
        ("Cost centers over budget (latest period)", f"{cost_centers_over_budget} / {total_cost_centers}"),
    ]
    return pd.DataFrame(rows, columns=["metric", "value"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--out-dir", default="exports")
    parser.add_argument(
        "--xlsx", action="store_true",
        help="Also write a single combined sap_fico_analytics_export.xlsx "
             "workbook (requires openpyxl). The flat CSVs are written either way.",
    )
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    gl = pd.read_csv(data_dir / "gl_postings.csv")
    ap = pd.read_csv(data_dir / "ap_invoices.csv")
    ar = pd.read_csv(data_dir / "ar_invoices.csv")
    budget = pd.read_csv(data_dir / "cost_center_budget.csv")

    gl["posting_date"] = pd.to_datetime(gl["posting_date"])
    gl["period"] = gl["posting_date"].dt.to_period("M").astype(str)

    ap_aging = build_aging(ap, "invoice_number", "vendor_name")
    ar_aging = build_aging(ar, "invoice_number", "customer_name")

    kpi_summary = build_kpi_summary(gl, ap_aging, ar_aging, budget)

    # Flat CSVs are the primary deliverable here: Power BI and Tableau both
    # import a folder of clean CSVs directly, no Python required to use them.
    kpi_summary.to_csv(out_dir / "kpi_summary.csv", index=False)
    gl.to_csv(out_dir / "gl_postings_clean.csv", index=False)
    ap_aging.to_csv(out_dir / "ap_aging.csv", index=False)
    ar_aging.to_csv(out_dir / "ar_aging.csv", index=False)
    budget.to_csv(out_dir / "cost_center_budget_vs_actual.csv", index=False)

    print(
        f"Wrote CSVs to {out_dir}/: kpi_summary.csv, gl_postings_clean.csv, "
        f"ap_aging.csv, ar_aging.csv, cost_center_budget_vs_actual.csv"
    )

    if args.xlsx:
        xlsx_path = out_dir / "sap_fico_analytics_export.xlsx"
        with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
            kpi_summary.to_excel(writer, sheet_name="KPI_Summary", index=False)
            gl.to_excel(writer, sheet_name="GL_Postings", index=False)
            ap_aging.to_excel(writer, sheet_name="AP_Aging", index=False)
            ar_aging.to_excel(writer, sheet_name="AR_Aging", index=False)
            budget.to_excel(writer, sheet_name="CostCenter_Budget_vs_Actual", index=False)
        print(f"Wrote {xlsx_path}")


if __name__ == "__main__":
    main()
