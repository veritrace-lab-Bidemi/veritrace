# Veritrace

Financial Crime Knowledge Assistant. Veritrace answers BSA/AML questions from approved sources and cites the exact section behind every answer.

Built on AWS with Terraform. Uses public regulatory text and synthetic data only.

## Status

Phase 1: policy Q&A with citations. See the [charter](docs/01-business/charter.md).

## Repository Layout

| Path | Contents | Owner |
|---|---|---|
| `docs/01-business/` | Charter, user stories, test questions | Business Analyst |
| `docs/02-design/` | User flow, wireframes | UX Designer |
| `docs/03-engineering/` | Engineering runbooks and decisions | Software Engineer |
| `docs/04-ml/` | Data, retrieval and model documentation | AI/ML Engineer |
| `infra/` | Terraform for all AWS resources | Software Engineer |
| `backend/` | API service | Software Engineer |
| `frontend/` | Web app | Software Engineer, UX Designer |
| `ml/` | Ingestion, retrieval, agents, evaluation | AI/ML Engineer |

Folders are added when their first task starts. Ownership is enforced by [CODEOWNERS](.github/CODEOWNERS).

## How We Work

Read [CONTRIBUTING.md](CONTRIBUTING.md) before your first change.

## Documents

| Task | Document |
|---|---|
| BA-1 | [Project charter](docs/01-business/charter.md) |
| BA-2 | [User stories](docs/01-business/user-stories.md) |
| UX-1 | [User flow](docs/02-design/user-flow.md) |
| UX-2 | [Wireframes](docs/02-design/wireframes.md) |
| SWE-1 | [Repository setup](docs/03-engineering/swe-1-repo-setup.md) |
| SWE-2 | [AWS foundation](docs/03-engineering/swe-2-aws-foundation.md) |
