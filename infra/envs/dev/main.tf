module "account_baseline" {
  source = "../../modules/account-baseline"
}

module "cloudtrail" {
  source = "../../modules/cloudtrail"

  project    = var.project
  trail_name = "${var.project}-${var.environment}"
}

module "budget" {
  source = "../../modules/budget"

  project           = var.project
  monthly_limit_usd = var.monthly_budget_usd
  alert_email       = var.alert_email
}

module "access" {
  source = "../../modules/access"

  project        = var.project
  owner_username = var.owner_username
}

module "cicd" {
  source = "../../modules/cicd"

  project    = var.project
  github_org = var.github_org
}
