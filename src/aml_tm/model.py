"""ML risk score for customer-months + plain-language reason codes."""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from . import config as C
from .features import FEATURE_DESCRIPTIONS, FEATURES


def time_split(df: pd.DataFrame):
    """Out-of-time split: train on Jan–Apr, validate on May–Jun.

    A random split would let the model 'see the future' (same customers, same
    typologies, later months) and overstate performance — a classic finding
    in model validation.
    """
    return df[df.month.isin(C.TRAIN_MONTHS)], df[df.month.isin(C.TEST_MONTHS)]


def train_models(train: pd.DataFrame, seed: int = C.SEED) -> dict:
    X, y = train[FEATURES], train.is_suspicious
    gbm = HistGradientBoostingClassifier(
        max_iter=300, learning_rate=0.05, max_leaf_nodes=15, min_samples_leaf=40,
        l2_regularization=1.0, random_state=seed,
    ).fit(X, y)
    # No class re-weighting for the GBM: we use the score to *rank* alerts, and
    # re-weighting saturated the top scores (many ties at ~0.99), which makes the
    # ranking arbitrary exactly where investigators start working.
    logreg = make_pipeline(
        StandardScaler(), LogisticRegression(max_iter=2_000, class_weight="balanced", C=0.5)
    ).fit(np.log1p(X.clip(lower=0)), y)
    return {"gradient_boosting": gbm, "logistic_regression": logreg}


def score(models: dict, df: pd.DataFrame) -> pd.DataFrame:
    X = df[FEATURES]
    return pd.DataFrame({
        "score_gbm": models["gradient_boosting"].predict_proba(X)[:, 1],
        "score_logreg": models["logistic_regression"].predict_proba(np.log1p(X.clip(lower=0)))[:, 1],
    }, index=df.index)


def model_metrics(y: pd.Series, scores: pd.DataFrame) -> dict:
    return {
        col: {"pr_auc": round(average_precision_score(y, scores[col]), 3),
              "roc_auc": round(roc_auc_score(y, scores[col]), 3)}
        for col in scores
    }


def feature_importance(model, test: pd.DataFrame, seed: int = C.SEED) -> pd.DataFrame:
    """Permutation importance on the out-of-time set (model-agnostic, easy to explain)."""
    r = permutation_importance(model, test[FEATURES], test.is_suspicious, scoring="average_precision",
                               n_repeats=10, random_state=seed)
    return (pd.DataFrame({"feature": FEATURES, "importance": r.importances_mean, "std": r.importances_std})
            .assign(description=lambda d: d.feature.map(FEATURE_DESCRIPTIONS))
            .sort_values("importance", ascending=False).reset_index(drop=True))


_SHARE = {"fast_out_share", "round_amount_share"}
_RATIO = {"out_in_ratio", "in_vs_own_history"}
_FLAG = {"is_sme", "kyc_risk_high"}


def _fmt(feature: str, value: float) -> str:
    if feature in _SHARE:
        return f"{value:.0%}"
    if feature in _RATIO:
        return f"{value:.1f}x"
    if feature in _FLAG:
        return "yes" if value else "no"
    if "sum" in feature or feature.startswith("total") or feature.endswith("max"):
        return f"EUR {value:,.0f}"
    return f"{value:,.0f}"


def reason_codes(rows: pd.DataFrame, population: pd.DataFrame, top_features: list[str], k: int = 3) -> pd.Series:
    """For each alert, name the k most unusual of the model's top features.

    'Unusual' = percentile versus all customer-months in the same period.
    Output is investigator-readable and shows the actual value, e.g.
    'Share of inbound money sent out again within 2 days = 94% (top 1%)'.
    Binary flags (SME, KYC high) are excluded: they are context, not a reason.
    """
    feats = [f for f in top_features if f not in _FLAG]
    sorted_pop = {f: np.sort(population[f].to_numpy()) for f in feats}

    def top_share(f, v):  # share of customer-months with a value >= v (ties count against rarity)
        a = sorted_pop[f]
        return 1 - np.searchsorted(a, v, side="left") / len(a)

    out = []
    for idx in rows.index:
        ranked = sorted((top_share(f, rows.at[idx, f]), f) for f in feats)[:k]
        out.append("; ".join(
            f"{FEATURE_DESCRIPTIONS[f]} = {_fmt(f, rows.at[idx, f])} (top {max(100 * t, 1):.0f}%)"
            for t, f in ranked))
    return pd.Series(out, index=rows.index)
