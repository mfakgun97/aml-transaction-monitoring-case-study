# 06 · Stakeholders & RACI

## Who cares about what

| Stakeholder | Main question | What they need from the translator |
|---|---|---|
| **Investigators (L1/L2)** | "Will this make my queue better or just different?" | Clear reason codes, a short briefing, a say in UAT |
| **AML subject-matter experts** | "Does the model reflect real typologies?" | Feature list in plain language; typology-level results |
| **Data scientists** | "What exactly should the model optimise, and what counts as done?" | A decision metric (detection within capacity), not just AUC; clear requirements |
| **DevOps engineers** | "What changes in the pipeline and how do we roll back?" | Functional requirements, config-driven parameters, rollback plan |
| **Product owner** | "What value, what risk, what does it cost?" | Options with trade-offs; phased plan |
| **Compliance (2nd line)** | "Do we stay compliant and in control?" | Rules kept as a safety net; QA design; audit trail |
| **Model Risk Management** | "Is the model sound and validated?" | Out-of-time validation, CIs, findings log |

## RACI for the model change

R = Responsible · A = Accountable · C = Consulted · I = Informed

| Activity | Translator | Data science | DevOps | AML SME | Investigations | Product owner | Compliance | Model Risk |
|---|---|---|---|---|---|---|---|---|
| Problem framing & KPIs | **R** | C | I | C | C | **A** | C | I |
| Requirements | **R** | C | C | C | C | **A** | C | I |
| Model development | C | **R/A** | I | C | I | I | I | I |
| Decision proposal | **R** | C | I | C | C | **A** | C | C |
| Model validation | I | C | I | C | I | I | I | **R/A** |
| Release & sign-off | **R** (coordination) | C | **R** (deploy) | I | C | **A** | C | C |
| Findings management | **R** | R (own findings) | R (own findings) | I | I | **A** | I | C |
| BAU handover | **R** | C | C | I | C | **A** | I | I |
