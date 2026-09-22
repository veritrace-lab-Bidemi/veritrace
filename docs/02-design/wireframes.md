# Veritrace Phase 1 Wireframes

| Field | Value |
|---|---|
| Task | UX-2 |
| Owner | UX Designer |
| Status | Approved |
| Started | 2026-09-21 |
| Finished | 2026-09-21 |
| Depends on | UX-1 (User Flow) |
| Hands off to | BA-3 (Wireframe Review), SWE-4 (API Contract) |

Design canvas: https://claude.ai/artifact/Db1Vor1wJb7jeqZLTp4AAW

Low fidelity: grayscale, no brand styling. Dashed tags on each screen (for example `US-02`) link elements to user stories.

## Artboards

| Artboard | Shows | Stories |
|---|---|---|
| S1 Sign-in | Email, password, idle timeout notice | US-07 |
| S2 Assistant: empty | Example questions, input with 2,000 character counter, empty history | US-01, US-10 |
| S2 Assistant: answer and source | Cited answer, source list with as-of date and status, feedback, source panel with highlighted passage | US-02, US-03, US-04, US-09 |
| S2 Assistant: other states | Proposed rule cited, out of scope, not covered, validation error | US-01, US-04, US-05, US-06 |
| S3 Audit Log | Filters, read-only log table, entry detail | US-08 |

## Data Each Screen Needs

Input to SWE-4. The API must return these fields.

| Screen element | Fields |
|---|---|
| Answer | answer text, result type (answered, not covered, out of scope), citation markers |
| Citation | number, document name, section, publisher, as-of or published date, status (in force, proposed), source URL |
| Source panel | full passage text, highlighted span used for the answer |
| Feedback | answer ID, rating (helpful, not helpful), optional comment |
| History | conversation ID, title, last updated |
| Audit entry | time, user, question, answer, citations, result type, app version, model ID, feedback |

## Review Checklist for BA-3

- [X] Every Must story appears on at least one artboard
- [X] Every answer state from the user flow is drawn
- [X] Status is shown with text, not color alone
- [X] The legal notice is visible on assistant screens
