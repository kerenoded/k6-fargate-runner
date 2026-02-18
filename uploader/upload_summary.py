import os
import sys
import boto3

SUMMARY_PATH = "/tmp/summary.json"


def die(msg: str, code: int = 1):
    print(msg, file=sys.stderr)
    raise SystemExit(code)


def main():
    bucket = os.environ.get("RESULTS_BUCKET")
    key = os.environ.get("RESULTS_KEY")

    if not bucket or not key:
        die("Missing RESULTS_BUCKET/RESULTS_KEY env vars")

    if not os.path.exists(SUMMARY_PATH):
        die(f"Missing {SUMMARY_PATH} (handleSummary didn't write it?)")

    # Always pass an explicit region. Without it, boto3 falls back to us-east-1,
    # which causes a PermanentRedirect / 301 error when the bucket is in any
    # other region — and the entrypoint swallows that error silently with set +e.
    # AWS_DEFAULT_REGION is injected by run_task.py into the ECS task environment.
    region = os.environ.get("AWS_DEFAULT_REGION") or os.environ.get("AWS_REGION")
    if not region:
        die("Missing AWS_DEFAULT_REGION / AWS_REGION env var — cannot determine S3 region")

    s3 = boto3.client("s3", region_name=region)
    # Upload with a sane content type (handy when viewing in console)
    s3.upload_file(
        SUMMARY_PATH,
        bucket,
        key,
        ExtraArgs={"ContentType": "application/json"},
    )
    print(f"Uploaded {SUMMARY_PATH} -> s3://{bucket}/{key}")


if __name__ == "__main__":
    main()
