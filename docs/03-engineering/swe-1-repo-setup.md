# SWE-1 Repository Setup

| Field | Value |
|---|---|
| Task | SWE-1 |
| Owner | Software Engineer |
| Status | Approved |
| Started | 2026-09-22 |
| Finished | 2026-09-22 |
| Depends on | None |
| Hands off to | SWE-2 (AWS Foundation), SWE-3 (CI/CD), all roles (CONTRIBUTING.md) |

## What This Sets Up

| Control | Where it is enforced |
|---|---|
| Public repo in a free GitHub organization | GitHub |
| One team per role, used in CODEOWNERS | GitHub organization |
| `main` protected: PR only, squash only, signed commits, linear history, no force push, no delete | Ruleset `protect-main` |
| Secret scanning and push protection | GitHub |
| Dependabot security alerts | GitHub |
| Local checks before every commit: no secrets, no private keys, no commits on `main` | pre-commit |

Required approvals are set to 0 because GitHub does not let you approve your own PR, and you play every role. In a real team, set `required_approving_review_count` to 1 and `require_code_owner_review` to true in `.github/rulesets/main-branch.json`.

## Steps

Run every command in macOS Terminal.

### 1. Install the tools

```bash
brew install git gh pre-commit gitleaks
git --version && gh --version && pre-commit --version && gitleaks version
```

Each command prints a version number.

### 2. Set your Git identity

1. On GitHub, open **Settings > Emails**.
2. Check **Keep my email addresses private**. Copy the `...@users.noreply.github.com` address shown there.
3. Set it in Git:

```bash
git config --global user.name "Your Name"
git config --global user.email "PASTE_NOREPLY_ADDRESS"
git config --global init.defaultBranch main
```

The repo is public. The noreply address keeps your personal email out of commit history.

### 3. Create or reuse an SSH key

```bash
ls ~/.ssh/id_ed25519.pub
```

If the file exists, reuse it and skip to step 4. If not:

```bash
ssh-keygen -t ed25519 -C "PASTE_NOREPLY_ADDRESS"
```

Press Enter to accept the default path. Set a passphrase. Then load it into the macOS keychain:

```bash
cat >> ~/.ssh/config <<'EOF'
Host github.com
  AddKeysToAgent yes
  UseKeychain yes
  IdentityFile ~/.ssh/id_ed25519
EOF
ssh-add --apple-use-keychain ~/.ssh/id_ed25519
```

### 4. Sign in with the GitHub CLI

```bash
gh auth login --hostname github.com --git-protocol ssh --web
```

When asked, choose to upload `~/.ssh/id_ed25519.pub` as your authentication key. Then add the permissions needed for teams and signing keys:

```bash
gh auth refresh --hostname github.com --scopes admin:org,write:ssh_signing_key
ssh -T git@github.com
```

The last command prints `Hi <username>! You've successfully authenticated`.

### 5. Turn on commit signing

```bash
gh ssh-key add ~/.ssh/id_ed25519.pub --type signing --title "veritrace-signing"
git config --global gpg.format ssh
git config --global user.signingkey ~/.ssh/id_ed25519.pub
git config --global commit.gpgsign true
git config --global tag.gpgsign true
echo "$(git config --global user.email) namespaces=\"git\" $(cat ~/.ssh/id_ed25519.pub)" >> ~/.ssh/allowed_signers
git config --global gpg.ssh.allowedSignersFile ~/.ssh/allowed_signers
```

The last two lines let Git verify your own signatures locally.

### 6. Create the organization

1. On GitHub, click your profile picture > **Settings**.
2. In the sidebar under **Access**, click **Organizations**, then **New organization**.
3. Choose the **Free** plan.
4. Name it, for example `veritrace-lab-<yourname>`. The name must be unique on GitHub.
5. Choose **My personal account** as the owner and finish the prompts.
6. In the new organization, open **Settings > Authentication security**. Check **Require two-factor authentication for everyone in your organization** and click **Save**. Your own account must already have 2FA on.

Save the name for the rest of this runbook. Run this again in every new Terminal window:

```bash
export ORG=your-org-name
```

### 7. Make the first commit

The files from BA-1, BA-2, UX-1 and UX-2 are already in `~/projects/veritrace/docs`. Unzip the SWE-1 files on top of them:

```bash
unzip -o ~/Downloads/veritrace-swe-1.zip -d ~/projects/veritrace
cd ~/projects/veritrace
sed -i '' "s/your-org/$ORG/g" .github/CODEOWNERS
grep "@" .github/CODEOWNERS | head -3
```

The `grep` output shows your org name, not `your-org`. Now create the first signed commit:

```bash
git init
git add -A
git status
git commit -m "chore(swe): bootstrap repository"
git log --show-signature -1
```

