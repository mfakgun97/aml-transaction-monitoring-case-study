# 02 · Requirements for the model change

Written so that **data scientists, DevOps engineers and AML experts** can each read their own part. Every acceptance criterion points to evidence (a test, a metric or a sign-off).

## Functional requirements

| ID | Requirement | Owner | Acceptance criterion | Evidence |
|---|---|---|---|---|
| FR-1 | Existing rules R1–R4 keep firing exactly as today | DevOps | Rule outputs identical before/after release on the same data | `tests/test_rules.py` (boundary tests) |
| FR-2 | Each customer-month receives a risk score between 0 and 1 | Data science | Score present for 100% of customer-months, no nulls | Pipeline run log |
| FR-3 | Rule alerts are presented to investigators **sorted by risk score** | DevOps + Investigations | Queue order = descending score; ties broken by alert date | UAT script |
| FR-4 | A new "ML scenario" adds up to **60** non-rule alerts per month | Data science | Monthly ML-only alerts ≤ 60 | `tests/test_features_and_options.py::test_every_option_respects_investigator_capacity` |
| FR-5 | Every ML-scenario alert carries **3 reason codes** in plain language with real values | Data science | 100% of ML alerts have 3 non-empty reason codes | `reports/sample_ml_alerts_with_reason_codes.csv` |
| FR-6 | Rule alerts not reviewed in full are **not deleted**: they go to a documented lighter-handling lane | Investigations + Compliance | Lane definition approved; QA sample ≥ 10% | Decision D-3 in decision proposal |

## Non-functional requirements

| ID | Requirement | Why |
|---|---|---|
| NFR-1 | **Out-of-time validation**: train on earlier months, validate on later months | A random split overstates performance (finding F-01) |
| NFR-2 | Every model feature can be explained to an investigator in one sentence | Explainability for investigators, model validation and the regulator |
| NFR-3 | No feature uses information from the future (e.g., behavioural baseline uses *previous* months only) | Must be computable on day 1 of the month in production |
| NFR-4 | Thresholds, capacity and slot numbers live in **one config file** | Every change is a reviewable diff for release sign-off |
| NFR-5 | Results are reproducible from a fixed random seed | Audit trail |
| NFR-6 | Performance reported with **uncertainty** (95% bootstrap CI) | Only 59 positive cases in validation; point estimates alone would mislead |

## Out of scope for this release
- Changing R1–R4 thresholds (logged as F-04)
- Automated closure of alerts without human review
- Real-time (per-transaction) scoring

## Open questions (to resolve before build is "done")

| # | Question | To | Status |
|---|---|---|---|
| Q1 | Is a 60/140 split of capacity between ML and rule alerts acceptable to Compliance? | Compliance | Open, see decision D-2 |
| Q2 | What QA sample size is required for the lighter-handling lane? | 2nd line / Model Risk | Open, see decision D-3 |
| Q3 | How do investigators record the outcome of ML alerts so we can retrain on it? | Investigations + Data science | Proposed: reuse existing disposition codes |
| Q4 | Retraining frequency and drift monitoring owner after go-live? | Product owner | Proposed in BAU handover |
