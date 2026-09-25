output "cloudtrail_bucket" {
  description = "Bucket holding CloudTrail logs"
  value       = module.cloudtrail.log_bucket
}

output "permission_sets" {
  description = "Role permission sets available at the AWS access portal"
  value       = module.access.permission_set_names
}
