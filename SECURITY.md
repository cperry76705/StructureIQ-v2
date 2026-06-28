# Security Policy

## Supported Version

Security fixes are currently targeted at the latest `1.0.x` release line.

## Reporting a Vulnerability

Do not disclose suspected vulnerabilities in a public issue. Use the repository host's private vulnerability-reporting feature when available, or contact the repository owner privately with:

- the affected endpoint, module, and version;
- reproduction steps or a minimal proof of concept;
- the expected impact;
- any suggested mitigation.

Please avoid accessing data that is not yours, disrupting external providers, or including secrets or personal journal content in reports.

## Security Scope

StructureIQ stores journal data locally and queries an external market-data provider. Deployers are responsible for access control, TLS, host hardening, backups, provider terms, log handling, and secret management. The Stable MVP does not include authentication or multi-user isolation and should not be exposed directly to untrusted networks without an appropriate gateway.
