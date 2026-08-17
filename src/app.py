"""
SAP FICO Data Analytics Dashboard

An interactive Streamlit app over synthetic SAP FI/CO extracts (GL postings,
AP invoices, AR invoices, cost center budgets) — the kind of self-service
reporting layer a Finance Systems Analyst builds on top of SAP data exports
when the business needs answers faster than a custom ABAP report or a
manual pivot table.

Run it with:
    streamlit run src/app.py
"""

from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from build_export import build_aging

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

st.set_page_config(
    page_title="SAP FICO Analytics Dashboard",
    page_icon="📊",
    layout="wide",
)


@st.cache_data
def load_data():
    gl = pd.read_csv(DATA_DIR / "gl_postings.csv")
    ap = pd.read_csv(DATA_DIR / "ap_invoices.csv")
    ar = pd.read_csv(DATA_DIR / "ar_invoices.csv")
    budget = pd.read_csv(DATA_DIR / "cost_center_budget.csv")

    gl["posting_date"] = pd.to_datetime(gl["posting_date"])
    gl["period"] = gl["posting_date"].dt.to_period("M").astype(str)

    ap = build_aging(ap, "invoice_number", "vendor_name")
    ar = build_aging(ar, "invoice_number", "customer_name")

    return gl, ap, ar, budget


gl, ap, ar, budget = load_data()

# ---------------------------------------------------------------------------
# Sidebar filters
# ---------------------------------------------------------------------------

st.sidebar.header("Filters")

company_codes = sorted(gl["company_code"].astype(str).unique())
selected_companies = st.sidebar.multiselect(
    "Company code", company_codes, default=company_codes
)

cost_centers = sorted(gl["cost_center"].unique())
selected_cost_centers = st.sidebar.multiselect(
    "Cost center", cost_centers, default=cost_centers
)

min_date = gl["posting_date"].min().date()
max_date = gl["posting_date"].max().date()
date_range = st.sidebar.date_input(
    "Posting date range", value=(min_date, max_date), min_value=min_date, max_value=max_date
)
if isinstance(date_range, tuple) and len(date_range) == 2:
    start_date, end_date = date_range
else:
    start_date, end_date = min_date, max_date

# ---------------------------------------------------------------------------
# Apply filters
# ---------------------------------------------------------------------------

gl_f = gl[
    gl["company_code"].astype(str).isin(selected_companies)
    & gl["cost_center"].isin(selected_cost_centers)
    & (gl["posting_date"].dt.date >= start_date)
    & (gl["posting_date"].dt.date <= end_date)
]
ap_f = ap[ap["company_code"].astype(str).isin(selected_companies)]
ar_f = ar[ar["company_code"].astype(str).isin(selected_companies)]
budget_f = budget[
    budget["company_code"].astype(str).isin(selected_companies)
    & budget["cost_center"].isin(selected_cost_centers)
]

# ---------------------------------------------------------------------------
# Header + KPIs
# ---------------------------------------------------------------------------

st.title("📊 SAP FICO Data Analytics Dashboard")
st.caption(
    "Synthetic SAP FI/CO data — GL postings, AP/AR invoices, and cost center "
    "budgets. Use the filters in the sidebar to slice by company code, cost "
    "center, and posting date."
)

total_gl_spend = gl_f["amount_usd"].sum()
ap_outstanding = ap_f.loc[ap_f["status"] != "Paid", "amount_usd"].sum()
ar_outstanding = ar_f.loc[ar_f["status"] != "Paid", "amount_usd"].sum()

latest_period = budget_f["period"].max() if not budget_f.empty else None
latest_budget = budget_f[budget_f["period"] == latest_period] if latest_period else budget_f
over_budget_count = int((latest_budget["variance_usd"] > 0).sum())
total_cc_count = latest_budget["cost_center"].nunique()

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total GL spend (USD)", f"${total_gl_spend:,.0f}")
col2.metric("AP outstanding (USD)", f"${ap_outstanding:,.0f}")
col3.metric("AR outstanding (USD)", f"${ar_outstanding:,.0f}")
col4.metric(
    "Cost centers over budget",
    f"{over_budget_count} / {total_cc_count}" if total_cc_count else "n/a",
    help=f"As of the latest period in the filtered data ({latest_period}).",
)

st.divider()

# ---------------------------------------------------------------------------
# GL trend + cost center budget vs actual
# ---------------------------------------------------------------------------

left, right = st.columns(2)

