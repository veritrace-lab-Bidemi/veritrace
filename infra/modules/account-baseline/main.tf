# Account-wide safety settings.

# No S3 bucket in this account can be made public.
resource "aws_s3_account_public_access_block" "this" {
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# New EBS volumes are encrypted by default.
resource "aws_ebs_encryption_by_default" "this" {
  enabled = true
}
