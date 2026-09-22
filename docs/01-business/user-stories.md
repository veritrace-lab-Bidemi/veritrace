# Veritrace Phase 1 User Stories

| Field | Value |
|---|---|
| Task | BA-2 |
| Owner | Business Analyst |
| Status | Approved |
| Started | 2026-09-21 |
| Finished | 2026-09-21 |
| Depends on | BA-1 (Charter) |
| Hands off to | UX-1 (User Flow), ML-4 (Evaluation Set), BA-4 (Test Cases) |

Priority uses MoSCoW: Must, Should, Could.

## Stories

### US-01 Ask a policy question (Must)

As an AML investigator, I want to ask a BSA/AML question in plain English so that I get an answer without searching documents myself.

- Given I am signed in, when I submit a question, then I receive an answer in the same screen.
- Given I ask a follow-up question, when it refers to my earlier question, then the answer uses that context.
- Given my question is empty or over 2,000 characters, when I submit, then I see a clear validation message.

### US-02 Every answer is cited (Must)

As an investigator, I want every answer to cite its sources so that I can rely on it in a case file.

- Given an answer is returned, then it includes at least one citation.
- Each citation shows the document name, section number (for example 31 CFR 1020.320(b)(3)) and a link to the source.
- Each factual statement in the answer is linked to the citation that supports it.

### US-03 View the cited source (Must)

As an investigator, I want to open the cited text so that I can verify the answer myself.

- Given an answer with citations, when I select a citation, then the source passage opens beside the answer.
- The passage shown is the exact text used to produce the answer.

### US-04 Know if a source is current (Must)

As a BSA officer, I want to see each source's date and status so that no one relies on outdated or proposed rules by mistake.

- Each citation shows the source's as-of date.
- Given a cited source is a proposed rule, then the answer states clearly that it is proposed and not yet in force.

### US-05 Say when the answer is not known (Must)

As an investigator, I want the assistant to tell me when it has no supporting source so that I am never given an unsupported answer.

- Given no approved source supports an answer, then the response says the topic is not covered and gives no answer.
- The response never contains a citation that does not support its statement.

### US-06 Handle out-of-scope requests (Must)

As a BSA officer, I want out-of-scope requests declined so that the tool stays within its approved use.

- Given a request for sanctions screening, customer data or case data, then the response says this is not available in the current release.
- Given a request for legal advice, then the response points to the relevant source and states it is not legal advice.

### US-07 Secure sign-in (Must)

As a BSA officer, I want only authorized users to access the tool so that usage is controlled.

- Given I am not signed in, when I open the app, then I am sent to sign-in.
- Given my session is idle for 30 minutes, then I must sign in again.

### US-08 Audit trail (Must)

As a BSA officer, I want every question and answer logged so that I can review how the tool is used.

- Each log entry records user, time, question, answer, citations and model version.
- Users cannot edit or delete log entries.

### US-09 Answer feedback (Should)

As an investigator, I want to rate an answer so that the team can improve answer quality.

- Given an answer, I can mark it helpful or not helpful and add an optional comment.
- Feedback is stored with the audit log entry for that answer.

### US-10 Conversation history (Could)

As an investigator, I want to reopen past conversations so that I can pick up where I left off.

- Given I have past conversations, I can see and reopen them from a list.

## Evaluation Seed Questions

Verified against eCFR (up to date as of September 17, 2026) and FinCEN publications. ML-4 expands this into the full evaluation set. BA-4 reuses it for test cases.

| # | Question | Expected answer | Expected source |
|---|---|---|---|
| Q01 | How long does a bank have to file a SAR after detecting suspicious activity? | 30 calendar days from initial detection. If no suspect is identified, up to 30 more days to identify one, but never more than 60 days. | 31 CFR 1020.320(b)(3) |
| Q02 | What dollar amount triggers a bank's SAR requirement? | A transaction that involves or aggregates at least $5,000 in funds or other assets. | 31 CFR 1020.320(a)(2) |
| Q03 | How long must a bank keep a SAR and its supporting documents? | Five years from the date of filing. | 31 CFR 1020.320(d) |
| Q04 | When must a bank file a Currency Transaction Report? | For a transaction in currency of more than $10,000. | 31 CFR 1010.311 |
| Q05 | Are several cash deposits by one person on the same day added together for CTR purposes? | Yes, when the bank knows they are by or on behalf of the same person and total more than $10,000 in one business day. | 31 CFR 1010.313(b) |
| Q06 | Is structuring prohibited? | Yes. No person may structure, or help structure, transactions to evade currency reporting requirements. | 31 CFR 1010.314; definition at 31 CFR 1010.100(xx) |
| Q07 | What must a bank's AML program include? | Internal controls, independent testing, a designated compliance person, training, and risk-based customer due diligence. | 31 CFR 1020.210 |
| Q08 | What is the travel rule threshold for funds transfers? | $3,000 or more. | 31 CFR 1010.410(f) |
| Q09 | Must a bank file a SAR for a cash transaction just over $10,000 with no sign of evasion? | No. Being at or near the CTR threshold alone does not require a SAR without knowledge, suspicion or reason to suspect the transaction is designed to evade reporting. | FinCEN SAR FAQs, October 9, 2025, Question 1 |
| Q10 | Must a bank document a decision not to file a SAR? | Not required by rule. Brief documentation under internal policy may be appropriate. | FinCEN SAR FAQs, October 9, 2025, Question 4 |
| Q11 | Is FinCEN's 2026 AML/CFT program rule in effect? | Must state it is a proposed rule (published April 10, 2026) and give the source date. | FR Doc. 2026-07033 |
| Q12 | Is John Smith on the OFAC SDN list? | Must decline: sanctions screening is not in Phase 1. | None (US-06) |
| Q13 | What is the SAR filing deadline in Nigeria? | Must say the topic is not covered by approved sources. | None (US-05) |

## Handoff

| To | What they receive | What they do next |
|---|---|---|
| UX Designer | US-01 to US-10 | UX-1 user flow and UX-2 wireframes |
| AI/ML Engineer | Stories and seed questions | ML-4 evaluation set, ML-5 agent behavior |
| Software Engineer | US-07, US-08 | Auth and audit design in SWE-4 and SWE-5 |

Definition of done for BA-2: every Must story has acceptance criteria, seed questions are verified, and the UX Designer confirms the stories are clear enough to start UX-1.
