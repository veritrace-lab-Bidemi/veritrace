output "permission_set_names" {
  description = "Permission sets created, one per role"
  value       = [for ps in aws_ssoadmin_permission_set.role : ps.name]
}

output "group_names" {
  description = "Identity Center groups created, one per role"
  value       = [for g in aws_identitystore_group.role : g.display_name]
}
