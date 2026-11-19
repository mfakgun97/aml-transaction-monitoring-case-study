# 04 · Release sign-off checklist: Phase 1 (ML prioritisation of rule alerts)

A release only goes live when **every line has an owner's sign-off**. Items that are not applicable are marked N/A with a reason, never left blank.

## A. Business & compliance
| # | Check | Owner | Status |
|---|---|---|---|
| A1 | Decision D-1 approved and recorded | Product owner | ☐ |
| A2 | Change does not alter which alerts are *generated* (only their order) | Compliance | ☐ |
| A3 | Investigators briefed on the new sort order and the meaning of the score | Investigations lead | ☐ |
| A4 | Rollback plan agreed (restore FIFO ordering) | Product owner | ☐ |

## B. Model
| # | Check | Owner | Status |
|---|---|---|---|
| B1 | Model validation report available; no open **high** findings | Model Risk | ☐ |
| B2 | Out-of-time performance reported with confidence intervals | Data science | ☐ |
| B3 | Feature list and descriptions reviewed by an AML SME (NFR-2) | AML expert | ☐ |
| B4 | No look-ahead features (NFR-3) confirmed by test | Data science | ☐ `test_behavioural_baseline_has_no_look_ahead` |
| B5 | Model version, training data period and seed recorded | Data science | ☐ |

## C. Technical
| # | Check | Owner | Status |
|---|---|---|---|
| C1 | Rule boundary tests pass (FR-1) | DevOps | ☐ `tests/test_rules.py` |
| C2 | Full test suite green in CI | DevOps | ☐ |
| C3 | Score populated for 100% of customer-months in acceptance run (FR-2) | DevOps | ☐ |
| C4 | Queue ordering verified in the case-management tool (FR-3) | DevOps + Investigations | ☐ |
| C5 | Monitoring dashboard for score distribution and alert volumes live | DevOps | ☐ |

## D. Documentation & handover
| # | Check | Owner | Status |
|---|---|---|---|
| D1 | Findings log updated; all findings have an owner and a due date | Analytics translator | ☐ |
| D2 | BAU handover document reviewed by the receiving owner | Analytics translator | ☐ |
| D3 | Release notes written in non-technical language | Analytics translator | ☐ |

**Go / No-go:** ☐ Go  ☐ No-go. Signed: Product owner ______  Compliance ______  Model Risk ______
