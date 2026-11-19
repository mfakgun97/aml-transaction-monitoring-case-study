"""End-to-end run: data → features → rules → model → options → reports.

    python -m aml_tm.pipeline

Every number quoted in docs/ comes from reports/results.json produced here.
"""

from __future__ import annotations

import json

import pandas as pd

from . import config as C
from . import generate_data, model as M, options as O, plots
from .features import build_features
from .rules import RULE_DESCRIPTIONS, apply_rules


def _load_or_generate():
    files = [C.DATA_DIR / f for f in ("customers.csv", "transactions.csv", "labels.csv")]
    if not all(f.exists() for f in files):
        generate_data.main()
    customers = pd.read_csv(files[0])
    tx = pd.read_csv(files[1], parse_dates=["date"])
    labels = pd.read_csv(files[2])
    return customers, tx, labels


def run() -> dict:
    C.FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    customers, tx, labels = _load_or_generate()

    print("1/5 features")
    df = build_features(tx, customers).merge(labels, on=["customer_id", "month"], how="left")
    df["profile"] = df.customer_id.map(customers.set_index("customer_id").behaviour_profile)

    print("2/5 rules")
    df = df.join(apply_rules(df, tx))

    print("3/5 model")
    train, test = M.time_split(df)
    models = M.train_models(train)
    scores = M.score(models, test)
    test = test.assign(score=scores.score_gbm)
    importance = M.feature_importance(models["gradient_boosting"], test)

    print("4/5 options")
    options, reviewed = O.evaluate_options(test, ml_slots=C.ML_SCENARIO_SLOTS)
    options["recall_ci_95"] = [list(O.bootstrap_recall_ci(test, reviewed[o])) for o in options.option]
    curve = O.capacity_curve(test)
    slots = pd.DataFrame([
        {"ml_slots": s, "recall": O.evaluate_options(test, ml_slots=s, fifo_repeats=1)[0].set_index("option").loc["C", "recall"]}
        for s in range(0, 161, 20)
    ])

    # Rule-level performance on the test period
    rule_perf = []
    for r, desc in RULE_DESCRIPTIONS.items():
        fired = test[r]
        tp = int((fired & test.is_suspicious.eq(1)).sum())
        rule_perf.append({"rule": r, "description": desc, "alerts_per_month": round(fired.sum() / len(C.TEST_MONTHS), 1),
                          "true_positives": tp, "precision": round(tp / max(fired.sum(), 1), 3),
                          "top_false_positive_profile": test[fired & test.is_suspicious.eq(0)].profile.mode().iat[0]
                          if (fired & test.is_suspicious.eq(0)).any() else None})
    rule_perf = pd.DataFrame(rule_perf)

    # Detection by typology: rules fully reviewed vs recommended option C
    pos = test[test.is_suspicious.eq(1)]
    typology = pd.DataFrame({
        "cases": pos.groupby("typology").size(),
        "rules_all_alerts_reviewed": pos.groupby("typology").rule_alert.mean().round(3),
        "option_C": pos.assign(hit=pos.index.isin(reviewed["C"])).groupby("typology").hit.mean().round(3),
        "option_D": pos.assign(hit=pos.index.isin(reviewed["D"])).groupby("typology").hit.mean().round(3),
    }).reset_index()

    # Sample alert explanations for investigators (top-scored ML-scenario alerts in option C)
    top_feats = importance.feature.head(8).tolist()
    sample = test.loc[reviewed["C"]]
    sample = sample[~sample.rule_alert].sort_values("score", ascending=False).head(10)
    sample = sample.assign(reason_codes=M.reason_codes(sample, test, top_feats))
    sample[["customer_id", "month", "score", "reason_codes", "is_suspicious", "typology", "profile"]].round(3) \
        .to_csv(C.REPORTS_DIR / "sample_ml_alerts_with_reason_codes.csv", index=False)

    print("5/5 reports")
    results = {
        "data": {
            "customers": int(customers.shape[0]), "transactions": int(tx.shape[0]),
            "customer_months": int(df.shape[0]), "suspicious_customer_months": int(df.is_suspicious.sum()),
            "prevalence": round(float(df.is_suspicious.mean()), 4),
            "train_positives": int(train.is_suspicious.sum()), "test_positives": int(test.is_suspicious.sum()),
        },
        "assumptions": {"capacity_per_month": C.INVESTIGATOR_CAPACITY_PER_MONTH,
                        "minutes_per_alert": C.MINUTES_PER_ALERT, "ml_slots_option_C": C.ML_SCENARIO_SLOTS},
        "rules_test_period": {
            "alerts_per_month": round(float(test.rule_alert.sum() / len(C.TEST_MONTHS)), 1),
            "precision": round(float(test[test.rule_alert].is_suspicious.mean()), 3),
            "recall_if_all_reviewed": round(float(test[test.rule_alert].is_suspicious.sum() / test.is_suspicious.sum()), 3),
            "per_rule": rule_perf.to_dict(orient="records"),
        },
        "model_metrics_test": M.model_metrics(test.is_suspicious, scores),
        "options": options.to_dict(orient="records"),
        "typology_detection": typology.to_dict(orient="records"),
        "ml_slots_sensitivity": slots.to_dict(orient="records"),
        "feature_importance_top10": importance.head(10).round(4).to_dict(orient="records"),
    }
    (C.REPORTS_DIR / "results.json").write_text(json.dumps(results, indent=2, default=float))
    options.to_csv(C.REPORTS_DIR / "options_comparison.csv", index=False)

    plots.make_all(results, curve, slots, importance, rule_perf, typology)
    print(options[["label", "alerts_reviewed_per_month", "suspicious_cases_caught", "recall"]].to_string(index=False))
    return results


if __name__ == "__main__":
    run()
