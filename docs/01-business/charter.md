# Veritrace Project Charter

| Field | Value |
|---|---|
| Task | BA-1 |
| Owner | Business Analyst |
| Status | Started |
| Started | 2026-09-21 |
| Finished | YYYY-MM-DD |
| Hands off to | BA-2 (User Stories) |

## 1. Problem

AML investigators spend a large part of each case looking up regulations, FinCEN guidance and internal policy, then writing up their findings. The sources are spread across many documents, change over time, and must be cited exactly. Slow lookups delay SAR decisions and lead to inconsistent case write-ups.

## 2. Goal

Build Veritrace, an assistant that answers financial crime questions from approved sources and cites the exact section behind every answer.

Phase 1 goal: an investigator asks a BSA/AML policy question and gets a correct, cited answer they can verify in one click.

## 3. Users

| Persona | Needs | Phase 1 access |
|---|---|---|
| AML Investigator (primary) | Fast, cited answers while working a case | Ask questions, view sources |
| Investigations Team Lead | Consistent answers across the team | Same as investigator |
| BSA Officer / Compliance | Trust in answer quality and a full audit trail | Read audit log |

## 4. Scope

### Phase 1 (in scope)

- Question and answer on BSA/AML regulations and FinCEN guidance
- Citation to document and section for every answer
- View the cited source text
- Show each source's as-of date and status (in force or proposed)
- Sign-in and audit log of every question and answer

### Out of scope for Phase 1

- OFAC sanctions screening (Phase 2)
- Alerts, transactions and customer data (Phase 2)
- Similar historical cases (Phase 2)
- Investigation summaries and SAR narrative drafts (Phase 2)
- Any real customer, SAR or bank data (never in scope)
- Legal advice

## 5. Phase 1 Knowledge Sources

| Source | Publisher | Status |
|---|---|---|
| 31 CFR Chapter X, Parts 1010 and 1020 | eCFR | In force |
| BSA/AML Examination Manual | FFIEC | In force |
| SAR FAQs (October 9, 2025) | FinCEN | In force |
| Selected advisories and alerts | FinCEN | In force |
| AML/CFT Programs NPRM (FR Doc. 2026-07033, April 10, 2026) | FinCEN | Proposed |

Proposed rules are included so users can ask about them, but answers must label them as proposed.

## 6. Success Measures (Phase 1 targets)

| Measure | Target |
|---|---|
| Answers with at least one valid citation | 100% |
| Citation accuracy on the evaluation question set | 95% or higher |
| Correct "not covered" response when no source supports an answer | 100% on test set |
| Response time (95th percentile) | Under 10 seconds |
| UAT pass rate on Phase 1 stories | All Must stories pass |

## 7. Constraints

- Public or synthetic data only
- Personal AWS account, built to enterprise standards
- All infrastructure in Terraform so it can be torn down and rebuilt
- Cost kept low: services shut down when not in use

## 8. Risks

| Risk | Mitigation |
|---|---|
| Regulations change (for example the 2026 program rule proposal) | Store as-of date and status per source; show both in answers |
| Model cites a section that does not support the answer | Automated citation check before any answer is returned |
| Users treat answers as legal advice | Standing notice in the UI; answers point to the source |
| AWS costs grow while idle | Budget alarms and one-command teardown |

## 9. Team

| Role | Owns |
|---|---|
| Business Analyst | Scope, stories, acceptance criteria, UAT |
| UX Designer | User flow, wireframes, UI design |
| Software Engineer | Repo, AWS foundation, CI/CD, API, frontend |
| AI/ML Engineer | Data pipeline, retrieval, agents, evaluation |

## 10. Sign-off

| Role | Approved | Date |
|---|---|---|
| Business Analyst |Yes |2026-09-21 |
| AI/ML Engineer | | |
| Software Engineer | | |
