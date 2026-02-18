import os
import subprocess
import sys
from pathlib import Path
from datetime import datetime, timezone

# Allow both `python tools/build_push.py` and `python -m tools.build_push`
# When executed as a script, Python puts `tools/` on sys.path, not repo root,
# so absolute imports like `from tools...` would otherwise fail.
if __package__ is None and __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.tf_outputs import terraform_outputs

REGION = os.environ.get("AWS_REGION", "eu-west-1")
REPO_ROOT = Path(__file__).resolve().parents[1]
TF_DIR = REPO_ROOT / "infra" / "terraform"


def run(cmd, cwd=None, input_text=None):
    print("+", " ".join(cmd))
    subprocess.run(cmd, cwd=cwd, check=True, input=input_text, text=True)


def ensure_buildx():
    # Create a buildx builder if missing (idempotent)
    try:
        subprocess.run(
            ["docker", "buildx", "inspect", "k6builder"],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError:
        run(["docker", "buildx", "create", "--name", "k6builder", "--use"])
    run(["docker", "buildx", "inspect", "--bootstrap"])


def main():
    outs = terraform_outputs(TF_DIR)
    ecr_repo_url = outs["ecr_repo_url"]
    registry = ecr_repo_url.split("/")[0]

    # Primary tag (default: stable). You can still override via IMAGE_TAG.
    primary_tag = os.environ.get("IMAGE_TAG", "stable")

    # Immutable tag for lifecycle pruning + reproducibility
    build_tag = "build-" + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")

    image_primary = f"{ecr_repo_url}:{primary_tag}"
    image_build = f"{ecr_repo_url}:{build_tag}"

    # ECR login
    password = subprocess.check_output(
        ["aws", "ecr", "get-login-password", "--region", REGION],
        text=True,
    )
    run(["docker", "login", "--username", "AWS", "--password-stdin", registry], input_text=password)

    # Multi-arch build & push (portable for all users)
    ensure_buildx()
    run(
        [
            "docker", "buildx", "build",
            "--platform", "linux/amd64,linux/arm64",
            "-f", "docker/Dockerfile",
            "-t", image_primary,
            "-t", image_build,
            "--push",
            ".",
        ],
        cwd=REPO_ROOT,
    )

    print(f"\n✅ Pushed multi-arch image: {image_primary}")
    print(f"✅ Also tagged build image: {image_build}")


if __name__ == "__main__":
    main()