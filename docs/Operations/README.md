# StructureIQ Operations Manual

## Purpose and Audience

This manual is the operational source of truth for running, validating, reviewing, troubleshooting, and releasing StructureIQ. It is for engineers and operators maintaining the repository or running local paper sessions. StructureIQ remains decision-support and paper-trading software; these procedures do not connect to a live broker.

## Recommended Daily Workflow

1. Activate the virtual environment and run `python start.py --validate`.
2. Start the API or a controlled, labeled paper session.
3. Review system health, dashboard readiness, journal activity, and reports.
4. Stop or pause paper sessions before maintenance.
5. Run tests and validation before committing changes.
6. Review the daily report, then commit and push intentional changes.

See [Daily Workflow](DailyWorkflow.md) for the checklist and [COMMANDS.md](../../COMMANDS.md) for copy/paste commands.

## Manual Contents

- [Startup and local environment](Startup.md)
- [Complete command reference](Commands.md)
- [Git operating procedures](Git.md)
- [Paper-trading operations](PaperTrading.md)
- [Daily operating workflow](DailyWorkflow.md)
- [Release procedure](Releases.md)
- [Troubleshooting and recovery](Troubleshooting.md)
- [Operational architecture overview](ArchitectureOverview.md)

## Operating Principles

- Treat WATCHLIST as a review requirement, not an automatic failure.
- Do not bypass FAIL, account-risk locks, or runtime pause reasons.
- Keep auto-approval disabled unless an approved paper-only test requires it.
- Never commit generated journals, reports, account state, logs, secrets, or credentials.
- Use localhost in browsers even though Uvicorn binds to `0.0.0.0`.
