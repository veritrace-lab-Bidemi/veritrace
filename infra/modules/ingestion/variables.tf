variable "project" {
  description = "Project name, used as a prefix for resource names"
  type        = string
}

variable "lambda_zip_path" {
  description = "Deployment package built by scripts/build_lambda.sh"
  type        = string
}

variable "lambda_memory_mb" {
  description = "Lambda memory. More memory also buys more CPU"
  type        = number
  default     = 1024
}

variable "lambda_timeout_seconds" {
  description = "Per-invocation timeout. Part 1010 is the long one"
  type        = number
  default     = 300
}

variable "map_concurrency" {
  description = "Parts fetched at once. Kept low to stay polite to eCFR"
  type        = number
  default     = 2
}

variable "log_retention_days" {
  description = "CloudWatch log retention"
  type        = number
  default     = 30
}

variable "noncurrent_version_days" {
  description = "Days before superseded object versions are deleted"
  type        = number
  default     = 30
}
