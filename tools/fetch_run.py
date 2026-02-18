import argparse
import os
import sys
from pathlib import Path
import boto3

# Allow both `python tools/fetch_run.py` and `python -m tools.fetch_run`
if __package__ is None and __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.tf_outputs import terraform_outputs

REGION = os.environ.get("AWS_REGION", "eu-west-1")
REPO_ROOT = Path(__file__).resolve().parents[1]
TF_DIR = REPO_ROOT / "infra" / "terraform"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run_id", help="RUN_ID printed by tools/run_task.py")
    ap.add_argument("--out-dir", default="test-results", help="Local folder to store downloaded runs")
    ap.add_argument("--region", default=REGION)
    args = ap.parse_args()

    outs = terraform_outputs(TF_DIR)
    bucket = outs["results_bucket_name"]
    prefix = outs["results_prefix"]

    # Where the task uploaded it
    key = f"{prefix}/{args.run_id}/summary.json"

    out_dir = Path(args.out_dir) / args.run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "summary.json"

    s3 = boto3.client("s3", region_name=args.region)

    try:
        s3.download_file(bucket, key, str(out_path))
    except Exception as e:
        raise SystemExit(
            f"Failed to download s3://{bucket}/{key}\n"
            f"Error: {e}\n"
            f"Tip: confirm the run finished and uploaded results."
        )

    print(f"✅ Downloaded: {out_path}")
    print(f"📦 Source: s3://{bucket}/{key}")

if __name__ == "__main__":
    main()