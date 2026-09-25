# SWE-2 AWS Foundation

| Field | Value |
|---|---|
| Task | SWE-2 |
| Owner | Software Engineer |
| Status | Started |
| Started | 2026-09-23 |
| Finished | YYYY-MM-DD |
| Depends on | SWE-1 (Repository) |
| Hands off to | SWE-3 (CI/CD), ML-2 (Ingestion pipeline) |

Region: `us-east-1`. Account: your personal AWS account.

## What This Builds

| Resource | Why |
|---|---|
| S3 state bucket, versioned, KMS encrypted, TLS only | Terraform state with S3 native locking |
| IAM Identity Center groups and permission sets, one per role | Sign in as one role at a time. No IAM users, no access keys |
| CloudTrail, multi-region, KMS encrypted, log file validation | Audit trail of every API call |
| Account S3 public access block, EBS encryption by default | Account-wide guardrails |
| Monthly cost budget with email alerts | Cost control on a personal account |

## Running Cost

| Item | Monthly |
|---|---|
| 2 KMS keys (state, CloudTrail) | about $2, plus a few cents of requests |
| CloudTrail first trail, management events | Free. S3 storage for logs is cents |
| Budgets with notifications | Free |
| IAM Identity Center | Free |

Everything here is removed by the teardown at the end.

## Part 1: AWS Console Setup

Terraform needs an identity to run as, and that identity must not be the root user. These steps create it.

### 1. Install the tools

```bash
brew install terraform awscli
terraform version && aws --version
```

Terraform must be 1.11 or later. Any recent AWS CLI v2 works.

### 2. Secure the root user

1. Sign in to the AWS console as the root user.
2. Open **Account settings** (top right menu, **Security credentials**).
3. Confirm **Multi-factor authentication (MFA)** shows a device. If not, add one now.
4. Confirm there are no access keys under **Access keys**. Delete any that exist.

### 3. Enable IAM Identity Center

1. Set the console region (top right) to **US East (N. Virginia) us-east-1**.
2. Open the **IAM Identity Center** console.
3. Under **Instance configuration**, choose **Single-Region instance**.
4. Leave **Enable multi-account permissions** on.
5. Choose **Enable**.

This turns your standalone account into an AWS organization with your account as the management account. That is expected and free.

On the dashboard, copy the **AWS access portal URL**. It looks like `https://d-xxxxxxxxxx.awsapps.com/start`. You need it in step 6.

### 4. Create your user

1. In IAM Identity Center, open **Users**, then **Add user**.
2. Username: pick a short one, for example `bidex`. Write it down, Terraform needs it exactly.
3. Email: your own address. Give a first and last name.
4. Choose **Next** through the group screens, then **Add user**.
5. Open the invitation email, accept it, set a password, and register an MFA device.

### 5. Give yourself admin access

1. In IAM Identity Center, open **Permission sets**, then **Create permission set**.
2. Choose **Predefined permission set**, then **AdministratorAccess**. Choose **Next**.
3. Keep the name `AdministratorAccess`, set **Session duration** to 4 hours, then create it.
4. Open **AWS accounts**, tick your account, then **Assign users or groups**.
5. On the **Users** tab pick your user, choose **Next**, select the `AdministratorAccess` permission set, then **Submit**.

This is your break-glass access. Terraform creates the role permission sets later, but this one stays.

### 6. Sign in from the command line

```bash
aws configure sso
```

Answer the prompts:

| Prompt | Answer |
|---|---|
| SSO session name | `veritrace` |
| SSO start URL | the access portal URL from step 3 |
| SSO region | `us-east-1` |
| SSO registration scopes | press Enter for the default |

A browser opens. Approve the request, then pick your account and the `AdministratorAccess` role. For the last prompts: default client region `us-east-1`, default output format `json`, profile name `veritrace-admin`.

Check it works:

```bash
aws sso login --profile veritrace-admin
aws sts get-caller-identity --profile veritrace-admin
```

The output shows your account ID and an assumed role ARN containing `AdministratorAccess`. Write the account ID down.

## Part 2: Terraform

### 7. Start the task

```bash
cd ~/projects/veritrace
git checkout main && git pull
git checkout -b swe/swe-2-aws-foundation
unzip -o ~/Downloads/veritrace-swe-2.zip -d ~/projects/veritrace
export AWS_PROFILE=veritrace-admin
```

Set **Started** in this file and in the task tracker.

`AWS_PROFILE` lasts for this Terminal window only. Set it again in any new window.

### 8. Create the state bucket

```bash
cd infra/bootstrap
terraform init
terraform plan
```

The plan should show **8 to add**. Read it, then apply:

```bash
terraform apply
```

