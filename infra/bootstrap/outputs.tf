output "state_bucket" {
  description = "Name of the Terraform state bucket. Put this in infra/envs/dev/backend.tf"
  value       = aws_s3_bucket.state.id
}

output "state_kms_key_arn" {
  description = "KMS key that encrypts the state bucket"
  value       = aws_kms_key.state.arn
}
