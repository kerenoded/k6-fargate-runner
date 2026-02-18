import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

# Allow both `python tools/fetch_and_append.py` and `python -m tools.fetch_and_append`
if __package__ is None and __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

REPO_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_REGION = os.environ.get("AWS_DEFAULT_REGION") or os.environ.get("AWS_REGION") or "eu-west-1"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run_id")
    ap.add_argument("--ledger", default="test-results/runs.jsonl")
    ap.add_argument(
        "--region",
        default=_DEFAULT_REGION,
        help="AWS region of the results S3 bucket (default: AWS_REGION env var or eu-west-1).",
    )
    args = ap.parse_args()

    fetch_script = REPO_ROOT / "tools" / "fetch_run.py"
    extract_script = REPO_ROOT / "tools" / "extract_run_metrics.py"

    # 1) Fetch — forward --region so boto3 uses the correct S3 endpoint.
    # Without this, fetch_run.py falls back to its own default (eu-west-1) and
    # gets a PermanentRedirect for buckets in any other region.
    subprocess.run(
        [sys.executable, str(fetch_script), args.run_id, "--region", args.region],
        check=True,
    )

    # 2) Extract and append
    summary_path = REPO_ROOT / "test-results" / args.run_id / "summary.json"
    if not summary_path.exists():
        raise SystemExit(f"Missing {summary_path} after fetch")

    # Append single-line JSON to ledger
    cmd = [sys.executable, str(extract_script), str(summary_path)]
    out = subprocess.check_output(cmd, text=True).strip()

    # Validate the output is valid JSON before writing to the ledger.
    # If extract_run_metrics.py ever prints a warning/error to stdout, writing
    # that raw text would corrupt runs.jsonl and break plot_runs.py.
    try:
        json.loads(out)
    except json.JSONDecodeError as e:
        raise SystemExit(
            f"extract_run_metrics.py produced invalid JSON — ledger not modified.\n"
            f"Output: {out[:500]}\nError: {e}"
        )

    ledger = Path(args.ledger)
    ledger.parent.mkdir(parents=True, exist_ok=True)
    with open(ledger, "a") as f:
        f.write(out + "\n")

    print(f"✅ Appended to {args.ledger}")


if __name__ == "__main__":
    main()
