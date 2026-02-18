# Contributing

Thanks for considering contributing.

## Contribution guidelines

This project prioritizes:
- Reproducibility of load tests
- Minimal operational complexity
- Cost-efficient AWS usage
- Clear, debuggable tooling

Please avoid introducing heavy dependencies or infrastructure changes
without discussing the tradeoffs.

## Development setup

Prereqs:
- Terraform
- AWS CLI
- Docker + buildx
- Python 3.11+

Setup:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r tools/requirements.txt -r tools/requirements-dev.txt
```

## Quality checks

Terraform:
```bash
terraform -chdir=infra/terraform fmt -check -recursive
terraform -chdir=infra/terraform init -backend=false -input=false
terraform -chdir=infra/terraform validate -no-color
```

Python:
```bash
python3 -m compileall -q tools uploader loadtest
ruff check --select F tools uploader loadtest
```

## Submitting changes

- Keep changes small and focused.
- Update README when you change behavior/flags.
- Do not commit `test-results/`, `.venv/`, `.terraform/`, or any `*.tfstate` files.
- Do not commit real target URLs or secrets in request templates.
