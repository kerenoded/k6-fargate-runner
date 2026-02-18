# Security Policy

## Reporting a vulnerability

If you discover a security issue, please do **not** open a public GitHub issue.

Instead, use **[GitHub's private vulnerability reporting](https://github.com/kerenoded/k6-fargate-runner/security/advisories/new)**:

1. Go to the link above (or: repository → Security tab → "Report a vulnerability")
2. Include:
   - A clear description of the issue
   - Steps to reproduce (or a proof-of-concept)
   - Impact assessment (what an attacker can do)

GitHub will notify the maintainer privately and keep the report confidential until a fix is published.

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