with left:
    st.subheader("GL spend trend by month")
    trend = gl_f.groupby(["period", "company_code"], as_index=False)["amount_usd"].sum()
    if trend.empty:
        st.info("No GL postings match the current filters.")
    else:
        fig = px.line(
            trend, x="period", y="amount_usd", color="company_code", markers=True,
            labels={"amount_usd": "Amount (USD)", "period": "Period", "company_code": "Company code"},
        )
        st.plotly_chart(fig, use_container_width=True)

with right:
    st.subheader("Cost center: budget vs. actual (latest period)")
    if latest_budget.empty:
        st.info("No budget data matches the current filters.")
    else:
        melted = latest_budget.melt(
            id_vars=["cost_center_desc"],
            value_vars=["budget_amount_usd", "actual_amount_usd"],
            var_name="type", value_name="amount_usd",
        )
        fig = px.bar(
            melted, x="cost_center_desc", y="amount_usd", color="type", barmode="group",
            labels={"amount_usd": "Amount (USD)", "cost_center_desc": "Cost center", "type": ""},
        )
        fig.update_xaxes(tickangle=-30)
        st.plotly_chart(fig, use_container_width=True)

# ---------------------------------------------------------------------------
# AP / AR aging
# ---------------------------------------------------------------------------

left, right = st.columns(2)

bucket_order = ["Not yet due", "0-30 days", "31-60 days", "61-90 days", "90+ days", "Paid"]

with left:
    st.subheader("AP aging (vendor invoices)")
    ap_open = ap_f[ap_f["status"] != "Paid"]
    if ap_open.empty:
        st.info("No open AP invoices match the current filters.")
    else:
        ap_bucketed = (
            ap_open.groupby("aging_bucket", as_index=False)["amount_usd"].sum()
        )
        ap_bucketed["aging_bucket"] = pd.Categorical(
            ap_bucketed["aging_bucket"], categories=bucket_order, ordered=True
        )
        ap_bucketed = ap_bucketed.sort_values("aging_bucket")
        fig = px.bar(
            ap_bucketed, x="aging_bucket", y="amount_usd",
            labels={"amount_usd": "Amount (USD)", "aging_bucket": "Aging bucket"},
        )
        st.plotly_chart(fig, use_container_width=True)

with right:
    st.subheader("AR aging (customer invoices)")
    ar_open = ar_f[ar_f["status"] != "Paid"]
    if ar_open.empty:
        st.info("No open AR invoices match the current filters.")
    else:
        ar_bucketed = (
            ar_open.groupby("aging_bucket", as_index=False)["amount_usd"].sum()
        )
        ar_bucketed["aging_bucket"] = pd.Categorical(
            ar_bucketed["aging_bucket"], categories=bucket_order, ordered=True
        )
        ar_bucketed = ar_bucketed.sort_values("aging_bucket")
        fig = px.bar(
            ar_bucketed, x="aging_bucket", y="amount_usd",
            labels={"amount_usd": "Amount (USD)", "aging_bucket": "Aging bucket"},
        )
        st.plotly_chart(fig, use_container_width=True)

# ---------------------------------------------------------------------------
# Spend breakdowns
# ---------------------------------------------------------------------------

left, right = st.columns(2)

with left:
    st.subheader("GL spend by account")
    by_account = gl_f.groupby("gl_account_desc", as_index=False)["amount_usd"].sum()
    by_account = by_account.sort_values("amount_usd", ascending=False)
    if by_account.empty:
        st.info("No GL postings match the current filters.")
    else:
        fig = px.pie(by_account, names="gl_account_desc", values="amount_usd", hole=0.4)
        st.plotly_chart(fig, use_container_width=True)

with right:
    st.subheader("Top 10 vendors by AP spend")
    top_vendors = (
        ap_f.groupby("vendor_name", as_index=False)["amount_usd"].sum()
        .sort_values("amount_usd", ascending=False)
        .head(10)
    )
    if top_vendors.empty:
        st.info("No AP invoices match the current filters.")
    else:
        fig = px.bar(
            top_vendors.sort_values("amount_usd"), x="amount_usd", y="vendor_name", orientation="h",
            labels={"amount_usd": "Amount (USD)", "vendor_name": "Vendor"},
        )
        st.plotly_chart(fig, use_container_width=True)

st.divider()
with st.expander("View filtered raw data"):
    tab1, tab2, tab3, tab4 = st.tabs(["GL postings", "AP invoices", "AR invoices", "Cost center budget"])
    tab1.dataframe(gl_f, use_container_width=True)
    tab2.dataframe(ap_f, use_container_width=True)
    tab3.dataframe(ar_f, use_container_width=True)
    tab4.dataframe(budget_f, use_container_width=True)
