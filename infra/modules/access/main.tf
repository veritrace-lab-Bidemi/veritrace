# One IAM Identity Center group and permission set per project role.
# Your Identity Center user joins every group, so you sign in as one role at a time.

data "aws_ssoadmin_instances" "this" {}

data "aws_caller_identity" "current" {}

locals {
  instance_arn      = tolist(data.aws_ssoadmin_instances.this.arns)[0]
  identity_store_id = tolist(data.aws_ssoadmin_instances.this.identity_store_ids)[0]
  account_id        = data.aws_caller_identity.current.account_id

  roles = {
    swe = {
      display_name = "Software Engineer"
      managed_policies = [
        "arn:aws:iam::aws:policy/AdministratorAccess",
      ]
    }
    ml = {
      display_name = "AI/ML Engineer"
      managed_policies = [
        "arn:aws:iam::aws:policy/ReadOnlyAccess",
      ]
    }
    ba = {
      display_name = "Business Analyst"
      managed_policies = [
        "arn:aws:iam::aws:policy/ReadOnlyAccess",
      ]
    }
    ux = {
      display_name = "UX Designer"
      managed_policies = [
        "arn:aws:iam::aws:policy/ReadOnlyAccess",
      ]
    }
  }

  # Flattened so each managed policy attachment gets its own key.
  managed_attachments = merge([
    for role_key, role in local.roles : {
      for policy_arn in role.managed_policies :
      "${role_key}:${basename(policy_arn)}" => {
        role_key   = role_key
        policy_arn = policy_arn
      }
    }
  ]...)
}

# The user created in the console during setup.
data "aws_identitystore_user" "owner" {
  identity_store_id = local.identity_store_id

  alternate_identifier {
    unique_attribute {
      attribute_path  = "UserName"
      attribute_value = var.owner_username
    }
  }
}

resource "aws_identitystore_group" "role" {
  for_each = local.roles

  identity_store_id = local.identity_store_id
  display_name      = "${var.project}-${each.key}"
  description       = "${each.value.display_name} on ${var.project}"
}

resource "aws_identitystore_group_membership" "owner" {
  for_each = local.roles

  identity_store_id = local.identity_store_id
  group_id          = aws_identitystore_group.role[each.key].group_id
  member_id         = data.aws_identitystore_user.owner.user_id
}

resource "aws_ssoadmin_permission_set" "role" {
  for_each = local.roles

  name             = "${var.project}-${each.key}"
  description      = each.value.display_name
  instance_arn     = local.instance_arn
  session_duration = var.session_duration
}

resource "aws_ssoadmin_managed_policy_attachment" "role" {
  for_each = local.managed_attachments

  depends_on = [aws_ssoadmin_account_assignment.role]

  instance_arn       = local.instance_arn
  managed_policy_arn = each.value.policy_arn
  permission_set_arn = aws_ssoadmin_permission_set.role[each.value.role_key].arn
}

# Extra write access the ML role needs on top of read-only.
data "aws_iam_policy_document" "ml" {
  statement {
    sid    = "BedrockUse"
    effect = "Allow"

    actions = [
      "bedrock:InvokeModel",
      "bedrock:InvokeModelWithResponseStream",
      "bedrock:ListFoundationModels",
      "bedrock:GetFoundationModel",
    ]

    resources = ["*"]
  }

  statement {
    sid    = "ProjectBuckets"
    effect = "Allow"

    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:DeleteObject",
      "s3:ListBucket",
    ]

    resources = [
      "arn:aws:s3:::${var.project}-*",
      "arn:aws:s3:::${var.project}-*/*",
    ]
  }

  statement {
    sid    = "SearchAndPipelines"
    effect = "Allow"

    actions = [
      "aoss:APIAccessAll",
      "states:StartExecution",
      "states:StopExecution",
      "lambda:InvokeFunction",
      "logs:GetLogEvents",
      "logs:FilterLogEvents",
    ]

    resources = ["*"]
  }
}

resource "aws_ssoadmin_permission_set_inline_policy" "ml" {
  depends_on = [aws_ssoadmin_account_assignment.role]

  inline_policy      = data.aws_iam_policy_document.ml.json
  instance_arn       = local.instance_arn
  permission_set_arn = aws_ssoadmin_permission_set.role["ml"].arn
}

resource "aws_ssoadmin_account_assignment" "role" {
  for_each = local.roles

  instance_arn       = local.instance_arn
  permission_set_arn = aws_ssoadmin_permission_set.role[each.key].arn
  principal_id       = aws_identitystore_group.role[each.key].group_id
  principal_type     = "GROUP"
  target_id          = local.account_id
  target_type        = "AWS_ACCOUNT"
}
