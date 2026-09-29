output "data_bucket" {
  description = "Bucket holding raw XML, chunk records and manifests"
  value       = aws_s3_bucket.data.id
}

output "data_key_arn" {
  description = "KMS key protecting the data bucket"
  value       = aws_kms_key.data.arn
}

output "lambda_name" {
  description = "Ingestion function name"
  value       = aws_lambda_function.ingest.function_name
}

output "state_machine_arn" {
  description = "Ingestion state machine, started by the runbook"
  value       = aws_sfn_state_machine.ingest.arn
}
