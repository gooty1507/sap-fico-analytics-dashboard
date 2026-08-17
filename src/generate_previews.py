"""
Render a few static preview charts (SVG) from the SAP FICO extracts, for
embedding in the README. These mirror three of the charts in the live
Streamlit dashboard (src/app.py) but are pre-rendered so they show up
directly on the GitHub repo page without anyone needing to run the app.

Usage:
    python src/generate_previews.py
    python src/generate_previews.py --data-dir data --out-dir assets
"""

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("svg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import pandas as pd

from build_export import build_aging

plt.rcParams.update(
    {
        "svg.fonttype": "none",  # keep text as <text> elements, not glyph paths (much smaller files)
        "font.size": 11,
        "axes.edgecolor": "#444444",
        "axes.labelcolor": "#222222",
        "text.color": "#222222",
        "xtick.color": "#444444",
        "ytick.color": "#444444",
        "axes.grid": True,
        "grid.color": "#e0e0e0",
        "grid.linewidth": 0.6,
        "figure.facecolor": "white",
        "axes.facecolor": "white",
    }
)

COLORS = ["#2f6fed", "#f2994a", "#27ae60", "#eb5757", "#9b51e0"]


def usd_formatter():
    return mticker.FuncFormatter(lambda x, _: f"${x/1000:,.0f}k")


def plot_gl_trend(gl, out_path):
    trend = gl.groupby(["period", "company_code"], as_index=False)["amount_usd"].sum()
    pivot = trend.pivot(index="period", columns="company_code", values="amount_usd").fillna(0)

    fig, ax = plt.subplots(figsize=(7, 4.2))
    for i, col in enumerate(pivot.columns):
        ax.plot(pivot.index.astype(str), pivot[col], marker="o", label=f"Company {col}", color=COLORS[i % len(COLORS)])
    ax.set_title("GL spend trend by month")
    ax.set_ylabel("Amount (USD)")
    ax.yaxis.set_major_formatter(usd_formatter())
    ax.legend(frameon=False)
    fig.autofmt_xdate(rotation=30)
    fig.tight_layout()
    fig.savefig(out_path, format="svg")
    plt.close(fig)


def plot_budget_vs_actual(budget, out_path):
    latest_period = budget["period"].max()
    latest = budget[budget["period"] == latest_period].sort_values("cost_center_desc")

    fig, ax = plt.subplots(figsize=(7, 4.2))
    x = range(len(latest))
    width = 0.38
    ax.bar([i - width / 2 for i in x], latest["budget_amount_usd"], width, label="Budget", color=COLORS[0])
    ax.bar([i + width / 2 for i in x], latest["actual_amount_usd"], width, label="Actual", color=COLORS[1])
    ax.set_xticks(list(x))
    ax.set_xticklabels(latest["cost_center_desc"], rotation=35, ha="right")
    ax.set_ylabel("Amount (USD)")
    ax.yaxis.set_major_formatter(usd_formatter())
    ax.set_title(f"Cost center: budget vs. actual ({latest_period})")
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(out_path, format="svg")
    plt.close(fig)


def plot_aging(ap, ar, out_path):
    bucket_order = ["Not yet due", "0-30 days", "31-60 days", "61-90 days", "90+ days"]

    ap_open = ap[ap["status"] != "Paid"]
    ar_open = ar[ar["status"] != "Paid"]
    ap_b = ap_open.groupby("aging_bucket")["amount_usd"].sum().reindex(bucket_order, fill_value=0)
    ar_b = ar_open.groupby("aging_bucket")["amount_usd"].sum().reindex(bucket_order, fill_value=0)

    fig, ax = plt.subplots(figsize=(7, 4.2))
    x = range(len(bucket_order))
    width = 0.38
    ax.bar([i - width / 2 for i in x], ap_b.values, width, label="AP (owed to vendors)", color=COLORS[3])
    ax.bar([i + width / 2 for i in x], ar_b.values, width, label="AR (owed by customers)", color=COLORS[2])
    ax.set_xticks(list(x))
    ax.set_xticklabels(bucket_order, rotation=20, ha="right")
    ax.set_ylabel("Amount (USD)")
    ax.yaxis.set_major_formatter(usd_formatter())
    ax.set_title("AP / AR aging")
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(out_path, format="svg")
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--out-dir", default="assets")
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
    ap = build_aging(ap, "invoice_number", "vendor_name")
    ar = build_aging(ar, "invoice_number", "customer_name")

    plot_gl_trend(gl, out_dir / "gl_trend.svg")
    plot_budget_vs_actual(budget, out_dir / "budget_vs_actual.svg")
    plot_aging(ap, ar, out_dir / "aging.svg")

    print(f"Wrote previews to {out_dir}/: gl_trend.svg, budget_vs_actual.svg, aging.svg")


if __name__ == "__main__":
    main()
