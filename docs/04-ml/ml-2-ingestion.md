# ML-2 Ingestion Pipeline

| Field | Value |
|---|---|
| Task | ML-2 |
| Owner | AI/ML Engineer |
| Status | Approved |
| Started | YYYY-MM-DD |
| Finished | 2026-09-28 |
| Depends on | ML-1 (Source and chunking spike), SWE-2 (AWS foundation) |
| Hands off to | ML-3 (Embeddings and index), SWE-4 (API contract) |

## What This Builds

| Piece | Purpose |
|---|---|
| Data bucket | Raw XML, chunk records and manifests, KMS encrypted and versioned |
| Ingestion Lambda | One function, four actions: resolve, fetch, transform, finalize |
| State machine | Fetches and transforms each part, then writes the manifest |
| Validation gates | An impossible citation or non-verbatim text fails the run |
| Manifest | Names exactly what a rebuild should load, with checksums |

Scope is eCFR only. FFIEC and FinCEN are separate tasks, because FinCEN needs
crawling plus PDF extraction and would stall the pipeline work behind it.

## Why It Is Built This Way

**The gates raise rather than annotate.** ML-1 found 145 paragraphs in 31 CFR
1010.100 carrying confidently wrong citations that no flag caught. A wrong
citation is worse than a missing one because it is quotable, so `transform`
stops the run when a path is impossible under the CFR paragraph cycle or when
chunk text has drifted from its source. Step Functions retries `Transform` only
on Lambda service errors, never on a validation failure: bad data does not
become good by trying again.

**Chunk records persist in S3, not only in the index.** The index is the
expensive, disposable part. Keeping records here means a rebuild reloads from
S3 in minutes with no re-fetching and no re-embedding, which is what makes
"shut it down and bring it back for a demo" cheap.

**Nothing is overwritten.** Keys carry the issue date, so two vintages coexist.
`latest.json` is written last and only on success, so it never names a partial
run.

**The token counter is exact in Lambda.** Chunk budgets are decided in tokens,
so the build bakes tiktoken's vocabulary into the package rather than
estimating or downloading it at cold start.

## Cost

| Resource | While idle | Notes |
|---|---|---|
| S3 | Cents | The corpus is a few MB |
| KMS key | ~$1/month | One key, charged whether used or not |
| Lambda | $0 | Well inside the free tier at this volume |
| Step Functions | $0 | Standard workflows include 4,000 transitions a month |
| CloudWatch Logs | Cents | 30-day retention |

About **$1 to $2 a month at rest**. This is the durable plane and is meant to be
left running; the expensive component is the search index in ML-3. See
*Teardown* below.

## Steps

### 1. Start the task

```bash
cd ~/projects/veritrace
git checkout main && git pull
git checkout -b ml/ml-2-ingestion
unzip -o ~/Downloads/veritrace-ml-2.zip
source .venv/bin/activate
export AWS_PROFILE=veritrace-admin
aws sso login --profile veritrace-admin
```

Set **Started** in this file and the tracker.

### 2. Prove the pipeline before building anything

The stages take a storage interface, so the whole pipeline runs against your
filesystem with no AWS involved:

```bash
python -m pytest ml/tests -q
python -m ml.pipeline.local_run --parts 1020
```

Expect **94 passed**, then a run that prints per-part counts and a manifest
summary. Look at what it wrote:

```bash
find data/local -type f
cat data/local/manifests/ecfr-31-x/latest.json
```

Four kinds of key: `raw/`, `chunks/`, a dated `manifests/` entry, and
`latest.json`. This is the exact layout the Lambda produces, so if something is
wrong here it is a pipeline problem, not a permissions problem. That distinction
saves a lot of time later.

Then the full corpus:

```bash
python -m ml.pipeline.local_run
```

### 3. Build the Lambda package

```bash
bash scripts/build_lambda.sh
```

This installs tiktoken for the Lambda platform rather than for your Mac, bakes
the vocabulary into the package, and adds `ml/ingestion` and `ml/pipeline`.

**Verify the vocabulary is inside**, because a package without it fails at
runtime in a way that looks like a network problem:

```bash
unzip -l build/veritrace-ingest.zip | grep tiktoken_cache
unzip -l build/veritrace-ingest.zip | grep -c "ml/"
du -h build/veritrace-ingest.zip
```

### 4. Provision

```bash
cd infra/envs/dev
terraform fmt -recursive ../..
terraform init -backend-config=backend.hcl
terraform validate
terraform plan
```

Expect **16 to add, 0 to change, 0 to destroy**: a KMS key and alias, the bucket
with its five configuration resources and policy, two IAM roles with a policy
each, two log groups, the function, and the state machine. Check the count
against the plan rather than against this sentence. Then:

```bash
terraform apply
```

**Verify in the console:**

