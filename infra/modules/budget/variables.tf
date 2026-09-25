variable "project" {
  description = "Project name, used as a prefix for resource names"
  type        = string
}

variable "monthly_limit_usd" {
  description = "Monthly spend limit in USD"
  type        = number
}

variable "alert_email" {
  description = "Email address that receives budget alerts"
  type        = string
}

variable "actual_thresholds_percent" {
  description = "Percentages of the limit that trigger an alert on actual spend"
  type        = list(number)
  default     = [50, 80, 100]
}
