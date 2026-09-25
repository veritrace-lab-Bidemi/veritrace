output "cloudtrail_bucket" {
  description = "Bucket holding CloudTrail logs"
  value       = module.cloudtrail.log_bucket
}

output "permission_sets" {
  description = "Role permission sets available at the AWS access portal"
  value       = module.access.permission_set_names
}

output "gha_plan_role_arn" {
  description = "Set as the AWS_ROLE_PLAN repository variable"
  value       = module.cicd.plan_role_arn
}

output "gha_apply_role_arn" {
  description = "Set as the AWS_ROLE_APPLY repository variable"
  value       = module.cicd.apply_role_arn
}

output "state_bucket" {
  description = "Set as the TF_STATE_BUCKET repository variable"
  value       = module.cicd.state_bucket
}
