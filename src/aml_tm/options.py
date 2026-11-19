"""Evaluate the decision options under a fixed investigator capacity.

The question the business actually asks is not 'what is the AUC?' but:
"With the people we have, how many suspicious cases do we catch, and what
changes for the investigators?" Every option below is therefore evaluated
per month at the same capacity (config.INVESTIGATOR_CAPACITY_PER_MONTH).

Options
-------
A  Status quo        – rule alerts worked first-in-first-out (FIFO) until capacity runs out
B  Prioritise        – same rule alerts, worked in order of ML risk score
C  Prioritise + new  – B, plus a capped ML-only "scenario" for cases no rule catches
D  Replace           – ML score only; rules switched off
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import config as C

OPTION_LABELS = {
    "A": "A. Status quo (rules, FIFO)",
    "B": "B. Rules + ML prioritisation",
    "C": "C. B + capped ML scenario",
    "D": "D. ML replaces rules",
}


def _select_month(m: pd.DataFrame, option: str, capacity: int, ml_slots: int, rng) -> pd.Index:
    rule = m[m.rule_alert]
    if option == "A":
        # FIFO ≈ arrival order, which is unrelated to risk → random order
        return rule.sample(frac=1.0, random_state=int(rng.integers(1e9))).index[:capacity]
    if option == "B":
        return rule.sort_values("score", ascending=False).index[:capacity]
    if option == "C":
        new = m[~m.rule_alert].sort_values("score", ascending=False).index[:ml_slots]
        rule_part = rule.sort_values("score", ascending=False).index[: capacity - len(new)]
        return rule_part.append(new)
    if option == "D":
        return m.sort_values("score", ascending=False).index[:capacity]
    raise ValueError(option)


def evaluate_options(df: pd.DataFrame, capacity: int = C.INVESTIGATOR_CAPACITY_PER_MONTH,
                     ml_slots: int = C.ML_SCENARIO_SLOTS, fifo_repeats: int = 200, seed: int = C.SEED) -> tuple[pd.DataFrame, dict]:
    """df: test-period customer-months with columns rule_alert, score, is_suspicious, typology, month."""
    rng = np.random.default_rng(seed)
    total_pos = int(df.is_suspicious.sum())
    n_months = df.month.nunique()
    rows, reviewed_sets = [], {}

    for opt in OPTION_LABELS:
        repeats = fifo_repeats if opt == "A" else 1
        tp_runs, reviewed_last = [], None
        for _ in range(repeats):
            reviewed = pd.Index([])
            for _, m in df.groupby("month"):
                reviewed = reviewed.append(_select_month(m, opt, capacity, ml_slots, rng))
            tp_runs.append(int(df.loc[reviewed, "is_suspicious"].sum()))
            reviewed_last = reviewed
        reviewed_sets[opt] = reviewed_last
        tp = float(np.mean(tp_runs))
        n_rev = len(reviewed_last)
        generated = int(df.rule_alert.sum()) if opt in "ABC" else n_rev
        if opt == "C":
            generated += ml_slots * n_months
        rows.append({
            "option": opt,
            "label": OPTION_LABELS[opt],
            "alerts_generated_per_month": round(generated / n_months, 1),
            "alerts_reviewed_per_month": round(n_rev / n_months, 1),
            "backlog_per_month": round(max(generated - n_rev, 0) / n_months, 1),
            "suspicious_cases_caught": round(tp, 1),
            "recall": round(tp / total_pos, 3),
            "precision_of_reviewed": round(tp / max(n_rev, 1), 3),
            "investigator_hours_per_month": round(n_rev / n_months * C.MINUTES_PER_ALERT / 60, 0),
        })
    return pd.DataFrame(rows), reviewed_sets


def bootstrap_recall_ci(df: pd.DataFrame, reviewed: pd.Index, n_boot: int = 1_000, seed: int = C.SEED) -> tuple[float, float]:
    """95% CI for recall, resampling *customers* (positives are rare, so honesty about uncertainty matters)."""
    rng = np.random.default_rng(seed)
    hit = df.index.isin(reviewed)
    per_cust = (pd.DataFrame({"cid": df.customer_id, "pos": df.is_suspicious, "hit": df.is_suspicious & hit})
                .groupby("cid")[["pos", "hit"]].sum())
    pos, hits = per_cust.pos.values, per_cust.hit.values
    stats = []
    for _ in range(n_boot):
        i = rng.integers(0, len(pos), len(pos))
        stats.append(hits[i].sum() / max(pos[i].sum(), 1))
    return round(float(np.percentile(stats, 2.5)), 3), round(float(np.percentile(stats, 97.5)), 3)


def capacity_curve(df: pd.DataFrame, capacities=range(10, 401, 10)) -> pd.DataFrame:
    """Recall achieved by ranking ALL customer-months by score, at different monthly capacities."""
    total = df.is_suspicious.sum()
    out = []
    for cap in capacities:
        tp = sum(m.sort_values("score", ascending=False).head(cap).is_suspicious.sum() for _, m in df.groupby("month"))
        out.append({"alerts_per_month": cap, "recall": tp / total})
    return pd.DataFrame(out)
