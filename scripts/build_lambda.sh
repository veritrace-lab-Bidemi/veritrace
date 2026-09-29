#!/usr/bin/env bash
# Build the ingestion Lambda package.
#
# Two things make this more than a zip of the source tree:
#
#   1. tiktoken is a compiled wheel, so it must be fetched for the Lambda
#      platform (linux x86_64, cp312), not for this Mac.
#   2. tiktoken downloads its vocabulary on first use. In Lambda that would be a
#      slow, failure-prone cold start, so the vocabulary is baked into the
#      package here and found at runtime through TIKTOKEN_CACHE_DIR.
#
# Token counts decide chunk budgets, so they have to be exact in the pipeline,
# not estimated.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD="$ROOT/build/lambda"
ZIP="$ROOT/build/veritrace-ingest.zip"
PY_VERSION="3.12"
# The python3.12 Lambda runtime is Amazon Linux 2023 (glibc 2.34), so current
# wheels are built for manylinux_2_28. The older tag is listed as a fallback for
# dependencies that still publish only 2014 wheels; pip takes the best match.
PLATFORMS=(--platform manylinux_2_28_x86_64 --platform manylinux2014_x86_64)

rm -rf "$BUILD" "$ZIP"
mkdir -p "$BUILD/tiktoken_cache"

echo "==> installing dependencies for Amazon Linux 2023, cp${PY_VERSION/./}"
pip install \
  --quiet \
  "${PLATFORMS[@]}" \
  --python-version "$PY_VERSION" \
  --implementation cp \
  --only-binary=:all: \
  --target "$BUILD" \
  -r "$ROOT/ml/requirements-lambda.txt"

# tiktoken names each cached file sha1(url) and checks it against a known
# sha256. Fetching it directly means the build does not import tiktoken locally,
# so it works whatever architecture this machine or this shell happens to be.
VOCAB_URL="https://openaipublic.blob.core.windows.net/encodings/cl100k_base.tiktoken"
VOCAB_NAME="9b5ad71b2ce5302211f9c61530b329a4922fc6a4"          # sha1 of the URL
VOCAB_SHA="223921b76ee99bde995b7ff738513eef100fb51d18c93597a113bcffe865b2a7"

echo "==> baking the tiktoken vocabulary into the package"
curl -sSfL "$VOCAB_URL" -o "$BUILD/tiktoken_cache/$VOCAB_NAME"

ACTUAL=$(shasum -a 256 "$BUILD/tiktoken_cache/$VOCAB_NAME" | cut -d' ' -f1)
if [ "$ACTUAL" != "$VOCAB_SHA" ]; then
  echo "vocabulary checksum mismatch" >&2
  echo "  expected $VOCAB_SHA" >&2
  echo "  got      $ACTUAL" >&2
  exit 1
fi
echo "    cached $VOCAB_NAME ($(du -h "$BUILD/tiktoken_cache/$VOCAB_NAME" | cut -f1)), checksum verified"

echo "==> adding source"
mkdir -p "$BUILD/ml"
cp "$ROOT/ml/__init__.py" "$BUILD/ml/"
cp -R "$ROOT/ml/ingestion" "$BUILD/ml/"
cp -R "$ROOT/ml/pipeline" "$BUILD/ml/"
find "$BUILD" -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true
# dist-info directories are kept: tiktoken discovers its encodings through the
# tiktoken_ext namespace, and stripping package metadata is a cheap way to break
# that in a confusing manner. The size saved is not worth the risk.

echo "==> zipping"
(cd "$BUILD" && zip -qr "$ZIP" .)

SIZE=$(du -h "$ZIP" | cut -f1)
echo "==> built $ZIP ($SIZE)"
echo "    verify the vocabulary is inside:"
echo "    unzip -l \"$ZIP\" | grep tiktoken_cache"
