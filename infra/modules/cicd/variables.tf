variable "project" {
  description = "Project name, used as a prefix for resource names"
  type        = string
}

variable "github_org" {
  description = "GitHub organization that owns the repository"
  type        = string
}

variable "github_repo" {
  description = "Repository name"
  type        = string
  default     = "veritrace"
}
variable "github_org_id" {
  description = "Numeric GitHub organization ID. GitHub puts it in the OIDC subject"
  type        = string
}

variable "github_repo_id" {
  description = "Numeric repository ID. GitHub puts it in the OIDC subject"
  type        = string
}
variable "deploy_environment" {
  description = "GitHub environment that may assume the apply role"
  type        = string
  default     = "dev"
}
