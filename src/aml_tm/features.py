"""Customer-month feature table.

Transaction monitoring is usually evaluated per *customer-period*: an alert
is raised on a customer for a review window, not on a single payment. Every
feature below is something an AML investigator can describe in one sentence,
which is a deliberate design choice (see docs/02_requirements.md, NFR-2).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import config as C

FEATURE_DESCRIPTIONS = {
    "n_tx": "Number of transactions in the month",
    "total_in": "Total inbound amount (EUR)",
    "total_out": "Total outbound amount (EUR)",
    "cash_dep_count": "Number of cash deposits",
    "cash_dep_sum": "Total cash deposited (EUR)",
    "cash_dep_max": "Largest single cash deposit (EUR)",
    "cash_dep_near_threshold": "Cash deposits between EUR 7.5k and 10k (just below reporting line)",
    "hr_out_sum": "Amount sent to high-risk jurisdictions (EUR)",
    "hr_out_count": "Number of transfers to high-risk jurisdictions",
    "n_distinct_senders": "Distinct counterparties sending money in",
    "n_distinct_receivers": "Distinct counterparties receiving money",
    "fast_out_share": "Share of inbound money sent out again within 2 days",
    "out_in_ratio": "Outbound / inbound amount (capped at 3)",
    "round_amount_share": "Share of outbound transfers that are round EUR 500 multiples",
    "in_vs_own_history": "Inbound amount vs the customer's own average of previous months",
    "is_sme": "Customer is an SME (vs retail)",
    "kyc_risk_high": "KYC risk rating is 'high'",
    "account_age_months": "Account age in months",
}
FEATURES = list(FEATURE_DESCRIPTIONS)


def _fast_out_share(tx: pd.DataFrame) -> pd.Series:
    """Share of inbound money matched by outbound money within 0–2 days.

    Day-level approximation: for each day d, the 'forwarded' amount is
    min(inflow_d, outflow_d + outflow_{d+1} + outflow_{d+2}). Card payments and
    ATM withdrawals are excluded so normal spending doesn't count as layering.
    """
    t = tx[tx.tx_type.isin(["transfer", "cash_deposit", "salary"])].astype({"amount": float})
    daily = (t.assign(day=t.date.dt.normalize())
             .pivot_table(index=["customer_id", "day"], columns="direction",
                          values="amount", aggfunc="sum", fill_value=0.0)
             .reindex(columns=["in", "out"], fill_value=0.0)
             .reset_index()
             .sort_values(["customer_id", "day"]))
    # Forward-looking 3-day outflow per customer, on a complete daily calendar
    out = []
    for cid, g in daily.groupby("customer_id", sort=False):
        s = g.set_index("day")[["in", "out"]].asfreq("D", fill_value=0.0)
        fwd_out = s["out"][::-1].rolling(3, min_periods=1).sum()[::-1]
        matched = np.minimum(s["in"], fwd_out)
        out.append(pd.DataFrame({"customer_id": cid, "month": s.index.month,
                                 "matched": matched.values, "inflow": s["in"].values}))
    m = pd.concat(out).groupby(["customer_id", "month"])[["matched", "inflow"]].sum()
    return (m.matched / m.inflow.replace(0, np.nan)).fillna(0.0).rename("fast_out_share")


def build_features(tx: pd.DataFrame, customers: pd.DataFrame) -> pd.DataFrame:
    tx = tx.copy()
    tx["date"] = pd.to_datetime(tx["date"])
    tx["month"] = tx.date.dt.month
    is_in, is_out = tx.direction.eq("in"), tx.direction.eq("out")
    is_cash = tx.tx_type.eq("cash_deposit")
    is_hr = tx.counterparty_country.isin(C.HIGH_RISK_COUNTRIES) & is_out
    is_transfer_out = tx.tx_type.eq("transfer") & is_out

    tx = tx.assign(
        amt_in=tx.amount.where(is_in, 0.0),
        amt_out=tx.amount.where(is_out, 0.0),
        cash_amt=tx.amount.where(is_cash, 0.0),
        cash_flag=is_cash.astype(int),
        near_thr=(is_cash & tx.amount.between(7_500, 10_000, inclusive="left")).astype(int),
        hr_amt=tx.amount.where(is_hr, 0.0),
        hr_flag=is_hr.astype(int),
        sender=tx.counterparty_id.where(is_in & tx.tx_type.eq("transfer")),
        receiver=tx.counterparty_id.where(is_transfer_out),
        tr_out=is_transfer_out.astype(int),
        round_out=(is_transfer_out & (tx.amount % 500 == 0)).astype(int),
    )
    g = tx.groupby(["customer_id", "month"])
    f = pd.DataFrame({
        "n_tx": g.size(),
        "total_in": g.amt_in.sum(),
        "total_out": g.amt_out.sum(),
        "cash_dep_count": g.cash_flag.sum(),
        "cash_dep_sum": g.cash_amt.sum(),
        "cash_dep_max": g.cash_amt.max(),
        "cash_dep_near_threshold": g.near_thr.sum(),
        "hr_out_sum": g.hr_amt.sum(),
        "hr_out_count": g.hr_flag.sum(),
        "n_distinct_senders": g.sender.nunique(),
        "n_distinct_receivers": g.receiver.nunique(),
        "round_amount_share": g.round_out.sum() / g.tr_out.sum().replace(0, np.nan),
    }).fillna({"round_amount_share": 0.0})
    f["out_in_ratio"] = (f.total_out / f.total_in.replace(0, np.nan)).fillna(0).clip(upper=3)
    f = f.join(_fast_out_share(tx)).fillna({"fast_out_share": 0.0}).reset_index()

    # Behavioural baseline: compare to the customer's own *previous* months only
    # (no look-ahead, so the feature is computable in production on day 1 of a month).
    f = f.sort_values(["customer_id", "month"])
    prev_mean = f.groupby("customer_id").total_in.transform(lambda s: s.shift().expanding().mean())
    f["in_vs_own_history"] = (f.total_in / prev_mean).replace([np.inf], np.nan).fillna(1.0).clip(upper=20)

    cust = customers.set_index("customer_id")
    f["is_sme"] = f.customer_id.map(cust.segment.eq("sme")).astype(int)
    f["kyc_risk_high"] = f.customer_id.map(cust.kyc_risk_rating.eq("high")).astype(int)
    f["account_age_months"] = f.customer_id.map(cust.account_age_months)
    return f.reset_index(drop=True)
