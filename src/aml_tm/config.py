"""Central configuration for the case study.

All business parameters (rule thresholds, investigator capacity, cost
assumptions) live here so that a change request can be traced to a single,
reviewable diff — the same way a threshold change would be handled in a
real transaction-monitoring (TM) release.
"""

from pathlib import Path

# --- Paths -----------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
REPORTS_DIR = ROOT / "reports"
FIGURES_DIR = REPORTS_DIR / "figures"

# --- Synthetic data ----------------------------------------------------------
SEED = 42
N_CUSTOMERS = 5_000
START_DATE = "2026-01-01"
N_MONTHS = 6

# Illustrative high-risk jurisdiction codes. In production this list comes
# from FATF publications and the bank's internal country-risk model; codes
# "XA".."XD" are deliberately fictional so the project never goes stale.
HIGH_RISK_COUNTRIES = ["XA", "XB", "XC", "XD"]
LOW_RISK_COUNTRIES = ["NL", "DE", "BE", "FR", "ES", "PL", "GB", "TR"]

# --- Baseline rule thresholds (current production "scenarios") ---------------
RULES = {
    "R1_large_cash": {"min_cash_deposit": 10_000},
    "R2_structuring": {"band_low": 8_000, "band_high": 10_000, "min_count": 3},
    "R3_high_risk_country": {"min_amount_out": 5_000},
    "R4_rapid_movement": {"min_inflow": 10_000, "min_fast_out_share": 0.80},
}

# --- Model ------------------------------------------------------------------
TRAIN_MONTHS = [1, 2, 3, 4]   # Jan–Apr: model development
TEST_MONTHS = [5, 6]          # May–Jun: out-of-time validation

# --- Operational assumptions (used in the decision proposal) -----------------
INVESTIGATOR_CAPACITY_PER_MONTH = 200  # alerts the L1 team can review per month
MINUTES_PER_ALERT = 45                 # average L1 handling time
ML_SCENARIO_SLOTS = 60                 # option C: monthly review slots for ML-only alerts
