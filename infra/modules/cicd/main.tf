# GitHub Actions authenticates with OIDC. No AWS access keys are stored.
# Two roles: a read-only one for plans, an admin one gated by the dev environment.

data "aws_caller_identity" "current" {}
data "aws_partition" "current" {}

# The state bucket and key created by infra/bootstrap.
data "aws_kms_alias" "state" {
  name = "alias/${var.project}-tfstate"
}

locals {
  account_id   = data.aws_caller_identity.current.account_id
  partition    = data.aws_partition.current.partition
  repo         = "${var.github_org}/${var.github_repo}"
  state_bucket = "${var.project}-tfstate-${data.aws_caller_identity.current.account_id}"
}

# AWS trusts GitHub's OIDC issuer directly, so no thumbprint is needed.
resource "aws_iam_openid_connect_provider" "github" {
  url            = "https://token.actions.githubusercontent.com"
  client_id_list = ["sts.amazonaws.com"]
}

# Plan role: any branch or pull request in this repo.
data "aws_iam_policy_document" "plan_trust" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.github.arn]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }

    condition {
      test     = "StringLike"
      variable = "token.actions.githubusercontent.com:sub"
      values   = ["repo:${local.repo}:*"]
    }
  }
}

resource "aws_iam_role" "plan" {
  name                 = "${var.project}-gha-plan"
  description          = "Read-only role used by pull request plans"
  assume_role_policy   = data.aws_iam_policy_document.plan_trust.json
  max_session_duration = 3600
}

resource "aws_iam_role_policy_attachment" "plan_readonly" {
  role       = aws_iam_role.plan.name
  policy_arn = "arn:${local.partition}:iam::aws:policy/ReadOnlyAccess"
}

# Plan writes a lock file to the state bucket, so it needs object write access there.
data "aws_iam_policy_document" "state_access" {
  statement {
    sid    = "StateBucketObjects"
    effect = "Allow"

    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:DeleteObject",
    ]

    resources = ["arn:${local.partition}:s3:::${local.state_bucket}/*"]
  }

  statement {
    sid       = "StateBucketList"
    effect    = "Allow"
    actions   = ["s3:ListBucket"]
    resources = ["arn:${local.partition}:s3:::${local.state_bucket}"]
  }

  statement {
    sid    = "StateKey"
    effect = "Allow"

    actions = [
      "kms:Decrypt",
      "kms:Encrypt",
      "kms:GenerateDataKey",
    ]

    resources = [data.aws_kms_alias.state.target_key_arn]
  }
}

resource "aws_iam_role_policy" "plan_state" {
  name   = "state-access"
  role   = aws_iam_role.plan.id
  policy = data.aws_iam_policy_document.state_access.json
}

# Apply role: only from the protected dev environment, which requires your approval.
data "aws_iam_policy_document" "apply_trust" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.github.arn]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:sub"
      values   = ["repo:${local.repo}:environment:${var.deploy_environment}"]
    }
  }
}

resource "aws_iam_role" "apply" {
  name                 = "${var.project}-gha-apply"
  description          = "Deploy role used after a merge to main"
  assume_role_policy   = data.aws_iam_policy_document.apply_trust.json
  max_session_duration = 3600
}

# Terraform manages IAM and KMS here, so the deploy role needs full access.
# It is constrained by the environment approval, not by policy.
resource "aws_iam_role_policy_attachment" "apply_admin" {
  role       = aws_iam_role.apply.name
  policy_arn = "arn:${local.partition}:iam::aws:policy/AdministratorAccess"
}
