"""Baseline rule-based detection scenarios (the 'current production' system).

Each rule is a plain function of the customer-month feature table so that it
is fully transparent and testable. An alert is raised for a customer-month if
*any* rule fires; the list of fired rules is kept for the investigator.
"""

from __future__ import annotations

import pandas as pd

from . import config as C

RULE_DESCRIPTIONS = {
    "R1_large_cash": "Single cash deposit of EUR 10,000 or more",
    "R2_structuring": "3+ cash deposits between EUR 8,000 and 10,000 in one month",
    "R3_high_risk_country": "EUR 5,000+ sent to high-risk jurisdictions in one month",
    "R4_rapid_movement": "EUR 10,000+ inflow of which 80%+ leaves again within 2 days",
}


def _r1(f, p):
    return f.cash_dep_max >= p["min_cash_deposit"]


def _r2(f, p, tx_band_counts=None):
    # Uses the transaction-level band count when available (exact band),
    # otherwise falls back to the 7.5k–10k feature.
    counts = tx_band_counts if tx_band_counts is not None else f.cash_dep_near_threshold
    return counts >= p["min_count"]


def _r3(f, p):
    return f.hr_out_sum >= p["min_amount_out"]


def _r4(f, p):
    return (f.total_in >= p["min_inflow"]) & (f.fast_out_share >= p["min_fast_out_share"])


def structuring_band_counts(tx: pd.DataFrame, features: pd.DataFrame, params=None) -> pd.Series:
    """Exact count of cash deposits inside the R2 band, aligned to the feature table."""
    p = (params or C.RULES)["R2_structuring"]
    t = tx[(tx.tx_type == "cash_deposit") & tx.amount.between(p["band_low"], p["band_high"], inclusive="left")]
    counts = t.groupby([t.customer_id, pd.to_datetime(t.date).dt.month]).size()
    idx = pd.MultiIndex.from_frame(features[["customer_id", "month"]])
    return pd.Series(counts.reindex(idx, fill_value=0).values, index=features.index)


def apply_rules(features: pd.DataFrame, tx: pd.DataFrame | None = None, params: dict | None = None) -> pd.DataFrame:
    """Return one boolean column per rule plus `rule_alert` and `rules_fired`."""
    p = params or C.RULES
    band = structuring_band_counts(tx, features, p) if tx is not None else None
    out = pd.DataFrame(index=features.index)
    out["R1_large_cash"] = _r1(features, p["R1_large_cash"])
    out["R2_structuring"] = _r2(features, p["R2_structuring"], band)
    out["R3_high_risk_country"] = _r3(features, p["R3_high_risk_country"])
    out["R4_rapid_movement"] = _r4(features, p["R4_rapid_movement"])
    rule_cols = list(RULE_DESCRIPTIONS)
    out["rule_alert"] = out[rule_cols].any(axis=1)
    out["rules_fired"] = out[rule_cols].apply(lambda r: ",".join(c.split("_")[0] for c in rule_cols if r[c]), axis=1)
    return out
