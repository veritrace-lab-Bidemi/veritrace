variable "project" {
  description = "Project name, used as a prefix for resource names"
  type        = string
}

variable "trail_name" {
  description = "CloudTrail trail name"
  type        = string
}

variable "log_retention_days" {
  description = "Days to keep CloudTrail logs in S3"
  type        = number
  default     = 90
}