Type `yes`. Copy the `state_bucket` output.

This layer keeps its state in a local file, `terraform.tfstate`, in `infra/bootstrap`. That file is gitignored. Everything else uses the S3 bucket.

**Verify in the console:** open **S3**, click the `veritrace-tfstate-...` bucket.
- **Properties**: Bucket Versioning is **Enabled**, Default encryption is **SSE-KMS** with the `veritrace-tfstate` key.
- **Permissions**: Block all public access is **On**, and the bucket policy has the `DenyInsecureTransport` statement.
- Open **KMS > Customer managed keys**: the alias `veritrace-tfstate` exists with rotation enabled.

### 9. Point the dev environment at the bucket

```bash
cd ../envs/dev
cp backend.hcl.example backend.hcl
```

Edit `backend.hcl` and set `bucket` to the name you copied. Then:

```bash
cp terraform.tfvars.example terraform.tfvars
```

Edit `terraform.tfvars`:
- `alert_email`: where budget alerts go.
- `owner_username`: the Identity Center username from step 4.
- `monthly_budget_usd`: 50 is a reasonable start.

Both files are gitignored.

### 10. Apply the foundation

```bash
terraform init -backend-config=backend.hcl
terraform fmt -recursive ../..
terraform validate
terraform plan
```

`validate` prints `Success!`. The plan adds the CloudTrail, budget, account guardrails, and the four role groups and permission sets. Read it, then:

```bash
terraform apply
```

Type `yes`. It takes a few minutes, mostly Identity Center.

**If apply fails on the access module** with a message about the Identity Store user, the `owner_username` in `terraform.tfvars` does not match the username in step 4. Fix it and run `terraform apply` again.

### 11. Verify in the AWS console

| Service | Where | What to see |
|---|---|---|
| CloudTrail | **Trails** | `veritrace-dev`, Multi-region **Yes**, Log file validation **Enabled**, KMS key set |
| S3 | Buckets | `veritrace-cloudtrail-<account>` with an `AWSLogs/` folder after about 15 minutes |
| KMS | Customer managed keys | Aliases `veritrace-tfstate` and `veritrace-cloudtrail` |
| S3 | **Block Public Access settings for this account** | All four settings **On** |
| EC2 | **EC2 Dashboard > Account attributes > Data protection and privacy** | EBS encryption by default **Enabled** |
| Billing and Cost Management | **Budgets** | `veritrace-monthly` with four alerts |
| IAM Identity Center | **Permission sets** | `veritrace-swe`, `veritrace-ml`, `veritrace-ba`, `veritrace-ux`, plus `AdministratorAccess` |
| IAM Identity Center | **Groups** | `veritrace-swe`, `veritrace-ml`, `veritrace-ba`, `veritrace-ux`, each with you as a member |
| IAM Identity Center | **AWS accounts > your account** | Five assignments, one per permission set |

### 12. Prove role separation works

Open your AWS access portal URL. You now see five roles. Add the ML role as a second CLI profile:

```bash
aws configure sso --profile veritrace-ml
```

Use the same session name `veritrace` when prompted, then pick the `veritrace-ml` role.

```bash
aws sts get-caller-identity --profile veritrace-ml
aws s3 ls --profile veritrace-ml
aws iam create-user --user-name should-fail --profile veritrace-ml
```

Expected: the first two succeed, and the third fails with `AccessDenied`. That is least privilege working: the ML role can read the account and use its own services, but cannot change identity or access management.

### 13. Commit and close SWE-2

```bash
cd ~/projects/veritrace
git status
```

`terraform.tfvars`, `backend.hcl`, `.terraform/` and `terraform.tfstate` must **not** appear. If any of them does, stop and fix `.gitignore` before committing.

Set **Status** to `Approved` and fill in **Finished** in this file, then:

```bash
git add -A
git commit -m "feat(swe): AWS foundation with Terraform"
git push -u origin swe/swe-2-aws-foundation
gh pr create --web
```

Paste the `terraform apply` summary line and your console checks into the PR, then:

```bash
gh pr merge --squash --delete-branch
git checkout main && git pull
```

Mark SWE-2 Finished and Synced in the tracker.

## Teardown

Order matters. The dev environment first, the state bucket last.

```bash
cd infra/envs/dev
export AWS_PROFILE=veritrace-admin
terraform destroy

cd ../../bootstrap
terraform destroy
```

Notes:
- Destroying the dev environment removes the four role permission sets. Your console-created `AdministratorAccess` assignment stays, so you keep access.
- KMS keys enter a 7 day waiting period before final deletion.
- IAM Identity Center itself stays enabled. It costs nothing.
- To rebuild everything later, run steps 8 to 10 again.
