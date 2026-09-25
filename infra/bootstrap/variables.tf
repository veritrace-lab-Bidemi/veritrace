variable "project" {
  description = "Project name, used as a prefix for resource names"
  type        = string
  default     = "veritrace"
}

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}
