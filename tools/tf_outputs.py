import json
import subprocess
from pathlib import Path
from typing import Any, Dict

def terraform_outputs(tf_dir: Path) -> Dict[str, Any]:
    try:
        p = subprocess.run(
            ["terraform", "output", "-json"],
            cwd=tf_dir,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        stderr = (e.stderr or "").strip()
        hint = "\nHint: run 'terraform init' and 'terraform apply' in infra/terraform first."
        raise SystemExit(f"Failed to read Terraform outputs from {tf_dir}.\n{stderr}{hint}")
    raw = json.loads(p.stdout)
    return {k: v["value"] for k, v in raw.items()}
