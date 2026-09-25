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

variable "deploy_environment" {
  description = "GitHub environment that may assume the apply role"
  type        = string
  default     = "dev"
}