| Where | What to confirm |
|---|---|
| **S3 > veritrace-data-… > Properties** | Encryption is SSE-KMS with `alias/veritrace-data`, Bucket Versioning is Enabled |
| **S3 > Permissions** | Block public access is fully on, and the bucket policy has a `DenyInsecureTransport` statement |
| **S3 > Management** | Lifecycle rule `expire-old-versions` exists |
| **Lambda > veritrace-ingest > Configuration > Environment variables** | `DATA_BUCKET` and `TIKTOKEN_CACHE_DIR` are set |
| **Lambda > Configuration > Permissions** | The execution role can reach only this bucket and this key, not `*` |
| **Step Functions > State machines > veritrace-ingest** | The graph shows Resolve, a Map, and Finalize |

Reading the Lambda's role policy is worth a minute. It is the difference between
a function that can touch one bucket and one that can touch your whole account.

### 5. Run an ingestion

```bash
cd ~/projects/veritrace
SM=$(cd infra/envs/dev && terraform output -raw ingest_state_machine_arn)

aws stepfunctions start-execution \
  --state-machine-arn "$SM" \
  --name "ml2-first-$(date +%s)" \
  --input '{"source_id":"ecfr-31-x","as_of":null,"parts":null,"max_tokens":512}'
```

All four keys must be present in the input, `null` where you want the default.
Step Functions fails a path that does not resolve, so an omitted key is an error
rather than a default.

Watch it:

```bash
EXEC=$(aws stepfunctions list-executions --state-machine-arn "$SM" \
  --max-results 1 --query 'executions[0].executionArn' --output text)
aws stepfunctions describe-execution --execution-arn "$EXEC" \
  --query '{status:status,output:output}' --output json
```

**Verify in the console:** **Step Functions > veritrace-ingest > Executions >**
the newest one. The graph view colours each state as it completes, and the Map
shows one iteration per part. Open a Fetch step and read its input and output.
This view is the reason the pipeline is orchestrated rather than written as one
long function: when part 1010 fails, you can see that it failed, why, and that
the other seven were unaffected.

### 6. Check what landed

```bash
BUCKET=$(cd infra/envs/dev && terraform output -raw data_bucket)
aws s3 ls "s3://$BUCKET/" --recursive --human-readable | head -30
aws s3 cp "s3://$BUCKET/manifests/ecfr-31-x/latest.json" - | python -m json.tool
```

The manifest totals should match your ML-1 numbers: **235 sections, 417 chunks**.
If they differ, something changed between the spike and the pipeline and is
worth understanding before ML-3 builds on it.

**Verify a citation by hand**, the same check that found two real defects in ML-1:

```bash
aws s3 cp "s3://$BUCKET/chunks/ecfr-31-x/$(aws s3 cp s3://$BUCKET/manifests/ecfr-31-x/latest.json - | python -c 'import json,sys; print(json.load(sys.stdin)["as_of"])')/part-1020.jsonl" - \
  | python -c "
import json,sys
for line in sys.stdin:
    r = json.loads(line)
    if r['citation'] == '31 CFR 1020.220':
        print(r['pinpoint'], r['token_count']); print(r['text'][:400]); break"
```

Compare against the section on eCFR. The text must sit at the paragraphs the
pinpoint names.

### 7. Prove the guardrails

Each of these should fail. A guardrail you have never seen refuse something is
an assumption, not a control.

**Public access is blocked:**

```bash
aws s3api put-object-acl --bucket "$BUCKET" \
  --key manifests/ecfr-31-x/latest.json --acl public-read
```

Expect `AccessDenied`.

**Plain HTTP is refused:**

```bash
curl -s -o /dev/null -w '%{http_code}\n' \
  "http://$BUCKET.s3.amazonaws.com/manifests/ecfr-31-x/latest.json"
```

Expect `403`, from the bucket policy rather than from S3 defaults.

**A bad citation stops the run.** The gate rejects a paragraph path that federal
drafting cannot produce. A capital directly under a letter is one: the arabic
and roman levels cannot be skipped.

```bash
LAMBDA=$(cd infra/envs/dev && terraform output -raw ingest_lambda_name)

cat > /tmp/broken.xml <<'XML'
<DIV5 N="9990" TYPE="PART"><HEAD>PART 9990</HEAD>
<DIV8 N="&#167; 9990.100" TYPE="SECTION"><HEAD>&#167; 9990.100 Broken.</HEAD>
<P>(a) First paragraph of the section.</P>
<P>(A) Impossible: a capital directly under a letter, with no (1) or (i) between.</P>
</DIV8></DIV5>
XML

aws s3 cp /tmp/broken.xml "s3://$BUCKET/raw/ecfr-31-x/9999-01-01/part-9990.xml"

aws lambda invoke --function-name "$LAMBDA" \
  --cli-binary-format raw-in-base64-out \
  --payload '{"action":"transform","source_id":"ecfr-31-x","part":"9990","as_of":"9999-01-01","run_id":"guardrail-test"}' \
  /tmp/out.json
cat /tmp/out.json
```

