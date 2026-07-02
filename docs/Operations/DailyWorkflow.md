# Daily Operating Workflow

[Operations index](README.md) · [Paper trading](PaperTrading.md) · [Commands](Commands.md)

## Morning

1. Activate `.venv`.
2. Pull intentional remote changes and inspect `git status`.
3. Run `python start.py --validate`.
4. Start the API or planned paper session.
5. Review `/reports/daily`, `/dashboard/overview`, `/dashboard/readiness`, `/dashboard/risks`, and `/paper-journal/summary`.
6. Resolve every FAIL and record WATCHLIST findings.

## During the Day

- Run labeled, controlled paper sessions.
- Watch `/continuous-paper/status` and `/system/health`.
- Investigate pause reasons instead of repeatedly resuming.
- Use lifecycle and monitor endpoints to inspect candidate flow.
- Avoid modifying code inside the process running a long paper session.

## Evening

1. Stop or confirm completion of the paper session.
2. Generate or inspect the daily report.
3. Review journal totals, warnings, rule violations, and paper risk.
4. Run:

   ```powershell
   python -m pytest -q
   python start.py --validate
   ```

5. Inspect `git diff`, commit a coherent change, and push.
6. Confirm generated artifacts remain ignored.

## Daily Close Checklist

- [ ] No unexpected running session
- [ ] No unresolved validation FAIL
- [ ] Health and risk warnings reviewed
- [ ] Daily report available or absence explained
- [ ] Journal and account state reviewed
- [ ] Tests pass for repository changes
- [ ] Git working tree understood
