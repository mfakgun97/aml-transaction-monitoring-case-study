"""Rule boundary tests — these mirror acceptance criteria AC-1..AC-4 in docs/02_requirements.md."""

import pandas as pd
import pytest

from aml_tm.rules import apply_rules


def _row(**kw):
    base = dict(customer_id="C1", month=1, cash_dep_max=0.0, cash_dep_near_threshold=0, hr_out_sum=0.0,
                total_in=0.0, fast_out_share=0.0)
    base.update(kw)
    return pd.DataFrame([base])


@pytest.mark.parametrize("amount, fires", [(9_999.99, False), (10_000, True), (25_000, True)])
def test_r1_large_cash_boundary(amount, fires):
    assert bool(apply_rules(_row(cash_dep_max=amount))["R1_large_cash"].iat[0]) == fires


def test_r2_structuring_uses_exact_band_from_transactions():
    f = _row()
    tx = pd.DataFrame({
        "customer_id": ["C1"] * 4,
        "date": pd.to_datetime(["2026-01-03", "2026-01-09", "2026-01-15", "2026-01-20"]),
        "tx_type": ["cash_deposit"] * 4,
        "amount": [8_000, 9_500, 9_999, 10_000],  # 10,000 is outside the band (that's R1's job)
    })
    assert bool(apply_rules(f, tx)["R2_structuring"].iat[0])
    tx.loc[0, "amount"] = 7_999  # drops to 2 deposits in band
    assert not bool(apply_rules(f, tx)["R2_structuring"].iat[0])


@pytest.mark.parametrize("amount, fires", [(4_999, False), (5_000, True)])
def test_r3_high_risk_country_boundary(amount, fires):
    assert bool(apply_rules(_row(hr_out_sum=amount))["R3_high_risk_country"].iat[0]) == fires


@pytest.mark.parametrize("inflow, share, fires", [
    (10_000, 0.80, True), (9_999, 0.95, False), (50_000, 0.79, False),
])
def test_r4_rapid_movement_needs_both_conditions(inflow, share, fires):
    assert bool(apply_rules(_row(total_in=inflow, fast_out_share=share))["R4_rapid_movement"].iat[0]) == fires


def test_rules_fired_is_traceable():
    out = apply_rules(_row(cash_dep_max=12_000, hr_out_sum=6_000))
    assert out["rule_alert"].iat[0]
    assert out["rules_fired"].iat[0] == "R1,R3"