Expect `FunctionError: Unhandled` and a `ValidationFailed` message naming
`(a)(A)` as impossible under the CFR cycle. Then clean up both prefixes, since
a failed attempt may still have written a chunk:

```bash
aws s3 rm "s3://$BUCKET/raw/ecfr-31-x/9999-01-01/" --recursive
aws s3 rm "s3://$BUCKET/chunks/ecfr-31-x/9999-01-01/" --recursive
```

A first version of this test used `(a)` followed by `(a)(b)` and did **not**
fail, which is worth understanding rather than forgetting. `(a)(b)` is read as a
marker run, the same rule that handles `(5)(i)`, so the sequence became `a, a, b`
and the resolver flattened it to three valid top-level paths, flagging one as
unresolved. Mangled input that the resolver can recover into a legal structure is
not the same as an impossible citation, and only the second is what this gate
exists to stop.

That failure is the point of the task. The pipeline refuses to produce a
citation that cannot exist, rather than storing it with a flag nobody reads.

### 8. Check the spend

```bash
aws ce get-cost-and-usage \
  --time-period Start=$(date -v-7d +%F),End=$(date +%F) \
  --granularity DAILY --metrics UnblendedCost \
  --group-by Type=DIMENSION,Key=SERVICE \
  --query 'ResultsByTime[-1].Groups[?Metrics.UnblendedCost.Amount!=`0`]' --output table
```

On macOS `date -v-7d` is correct; on Linux it is `date -d '7 days ago'`.

Veritrace should show only KMS (the project's three keys, about $0.06 a day) and
negligible S3. Anything else belongs to something other than this project, and
is worth identifying before ML-3 adds a search index, because a budget alert
that fires for unrelated reasons is an alert you learn to ignore.

```bash
for R in us-east-1 us-east-2 us-west-2; do
  echo "== $R"
  aws rds describe-db-instances --region $R \
    --query 'DBInstances[].{id:DBInstanceIdentifier,class:DBInstanceClass}' --output text
  aws elasticache describe-cache-clusters --region $R \
    --query 'CacheClusters[].{id:CacheClusterId,type:CacheNodeType}' --output text
  aws ec2 describe-instances --region $R \
    --filters Name=instance-state-name,Values=running \
    --query 'Reservations[].Instances[].{id:InstanceId,type:InstanceType}' --output text
done
```

### 9. Close ML-2

Set **Status** to `Approved`, fill in **Finished**, commit, open a pull request,
watch both checks pass, merge, and mark ML-2 Finished and Synced in the tracker.

## Teardown and Rebuild

**Leave this running.** At $1 to $2 a month it is not worth removing, and it is
what makes bringing the project back quick: the chunk records are already
built, so a rebuild skips fetching and parsing entirely.

If you do need it gone:

```bash
cd infra/envs/dev
terraform destroy -target=module.ingestion
```

The bucket has `force_destroy = true`, so this deletes the data with it. A later
rebuild re-fetches from eCFR and takes a few minutes, which is acceptable
because every source is public and reproducible. Nothing here is irreplaceable
by design.

To bring it back:

```bash
bash scripts/build_lambda.sh
cd infra/envs/dev && terraform apply
# then start an execution as in step 5
```

## What ML-3 Inherits

| Item | State |
|---|---|
| Chunk records | `s3://<data bucket>/chunks/ecfr-31-x/<as_of>/part-*.jsonl` |
| Manifest | `manifests/ecfr-31-x/latest.json`, names every file with checksums |
| Record schema | `SCHEMA_VERSION = 1` in `ml/pipeline/keys.py`. Bump it if a field changes |
| Storage interface | `ml/pipeline/storage.py`. ML-3 reads through the same seam |
| Embeddings | Not built. Write them beside the chunks, not only into the index |
| Search index | Not built. This is the expensive plane; settle the backend first |

## Open Questions for ML-3

1. Which embedding model: Titan Text Embeddings V2 at 1024 dimensions, or
   Cohere Embed English V3 at 512 tokens? The 512-token chunk budget was chosen
   to keep both available.
2. Does the exact Bedrock token count differ from tiktoken's enough to matter?
   If so, the counter is pluggable and chunking should be re-run.
3. Should the 62 cross-reference stub chunks be indexed, resolved to their
   target at ingestion, or followed at query time?

## Notes

The Terraform in this task has not been run before delivery; the state machine
definition was parsed and the Python is tested, but `fmt`, `validate` and `plan`
in step 4 are the first real check of the HCL. Read the plan rather than
applying it blind.