`git status` should list only `README.md`, `CONTRIBUTING.md`, the dotfiles, `.github/` and `docs/`. The last command shows `Good "git" signature`.

This is the only commit that goes straight to `main`. Everything after it goes through a pull request.

### 8. Create the GitHub repo and push

```bash
gh repo create $ORG/veritrace --public --source=. --remote=origin --push \
  --description "Financial Crime Knowledge Assistant" --disable-wiki
gh api repos/$ORG/veritrace/commits/main --jq .commit.verification
```

The second command should show `"verified":true`. If it shows `false`, note the `reason` value and continue. Merges into `main` are signed by GitHub, so this does not block you.

### 9. Configure the repo

```bash
gh repo edit $ORG/veritrace \
  --enable-squash-merge \
  --enable-merge-commit=false \
  --enable-rebase-merge=false \
  --delete-branch-on-merge \
  --enable-secret-scanning \
  --enable-secret-scanning-push-protection
gh api -X PUT repos/$ORG/veritrace/vulnerability-alerts
```

No output means success.

### 10. Create one team per role

```bash
for team in business-analysts ux-designers software-engineers ml-engineers; do
  gh api -X POST orgs/$ORG/teams -f name=$team -f privacy=closed --jq .slug
  gh api -X PUT orgs/$ORG/teams/$team/repos/$ORG/veritrace -f permission=push
done
gh api repos/$ORG/veritrace/codeowners/errors
```

You are added to every team automatically as the creator. CODEOWNERS teams need write access, which `permission=push` gives. The last command must return `{"errors":[]}`.

### 11. Protect `main`

```bash
gh api -X POST repos/$ORG/veritrace/rulesets --input .github/rulesets/main-branch.json --jq '.name, .enforcement'
```

The output is `protect-main` and `active`.

### 12. Install the local hooks

```bash
pre-commit install
```

Checks now run on every commit.

## Verify in the GitHub Console

Open `https://github.com/$ORG` (replace `$ORG` with your org name) and check each item.

| Where | What to check |
|---|---|
| Org > **Teams** | Four teams: business-analysts, ux-designers, software-engineers, ml-engineers |
| Org > **Settings > Authentication security** | Two-factor authentication is required |
| Repo > **Settings > Collaborators and teams** | All four teams have the **Write** role |
| Repo > **Settings > General > Pull Requests** | Only **Allow squash merging** is checked. **Automatically delete head branches** is checked |
| Repo > **Settings > Rules > Rulesets** | `protect-main` is **Active**, targets the default branch, and lists the rules from the table above |
| Repo > **Settings > Advanced Security** | Secret Protection, push protection and Dependabot alerts are enabled |
| Repo > **Code** > latest commit | Shows **Verified** (see step 8) |
| Repo > `.github/CODEOWNERS` | Opens with no error banner |

## Prove the Guardrails Work

Run each test and confirm it is blocked.

### Test 1: Direct push to `main` is rejected by GitHub

```bash
git commit --allow-empty --no-verify -m "test: direct push"
git push
```

Expected: the push fails with `GH013: Repository rule violations found`. Undo the local commit:

```bash
git reset --hard origin/main
```

### Test 2: A secret is blocked locally

```bash
git checkout -b swe/swe-1-guardrail-test
python3 -c "import secrets,string; print('token = \"ghp_' + ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(36)) + '\"')" > leak-test.py
git add leak-test.py
git commit -m "test: secret"
```

Expected: `Detect hardcoded secrets....Failed` with `RuleID: github-pat`. The token is random and not real. Clean up:

```bash
git reset HEAD leak-test.py && rm leak-test.py
git checkout main && git branch -D swe/swe-1-guardrail-test
```

### Test 3: Run all checks on a branch

```bash
git checkout -b swe/swe-1-close
pre-commit run --all-files
```

Every hook shows `Passed` or `Skipped`. If a hook shows `Failed` with `files were modified by this hook`, it fixed spacing in a file. Run the command again and it passes; the fixed files are committed in the next section. Keep this branch.

Running this on `main` always fails the `don't commit to branch` check. That is expected.

## Close SWE-1 With Your First Pull Request

1. In this file, set **Status** to `Approved` and fill in **Started** and **Finished**.
2. Commit and push:

```bash
git add -A
git commit -m "docs(swe): close SWE-1"
git push -u origin swe/swe-1-close
gh pr create --web
```

3. The browser opens with the PR template. Fill in Task ID `SWE-1`, Role `SWE`, and the handoff: "SWE-2 and SWE-3 can start. All roles follow CONTRIBUTING.md."
4. Create the PR, then merge it:

```bash
gh pr merge --squash --delete-branch
git checkout main && git pull
git log --oneline -3
```

The merged commit on GitHub shows **Verified** because GitHub signs squash merges.

5. In the task tracker, mark SWE-1 Finished and Synced.
