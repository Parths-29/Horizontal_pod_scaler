"""
ml/upload_model.py
───────────────────────────────────────────────────────────────────────────────
Uploads the trained model artifact to S3 for use by the KEDA external scaler.

Authentication options (in priority order):
  1. IRSA (IAM Roles for Service Accounts) — when running inside EKS
     The pod's ServiceAccount annotation triggers automatic credential injection
     via the OIDC token projector — no static keys ever touch the filesystem.
  2. Environment variables: AWS_ACCESS_KEY_ID + AWS_SECRET_ACCESS_KEY + AWS_DEFAULT_REGION
     Used for local dev / CI — credentials set in Jenkins credential store.
  3. ~/.aws/credentials profile — local developer convenience

Interview talking point:
  We deliberately DON'T hardcode credentials or commit .env files.
  The scaler pod uses IRSA (IAM Roles for Service Accounts) so that:
  - S3 access is pod-scoped (not node-scoped)
  - Credentials auto-rotate (no manual secret rotation)
  - CloudTrail logs show which pod did what
  This is the AWS-recommended pattern for EKS workloads.

Usage:
    export S3_BUCKET=my-hpa-scaler-artifacts
    export AWS_DEFAULT_REGION=us-east-1
    python ml/upload_model.py [--model-path ml/artifacts/model.pkl]

Environment variables:
    S3_BUCKET            — target bucket name (required)
    S3_MODEL_KEY         — object key inside bucket (default: models/model.pkl)
    AWS_ACCESS_KEY_ID    — (optional, for local dev)
    AWS_SECRET_ACCESS_KEY — (optional, for local dev)
    AWS_DEFAULT_REGION   — defaults to us-east-1
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

import boto3
from botocore.exceptions import BotoCoreError, ClientError

# ─── Paths ────────────────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_MODEL_PATH = SCRIPT_DIR / "artifacts" / "model.pkl"
DEFAULT_META_PATH = SCRIPT_DIR / "artifacts" / "metadata.json"

# ─── Helpers ──────────────────────────────────────────────────────────────────

def sha256_of_file(path: Path) -> str:
    """SHA-256 digest of a file (base64url encoded, matches AWS S3 checksum)."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def upload_file(
    s3_client,
    local_path: Path,
    bucket: str,
    key: str,
) -> str:
    """
    Upload *local_path* to s3://{bucket}/{key} and return the S3 URI.

    Uses multipart upload via boto3's managed transfer for files > 8 MB.
    Sets server-side encryption (AES-256) — bucket policy enforces this anyway.
    """
    file_size_mb = local_path.stat().st_size / (1024 ** 2)
    print(f"[upload] Uploading {local_path.name}  ({file_size_mb:.2f} MB) …")
    print(f"         → s3://{bucket}/{key}")

    extra_args = {
        "ServerSideEncryption": "AES256",
        "Metadata": {
            "sha256": sha256_of_file(local_path),
        },
    }

    s3_client.upload_file(
        str(local_path),
        bucket,
        key,
        ExtraArgs=extra_args,
    )

    s3_uri = f"s3://{bucket}/{key}"
    print(f"[upload] ✓ Done: {s3_uri}")
    return s3_uri


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Upload model artifact to S3")
    parser.add_argument("--model-path", type=Path, default=DEFAULT_MODEL_PATH)
    parser.add_argument("--meta-path", type=Path, default=DEFAULT_META_PATH)
    parser.add_argument(
        "--s3-model-key",
        default=os.environ.get("S3_MODEL_KEY", "models/model.pkl"),
        help="S3 object key for the model (default: models/model.pkl)",
    )
    parser.add_argument(
        "--s3-meta-key",
        default="models/metadata.json",
        help="S3 object key for metadata (default: models/metadata.json)",
    )
    args = parser.parse_args()

    # ── Validate pre-conditions ───────────────────────────────────────────────
    bucket = os.environ.get("S3_BUCKET")
    if not bucket:
        print(
            "[upload] ERROR: S3_BUCKET environment variable is not set.\n"
            "  Set it with: export S3_BUCKET=<your-bucket-name>",
            file=sys.stderr,
        )
        sys.exit(1)

    if not args.model_path.exists():
        print(
            f"[upload] ERROR: Model file not found: {args.model_path}\n"
            "  Run `python ml/train.py` first.",
            file=sys.stderr,
        )
        sys.exit(1)

    region = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
    print(f"[upload] Region: {region}  |  Bucket: {bucket}")

    # ── Build S3 client ───────────────────────────────────────────────────────
    # boto3 auto-discovers credentials in this order:
    #   1. IRSA web identity token (when running in EKS with IRSA annotation)
    #   2. AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY env vars
    #   3. ~/.aws/credentials
    # We never pass credentials explicitly here — that would risk committing them.
    try:
        s3 = boto3.client("s3", region_name=region)
        # Validate that the bucket exists and we have access
        s3.head_bucket(Bucket=bucket)
    except ClientError as exc:
        error_code = exc.response["Error"]["Code"]
        if error_code == "404":
            print(f"[upload] ERROR: Bucket '{bucket}' does not exist.", file=sys.stderr)
        elif error_code in ("403", "AccessDenied"):
            print(
                f"[upload] ERROR: Access denied to bucket '{bucket}'.\n"
                "  Check your IAM permissions / IRSA role.",
                file=sys.stderr,
            )
        else:
            print(f"[upload] ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
    except BotoCoreError as exc:
        print(f"[upload] Boto3 error: {exc}", file=sys.stderr)
        sys.exit(1)

    # ── Upload model ──────────────────────────────────────────────────────────
    model_uri = upload_file(s3, args.model_path, bucket, args.s3_model_key)

    # ── Upload metadata ───────────────────────────────────────────────────────
    if args.meta_path.exists():
        # Annotate metadata with S3 location so scaler knows where to pull from
        with open(args.meta_path) as f:
            meta = json.load(f)
        meta["s3_uri"] = model_uri
        meta["s3_bucket"] = bucket
        meta["s3_key"] = args.s3_model_key

        tmp_meta = args.meta_path.with_suffix(".upload.json")
        with open(tmp_meta, "w") as f:
            json.dump(meta, f, indent=2)

        upload_file(s3, tmp_meta, bucket, args.s3_meta_key)
        tmp_meta.unlink()  # clean up temp file

    print(f"\n[upload] Model available at: {model_uri}")
    print("[upload] Phase 2 upload complete ✓")


if __name__ == "__main__":
    main()
