variable "project" {
  description = "Project name, used as a prefix for resource names"
  type        = string
  default     = "veritrace"
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "dev"
}

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "monthly_budget_usd" {
  description = "Monthly spend limit in USD before alerts are sent"
  type        = number
  default     = 50
}

variable "alert_email" {
  description = "Email address that receives budget alerts"
  type        = string
}

variable "owner_username" {
  description = "Your IAM Identity Center user name"
  type        = string
}

variable "github_org" {
  description = "GitHub organization that owns the repository"
  type        = string
}

# Public identifiers, not secrets. GitHub puts them in the OIDC subject claim.
# gh api orgs/<org> --jq .id  and  gh api repos/<org>/<repo> --jq .id
variable "github_org_id" {
  description = "Numeric GitHub organization ID"
  type        = string
  default     = "332410823"
}

variable "github_repo_id" {
  description = "Numeric repository ID"
  type        = string
  default     = "1381241328"
}
