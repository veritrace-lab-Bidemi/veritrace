output "plan_role_arn" {
  description = "Role assumed by pull request plans"
  value       = aws_iam_role.plan.arn
}

output "apply_role_arn" {
  description = "Role assumed by deploys from main"
  value       = aws_iam_role.apply.arn
}

output "state_bucket" {
  description = "Terraform state bucket name"
  value       = local.state_bucket
}
