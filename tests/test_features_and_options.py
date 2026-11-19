import numpy as np
import pandas as pd

from aml_tm import config as C
from aml_tm.features import FEATURES, build_features
from aml_tm.generate_data import generate
from aml_tm.options import evaluate_options


def _tx(rows):
    df = pd.DataFrame(rows, columns=["customer_id", "date", "tx_type", "direction", "amount", "counterparty_id", "counterparty_country"])
    df["date"] = pd.to_datetime(df["date"])
    return df


CUSTOMERS = pd.DataFrame({"customer_id": ["C1"], "segment": ["retail"], "kyc_risk_rating": ["low"], "account_age_months": [12]})


def test_fast_out_share_counts_money_forwarded_within_two_days():
    tx = _tx([
        ("C1", "2026-01-10", "transfer", "in", 1_000, "P1", "NL"),
        ("C1", "2026-01-11", "transfer", "out", 900, "X1", "XA"),   # forwarded next day
        ("C1", "2026-01-20", "transfer", "in", 1_000, "P2", "NL"),
        ("C1", "2026-01-28", "transfer", "out", 1_000, "X1", "NL"),  # 8 days later: not 'fast'
    ])
    f = build_features(tx, CUSTOMERS)
    assert np.isclose(f.fast_out_share.iat[0], 900 / 2_000)
    assert f.hr_out_sum.iat[0] == 900
    assert f.n_distinct_senders.iat[0] == 2


def test_behavioural_baseline_has_no_look_ahead():
    tx = _tx([
        ("C1", "2026-01-05", "transfer", "in", 1_000, "P1", "NL"),
        ("C1", "2026-02-05", "transfer", "in", 5_000, "P1", "NL"),
    ])
    f = build_features(tx, CUSTOMERS).set_index("month")
    assert f.loc[1, "in_vs_own_history"] == 1.0   # no history yet → neutral, not 'future-informed'
    assert f.loc[2, "in_vs_own_history"] == 5.0   # compared with January only


def test_generator_is_reproducible_and_realistically_rare():
    c1, t1, l1 = generate(seed=7)
    c2, t2, l2 = generate(seed=7)
    pd.testing.assert_frame_equal(t1.head(500), t2.head(500))
    assert 0.002 < l1.is_suspicious.mean() < 0.02
    # bad actors are drawn from ordinary customers, not from the 'noisy' legit profiles
    assert set(c1[c1.true_typology != "none"].behaviour_profile) == {"standard"}


def test_every_option_respects_investigator_capacity():
    rng = np.random.default_rng(0)
    n = 1_000
    df = pd.DataFrame({
        "customer_id": [f"C{i % 500}" for i in range(n)], "month": np.repeat([5, 6], n // 2),
        "rule_alert": rng.random(n) < 0.4, "score": rng.random(n),
        "is_suspicious": (rng.random(n) < 0.05).astype(int),
    })
    res, reviewed = evaluate_options(df, capacity=50, ml_slots=10, fifo_repeats=3)
    assert (res.alerts_reviewed_per_month <= 50).all()
    c = df.loc[reviewed["C"]]
    assert (~c.rule_alert).groupby(c.month).sum().max() <= 10  # ML-only slots are capped


def test_feature_list_is_documented():
    from aml_tm.features import FEATURE_DESCRIPTIONS
    assert all(FEATURE_DESCRIPTIONS[f] for f in FEATURES)
    assert C.TRAIN_MONTHS[-1] < C.TEST_MONTHS[0]  # out-of-time split
