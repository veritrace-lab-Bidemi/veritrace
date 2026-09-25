variable "project" {
  description = "Project name, used as a prefix for group and permission set names"
  type        = string
}

variable "owner_username" {
  description = "Your IAM Identity Center user name, created during setup"
  type        = string
}

variable "session_duration" {
  description = "How long a signed-in role session lasts, ISO-8601"
  type        = string
  default     = "PT4H"
}
