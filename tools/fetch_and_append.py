import argparse
import subprocess
import sys
from pathlib import Path

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run_id")
    ap.add_argument("--ledger", default="test-results/runs.jsonl")
    args = ap.parse_args()

    # 1) Fetch
    subprocess.run([sys.executable, "tools/fetch_run.py", args.run_id], check=True)

    # 2) Extract and append
    summary_path = Path("test-results") / args.run_id / "summary.json"
    if not summary_path.exists():
        raise SystemExit(f"Missing {summary_path} after fetch")

    # Append single-line JSON to ledger
    cmd = [sys.executable, "tools/extract_run_metrics.py", str(summary_path)]
    out = subprocess.check_output(cmd, text=True).strip()
    Path(args.ledger).parent.mkdir(parents=True, exist_ok=True)
    with open(args.ledger, "a") as f:
        f.write(out + "\n")

    print(f"✅ Appended to {args.ledger}")

if __name__ == "__main__":
    main()