# Security Policy

## Reporting a vulnerability

If you discover a security issue, please do **not** open a public GitHub issue.

Instead, email the maintainer with:
- A clear description of the issue
- Steps to reproduce (or a proof-of-concept)
- Impact assessment (what an attacker can do)

## Sensitive data

This project deals with load testing and may involve:
- Target API endpoints
- API keys / bearer tokens
- Request headers and payloads

Do not paste secrets into issues, PRs, logs, or committed request files.
Use `loadtest/utils/*.local.json` for local-only request configs (ignored by git).

## Scope

Security issues relevant to:
- Infrastructure definitions (Terraform)
- Container image / dependencies
- Helper tooling

Out-of-scope:
- Misuse of load testing against third-party systems
