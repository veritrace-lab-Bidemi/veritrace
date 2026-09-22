# Contributing to Veritrace

This is the team's working agreement. It applies to every role.

## Roles

| Role | GitHub team | Task prefix |
|---|---|---|
| Business Analyst | `business-analysts` | BA |
| UX Designer | `ux-designers` | UX |
| Software Engineer | `software-engineers` | SWE |
| AI/ML Engineer | `ml-engineers` | ML |

## Task Lifecycle

Every task moves through three recorded points.

| Point | What you do |
|---|---|
| Start | Create a branch for the task. Set "Started" in the doc header and the task tracker. |
| Finish | Open a pull request. Set "Status" to `Approved` and "Finished" in the doc header. |
| Sync | Merge the pull request. Note the handoff in the PR. Mark "Synced" in the tracker once the next role confirms. |

## Branches

- `main` is protected. All changes go through a pull request.
- Branch name: `<role>/<task-id>-<short-description>`, all lowercase.
- Examples: `swe/swe-2-aws-foundation`, `ml/ml-1-data-spikes`, `ba/ba-4-test-cases`.
- One task per branch. Delete the branch after merge (GitHub does this automatically).

## Commits

- Format: `<type>(<role>): <summary>`, for example `feat(ml): add section-aware chunker`.
- Types: `feat`, `fix`, `docs`, `refactor`, `test`, `ci`, `build`, `chore`.
- Every commit must be signed. Unsigned commits cannot reach `main`.

## Pull Requests

- Fill in the template, including the task ID.
- Squash merge only. The PR title becomes the commit on `main`, so use the commit format above.
- Resolve all review comments before merging.
- Infrastructure changes must include `terraform plan` output and a console check of what was created.

## Security Rules

- Never commit secrets, keys, tokens or passwords. pre-commit and GitHub push protection block most of them, but you are still responsible.
- Never use long-lived AWS access keys. Use AWS IAM Identity Center locally and OIDC in CI.
- Never commit real customer, transaction, SAR or bank data. Public and synthetic data only.
- Raw data lives in S3, not in Git.

## Local Setup

1. Install the tools: `brew install git gh pre-commit gitleaks`
2. Install the hooks in your clone: `pre-commit install`
3. Check everything passes: `pre-commit run --all-files`
