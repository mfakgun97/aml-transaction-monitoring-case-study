"""Synthetic retail/SME banking transactions with injected AML typologies.

Why synthetic? Real transaction-monitoring data is (rightly) never public.
Generating it lets us control ground truth and — more importantly for this
case study — deliberately include the *legitimate* behaviour that makes
rule-based monitoring noisy:

* cash-intensive SMEs (restaurants, shops) that deposit large amounts of cash
* customers who send remittances to family in higher-risk jurisdictions
* "marketplace sellers" who receive many small payments from strangers
* "savings sweepers" who move most of their salary to another own account within a day or two
* import/export SMEs that legitimately pay suppliers in higher-risk jurisdictions

Suspicious typologies injected (one per suspicious customer, active for 1–3
months):

* structuring   – repeated cash deposits just below the €10k reporting line
* money_mule    – many small inbound transfers, forwarded within ~2 days
* high_risk_layering – round-amount transfers to high-risk jurisdictions

Outputs (written to data/):
    customers.csv     one row per customer, incl. ground-truth typology
    transactions.csv  one row per transaction
    labels.csv        customer-month ground truth (1 = suspicious activity)
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import config as C

TX_COLUMNS = [
    "customer_id", "date", "tx_type", "direction", "amount",
    "counterparty_id", "counterparty_country",
]


class _Writer:
    """Collects transactions in plain lists (much faster than appending to a DataFrame)."""

    def __init__(self) -> None:
        self.rows: list[tuple] = []

    def add(self, cid, day, tx_type, direction, amount, cp_id, cp_country):
        self.rows.append((cid, int(day), tx_type, direction, round(float(amount), 2), cp_id, cp_country))


def _month_bounds(n_months: int) -> list[tuple[int, int]]:
    start = pd.Timestamp(C.START_DATE)
    bounds = []
    for m in range(n_months):
        a = pd.Timestamp(start) + pd.DateOffset(months=m)
        b = a + pd.DateOffset(months=1)
        bounds.append(((a - start).days, (b - start).days))  # [a, b)
    return bounds


def _customers(rng: np.random.Generator) -> pd.DataFrame:
    n = C.N_CUSTOMERS
    cid = np.array([f"C{i:05d}" for i in range(n)])
    segment = rng.choice(["retail", "sme"], size=n, p=[0.8, 0.2])

    # Legitimate-but-noisy behaviour profiles
    profile = np.full(n, "standard", dtype=object)
    sme_idx = np.where(segment == "sme")[0]
    retail_idx = np.where(segment == "retail")[0]
    sme_noisy = rng.choice(sme_idx, size=int(0.40 * len(sme_idx)), replace=False)
    profile[sme_noisy[: int(0.75 * len(sme_noisy))]] = "cash_intensive_business"
    profile[sme_noisy[int(0.75 * len(sme_noisy)):]] = "import_export"
    r_noisy = rng.choice(retail_idx, size=int(0.18 * len(retail_idx)), replace=False)
    third = len(r_noisy) // 3
    profile[r_noisy[:third]] = "remitter"
    profile[r_noisy[third: 2 * third]] = "marketplace_seller"
    profile[r_noisy[2 * third:]] = "savings_sweeper"

    # Suspicious customers (~2%), drawn from 'standard' profiles so that
    # the bad actors look like ordinary customers in their KYC data.
    standard = np.where(profile == "standard")[0]
    susp_idx = rng.choice(standard, size=int(0.02 * n), replace=False)
    typology = np.full(n, "none", dtype=object)
    typology[susp_idx] = rng.choice(
        ["structuring", "money_mule", "high_risk_layering"], size=len(susp_idx), p=[0.3, 0.45, 0.25]
    )

    # KYC risk rating: imperfect — only partly correlated with true risk
    risk = rng.choice(["low", "medium", "high"], size=n, p=[0.70, 0.25, 0.05])
    flip = rng.random(n) < 0.25
    risk[susp_idx[flip[susp_idx]]] = "high"
    risk[profile == "remitter"] = rng.choice(["medium", "high"], size=(profile == "remitter").sum(), p=[0.7, 0.3])

    start_month = np.zeros(n, dtype=int)
    duration = np.zeros(n, dtype=int)
    start_month[susp_idx] = rng.integers(1, C.N_MONTHS + 1, size=len(susp_idx))
    duration[susp_idx] = rng.integers(1, 4, size=len(susp_idx))
    duration = np.minimum(duration, C.N_MONTHS - start_month + 1) * (start_month > 0)

    return pd.DataFrame({
        "customer_id": cid,
        "segment": segment,
        "behaviour_profile": profile,
        "kyc_risk_rating": risk,
        "account_age_months": rng.integers(1, 240, size=n),
        "true_typology": typology,
        "susp_start_month": start_month,
        "susp_duration_months": duration,
    })


def _normal_month(w: _Writer, rng, cust, lo, hi):
    cid, seg, prof = cust.customer_id, cust.segment, cust.behaviour_profile
    days = lambda k: rng.integers(lo, hi, size=k)  # noqa: E731

    if seg == "retail":
        w.add(cid, lo + rng.integers(20, 27), "salary", "in", max(1500.0, rng.normal(3200, 900)), f"EMP{int(cid[1:]) % 900:03d}", "NL")
        for d in days(rng.poisson(14)):
            w.add(cid, d, "card_payment", "out", rng.lognormal(3.3, 0.9), "MERCHANT", "NL")
        for d in days(rng.poisson(1.5)):
            w.add(cid, d, "cash_withdrawal", "out", rng.choice([50, 100, 200, 300]), "ATM", "NL")
        for d in days(rng.poisson(2)):
            w.add(cid, d, "transfer", "out", rng.lognormal(5.0, 0.8), f"P{rng.integers(1e6):06d}", rng.choice(C.LOW_RISK_COUNTRIES, p=[.86, .03, .03, .02, .02, .01, .02, .01]))
        for d in days(rng.poisson(1)):
            w.add(cid, d, "transfer", "in", rng.lognormal(4.5, 0.9), f"P{rng.integers(1e6):06d}", "NL")
        if rng.random() < 0.03:  # occasional legit large inbound (car sale, inheritance)
            w.add(cid, days(1)[0], "transfer", "in", rng.uniform(8_000, 30_000), f"P{rng.integers(1e6):06d}", "NL")
    else:  # SME
        for d in days(rng.poisson(25)):
            w.add(cid, d, "transfer", "in", rng.lognormal(6.3, 1.0), f"B{rng.integers(1e6):06d}", rng.choice(["NL", "DE", "BE"], p=[.8, .1, .1]))
        for d in days(rng.poisson(12)):
            w.add(cid, d, "transfer", "out", rng.lognormal(6.8, 1.0), f"S{rng.integers(1e5):05d}", rng.choice(["NL", "DE", "BE", "PL"], p=[.7, .12, .1, .08]))
        if rng.random() < 0.15:
            w.add(cid, days(1)[0], "cash_deposit", "in", rng.uniform(1_000, 6_000), "BRANCH", "NL")

    # Legitimate-but-noisy profiles ------------------------------------------
    if prof == "cash_intensive_business":
        for d in days(rng.integers(3, 9)):
            w.add(cid, d, "cash_deposit", "in", rng.lognormal(8.6, 0.45), "BRANCH", "NL")  # median ~€5.4k, tail >€10k
        if rng.random() < 0.08:  # a slow month followed by a big weekend: several deposits in the €8–10k band
            for d in days(3):
                w.add(cid, d, "cash_deposit", "in", rng.uniform(8_000, 9_950), "BRANCH", "NL")
    elif prof == "remitter":
        for d in days(rng.integers(1, 4)):
            w.add(cid, d, "transfer", "out", rng.uniform(300, 2_500), f"FAM{int(cid[1:]) % 9999:04d}", rng.choice(C.HIGH_RISK_COUNTRIES))
        if rng.random() < 0.2:  # e.g. family emergency / house purchase abroad
            w.add(cid, days(1)[0], "transfer", "out", rng.uniform(5_000, 15_000), f"FAM{int(cid[1:]) % 9999:04d}", rng.choice(C.HIGH_RISK_COUNTRIES))
    elif prof == "savings_sweeper":
        sal_day = lo + 22
        w.add(cid, sal_day + rng.integers(0, 3), "transfer", "out", rng.uniform(1_500, 3_500), "OWN_ACCOUNT_OTHER_BANK", "NL")
        if rng.random() < 0.15:  # bonus / tax refund swept on
            amt = rng.uniform(5_000, 20_000)
            d = rng.integers(lo, hi - 2)
            w.add(cid, d, "transfer", "in", amt, f"P{rng.integers(1e6):06d}", "NL")
            w.add(cid, d + 1, "transfer", "out", amt * rng.uniform(0.9, 1.0), "OWN_ACCOUNT_OTHER_BANK", "NL")
    elif prof == "import_export":
        for d in days(rng.integers(1, 5)):
            w.add(cid, d, "transfer", "out", rng.lognormal(8.7, 0.7), f"SUP{int(cid[1:]) % 997:03d}", rng.choice(C.HIGH_RISK_COUNTRIES))
    elif prof == "marketplace_seller":
        for d in days(rng.integers(8, 30)):
            w.add(cid, d, "transfer", "in", rng.uniform(15, 400), f"P{rng.integers(1e6):06d}", "NL")
        if rng.random() < 0.5:
            w.add(cid, hi - 2, "transfer", "out", rng.uniform(500, 3_000), "OWN_SAVINGS", "NL")


def _suspicious_month(w: _Writer, rng, cust, lo, hi):
    cid, typ = cust.customer_id, cust.true_typology
    small = rng.random() < 0.6  # most actors deliberately keep amounts small
    if rng.random() < 0.2:      # some months the actor is barely active (weak, realistic signal)
        typ = {"structuring": "quiet_cash", "money_mule": "quiet_mule", "high_risk_layering": "quiet_layer"}[typ]

    if typ == "structuring":
        n_dep = rng.integers(3, 8) if not small else rng.integers(2, 4)
        band = (8_200, 9_950) if not small else (4_000, 7_900)
        dep_days = np.sort(rng.integers(lo, hi - 3, size=n_dep))
        total = 0.0
        for d in dep_days:
            amt = rng.uniform(*band)
            total += amt
            w.add(cid, d, "cash_deposit", "in", amt, "BRANCH", "NL")
        w.add(cid, dep_days[-1] + rng.integers(1, 3), "transfer", "out", total * rng.uniform(0.7, 0.95), f"X{rng.integers(1e5):05d}", rng.choice(C.LOW_RISK_COUNTRIES + C.HIGH_RISK_COUNTRIES))

    elif typ == "money_mule":
        n_in = rng.integers(3, 15)
        amt_range = (300, 2_500) if not small else (100, 700)
        receivers = [f"X{rng.integers(1e5):05d}" for _ in range(rng.integers(1, 3))]
        for d in rng.integers(lo, hi - 2, size=n_in):
            amt = rng.uniform(*amt_range)
            w.add(cid, d, "transfer", "in", amt, f"P{rng.integers(1e6):06d}", "NL")
            fwd_day = min(d + rng.integers(0, 3), hi - 1)
            w.add(cid, fwd_day, "transfer", "out", amt * rng.uniform(0.85, 0.98), rng.choice(receivers),
                  rng.choice(C.HIGH_RISK_COUNTRIES + ["NL", "DE", "ES"], p=[.15, .15, .1, .1, .2, .15, .15]))

    elif typ == "high_risk_layering":
        n_out = rng.integers(2, 6)
        unit = 1_000 if not small else 500
        for d in rng.integers(lo, hi, size=n_out):
            amt = unit * rng.integers(5 if not small else 3, 25 if not small else 9)  # often round amounts
            if rng.random() < 0.4:
                amt *= rng.uniform(0.93, 0.99)
            w.add(cid, max(d - rng.integers(1, 4), lo), "transfer", "in", amt * rng.uniform(1.0, 1.05), f"B{rng.integers(1e6):06d}", rng.choice(["DE", "BE", "GB"]))
            w.add(cid, d, "transfer", "out", amt, f"X{rng.integers(1e5):05d}", rng.choice(C.HIGH_RISK_COUNTRIES))

    elif typ == "quiet_cash":
        w.add(cid, rng.integers(lo, hi), "cash_deposit", "in", rng.uniform(2_000, 6_000), "BRANCH", "NL")
    elif typ == "quiet_mule":
        for d in rng.integers(lo, hi - 2, size=2):
            amt = rng.uniform(150, 600)
            w.add(cid, d, "transfer", "in", amt, f"P{rng.integers(1e6):06d}", "NL")
            w.add(cid, d + 1, "transfer", "out", amt * 0.9, f"X{rng.integers(1e5):05d}", "NL")
    elif typ == "quiet_layer":
        amt = rng.uniform(1_500, 4_000)
        d = rng.integers(lo + 2, hi)
        w.add(cid, d - 2, "transfer", "in", amt, f"B{rng.integers(1e6):06d}", "DE")
        w.add(cid, d, "transfer", "out", amt * 0.97, f"X{rng.integers(1e5):05d}", rng.choice(C.HIGH_RISK_COUNTRIES))


def generate(seed: int = C.SEED) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(seed)
    customers = _customers(rng)
    bounds = _month_bounds(C.N_MONTHS)
    w = _Writer()
    label_rows = []

    for cust in customers.itertuples(index=False):
        for m, (lo, hi) in enumerate(bounds, start=1):
            _normal_month(w, rng, cust, lo, hi)
            active = cust.susp_start_month > 0 and cust.susp_start_month <= m < cust.susp_start_month + cust.susp_duration_months
            if active:
                _suspicious_month(w, rng, cust, lo, hi)
            label_rows.append((cust.customer_id, m, int(active), cust.true_typology if active else "none"))

    tx = pd.DataFrame(w.rows, columns=TX_COLUMNS)
    tx["date"] = pd.Timestamp(C.START_DATE) + pd.to_timedelta(tx["date"].clip(upper=bounds[-1][1] - 1), unit="D")
    tx = tx.sort_values(["customer_id", "date"]).reset_index(drop=True)
    tx.insert(0, "tx_id", [f"T{i:08d}" for i in range(len(tx))])
    labels = pd.DataFrame(label_rows, columns=["customer_id", "month", "is_suspicious", "typology"])
    return customers, tx, labels


def main() -> None:
    C.DATA_DIR.mkdir(parents=True, exist_ok=True)
    customers, tx, labels = generate()
    customers.to_csv(C.DATA_DIR / "customers.csv", index=False)
    tx.to_csv(C.DATA_DIR / "transactions.csv", index=False)
    labels.to_csv(C.DATA_DIR / "labels.csv", index=False)
    print(f"customers: {len(customers):,} | transactions: {len(tx):,} | "
          f"suspicious customer-months: {labels.is_suspicious.sum():,} "
          f"({labels.is_suspicious.mean():.2%})")


if __name__ == "__main__":
    main()
