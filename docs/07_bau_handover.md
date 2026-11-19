# 07 · Handover to business as usual (BAU)

When the change is live, the translator hands ownership to the people who run it day to day. This document is the contract for that handover.

## 1. What is being handed over
- ML risk score (model version, training period Jan–Apr, seed 42)
- Sorted rule-alert queue (Phase 1) and capped ML scenario (Phase 2, 60 slots/month)
- Lighter-handling lane with QA sampling
- Configuration: `src/aml_tm/config.py` (thresholds, capacity, ML slots)

## 2. Owners after go-live

| Area | Owner | Backup |
|---|---|---|
| Model performance & retraining | Data science lead | Senior data scientist |
| Pipeline running & incidents | DevOps on-call | DevOps lead |
| Queue usage & investigator feedback | Investigations team lead | Senior investigator |
| QA sample of lighter lane | Compliance analyst | Compliance lead |
| Change requests (thresholds, slots) | Product owner | Analytics translator (during transition) |

## 3. What to monitor, and when to act

| Metric | Frequency | Normal range | Action if outside range |
|---|---|---|---|
| Rule alerts per month | Monthly | ±20% of trailing 3-month average | Check data feed; inform product owner |
| ML-scenario precision (from dispositions) | Monthly | ≥ 3× rule precision | Review with data science; consider reducing slots |
| Lighter-lane QA hit rate | Monthly | Below agreed tolerance | **Rollback trigger:** move slots back to rule alerts |
| Score distribution drift (PSI) | Monthly | PSI < 0.2 | Investigate drift; retraining review |
| Alert rate & precision by segment (F-07) | Quarterly | No segment > 2× its share without higher precision | Fairness review with Compliance |

## 4. Recurring rhythm
- **Monthly:** performance & QA review (30 min), owners above
- **Quarterly:** retraining decision; review ML slot number
- **Yearly:** full model re-validation by Model Risk

## 5. Open items at handover
Carried over from the findings log: F-04 (R1 tuning), F-06 (QA tolerance), F-07 (segment monitoring), F-08 (feedback loop). Each has an owner in the findings log.

## 6. Handover sign-off
☐ Receiving owners have read this document and the findings log
☐ Monitoring is live and the first monthly review is scheduled
☐ Translator remains point of contact until: ____ (suggested: one month after go-live)
