# 05 · Findings log

Findings found while building and reviewing this model change, managed like model-validation findings: each has a severity, an owner, an action plan and a status. Several were found **and fixed** during development; they stay in the log because the history is part of the audit trail.

| ID | Finding | Severity | Owner | Action plan | Status |
|---|---|---|---|---|---|
| **F-01** | First model version reached PR-AUC 0.98, which is unrealistically high. Root cause: suspicious behaviour in the synthetic data was too easy to separate (no legitimate look-alikes). | High | Data science | Added legitimate look-alike profiles (savings sweepers, import/export SMEs) and quieter criminal behaviour; re-validated. PR-AUC now 0.84; real-data expectation is lower still. | ✅ Closed |
| **F-02** | Class re-weighting saturated the top scores (many alerts tied at ~0.99), making the ranking arbitrary exactly where investigators start working. | Medium | Data science | Removed re-weighting for the ranking model; verified spread of top-200 scores. | ✅ Closed |
| **F-03** | Reason codes showed "Total cash deposited = EUR 0 (top 8%)": percentile ranking treated tied zero values as high. | Medium | Data science | Percentile now = share of customer-months with a value ≥ this value. Re-checked sample alerts. | ✅ Closed |
| **F-04** | Rule R1 (cash ≥ €10k) produced ~104 alerts/month with **zero** true positives; all false positives are cash-intensive businesses. | Medium | Product owner + AML SME | Out of scope for this release. Propose a separate rule-tuning change (e.g., segment-specific thresholds or peer-group comparison). | 🔶 Open, follow-up |
| **F-05** | Validation set contains only 59 suspicious customer-months; point estimates are uncertain. | Medium | Data science | Report 95% bootstrap CIs (NFR-6); require a 3-month parallel run before Phase 2. | 🔶 Mitigated |
| **F-06** | Lower-ranked rule alerts under option C would not receive full review. No true positives among them in validation, but evidence is limited. | High | Compliance | Lighter-handling lane with ≥ 10% QA sample and a rollback trigger (decision D-3). | 🔶 Open, awaiting decision |
| **F-07** | `is_sme` is among the top model drivers. Segment is a legitimate risk factor, but it must not become a proxy that over-alerts on SMEs as a group. | Low | Data science + Compliance | Monitor alert rate and precision by segment during the parallel run. | 🔶 Open |
| **F-08** | Ground truth is synthetic. Real labels (investigation outcomes, reports to FIU) are noisier and delayed. | Info | Product owner | Define the feedback loop (Q3 in requirements) so the model can be retrained on real dispositions. | 🔶 Open |

### Severity scale
- **High:** could lead to missed suspicious activity or a wrong decision; must be closed before go-live
- **Medium:** affects quality or efficiency; must have an action plan before go-live
- **Low / Info:** monitor; no go-live blocker
