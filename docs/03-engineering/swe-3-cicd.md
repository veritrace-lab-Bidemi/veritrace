# SWE-3 CI/CD with OIDC

| Field | Value |
|---|---|
| Task | SWE-3 |
| Owner | Software Engineer |
| Status | Approved |
| Started | 2026-09-25 |
| Finished | 2026-09-25 |
| Depends on | SWE-1 (Repository), SWE-2 (AWS Foundation) |
| Hands off to | SWE-5 (Backend API), ML-2 (Ingestion pipeline) |

## What This Builds

| Piece | Purpose |
|---|---|
| GitHub OIDC provider in AWS | GitHub Actions gets short-lived credentials. No access keys anywhere |
| `veritrace-gha-plan` role | Read-only. Used by pull request plans. Any branch in this repo |
| `veritrace-gha-apply` role | Administrator. Only from the `dev` environment, which needs your approval |
| CI workflow | On every pull request: secret scan, format check, validate, plan posted as a comment |
| Deploy workflow | On merge to `main`: plan and apply, after approval |
| Required status checks | `main` cannot be merged into unless both CI jobs pass |
| Dependabot | Weekly updates for Actions and Terraform providers |

Running cost: nothing. IAM roles, OIDC and Actions minutes on a public repo are free.

## Steps

### 1. Start the task

```bash
cd ~/projects/veritrace
git checkout main && git pull
git checkout -b swe/swe-3-cicd
unzip -o ~/Downloads/veritrace-swe-3.zip -d ~/projects/veritrace
export AWS_PROFILE=veritrace-admin
export ORG=veritrace-lab-Bidemi
aws sso login --profile veritrace-admin
```

Set **Started** in this file and the tracker.

### 2. Add your org to the variables

Add one line to `infra/envs/dev/terraform.tfvars`:

```hcl
github_org = "veritrace-lab-Bidemi"
```

### 3. Create the roles

```bash
cd infra/envs/dev
terraform fmt -recursive ../..
terraform init -backend-config=backend.hcl
terraform validate
terraform plan
```

Expect **6 to add, 0 to change, 0 to destroy**: the OIDC provider, two roles, two policy attachments and one inline policy. Then:

```bash
terraform apply
```

**Verify in the console:** open **IAM > Identity providers**. `token.actions.githubusercontent.com` is listed. Then **IAM > Roles**, open `veritrace-gha-apply`, and on the **Trust relationships** tab confirm the condition ends with `:environment:dev`. That single line is what stops any branch from deploying.

### 4. Give GitHub the values it needs

From `infra/envs/dev`:

```bash
gh variable set AWS_REGION --repo $ORG/veritrace --body "us-east-1"
gh variable set TF_STATE_BUCKET --repo $ORG/veritrace --body "$(terraform output -raw state_bucket)"
gh variable set AWS_ROLE_PLAN --repo $ORG/veritrace --body "$(terraform output -raw gha_plan_role_arn)"
gh variable set AWS_ROLE_APPLY --repo $ORG/veritrace --body "$(terraform output -raw gha_apply_role_arn)"
gh variable list --repo $ORG/veritrace
```

The two values Terraform needs but that are not in Git go in as secrets, so they stay masked in logs:

```bash
gh secret set ALERT_EMAIL --repo $ORG/veritrace
gh secret set OWNER_USERNAME --repo $ORG/veritrace
gh secret list --repo $ORG/veritrace
```

Each `secret set` prompts you to paste the value. Use the same values as in `terraform.tfvars`.

### 5. Create the dev environment with an approval gate

```bash
MY_ID=$(gh api user --jq .id)
cat > /tmp/env.json <<EOF
{
  "wait_timer": 0,
  "prevent_self_review": false,
  "reviewers": [{"type": "User", "id": $MY_ID}],
  "deployment_branch_policy": {"protected_branches": true, "custom_branch_policies": false}
}
EOF
gh api -X PUT repos/$ORG/veritrace/environments/dev --input /tmp/env.json --jq .name
rm /tmp/env.json
```

`prevent_self_review` is false because you are the only reviewer. In a real team it would be true.

**Verify in the console:** **Settings > Environments > dev** shows **Required reviewers** with your name, and deployments limited to protected branches.

### 6. Open the pull request

```bash
cd ~/projects/veritrace
git add -A
git commit -m "feat(swe): CI/CD with GitHub Actions and OIDC"
git push -u origin swe/swe-3-cicd
gh pr create --web
```

Fill in the template with task ID `SWE-3`, then create it.

### 7. Watch the first CI run

```bash
gh pr checks --watch
```

Both jobs should pass: **Secret scan** and **Terraform plan**. Open the pull request and you should see a comment titled "Terraform plan" showing `No changes` (the roles already exist from step 3).

**Verify the OIDC login actually happened:** open **CloudTrail > Event history**, filter **Event name** = `AssumeRoleWithWebIdentity`, and open the most recent event. The user name shows the GitHub session, and the role is `veritrace-gha-plan`. That is the proof no static key was used.

**If the plan job fails on credentials**, the `AWS_ROLE_PLAN` variable or the trust condition is wrong. Compare the role ARN in the log with `terraform output -raw gha_plan_role_arn`.

### 8. Merge and approve the deploy

```bash
gh pr merge --squash --delete-branch
git checkout main && git pull
gh run watch
```

The Deploy workflow starts and then waits. Open the run in GitHub, click **Review deployments**, tick **dev**, then **Approve and deploy**. The apply runs with the admin role and reports no changes.

That pause is the point of the exercise: a merge alone cannot change AWS. Something has to approve the environment.

### 9. Require the checks before merge

Do this last, so a broken workflow cannot block your own merges.

```bash
RULESET_ID=$(gh api repos/$ORG/veritrace/rulesets --jq '.[] | select(.name=="protect-main") | .id')
gh api -X PUT repos/$ORG/veritrace/rulesets/$RULESET_ID \
  --input .github/rulesets/main-branch.json --jq '.name, .enforcement'
```

**Verify in the console:** **Settings > Rules > Rulesets > protect-main** now lists **Require status checks to pass** with `Secret scan` and `Terraform plan`.

### 10. Close SWE-3

Set **Status** to `Approved` and fill in **Finished** in this file. Commit it on a branch, open a pull request, watch the checks pass, merge, and mark SWE-3 Finished and Synced in the tracker.

## How to Read the Design

| Question | Answer |
|---|---|
| Where are the AWS keys? | There are none. GitHub presents a signed token, AWS exchanges it for credentials that expire in an hour |
| What stops another repo from assuming the role? | The trust policy pins the subject to `repo:<org>/veritrace:*` |
| What stops a random branch from deploying? | The apply role only trusts `environment:dev`, and that environment requires your approval |
| What if a secret is committed? | Three layers: pre-commit locally, GitHub push protection at the server, and the CI secret scan |
