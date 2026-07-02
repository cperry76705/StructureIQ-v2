# Release Operations

[Operations index](README.md) · [Git](Git.md) · [Changelog](../Changelog.md)

## Recommended Sequence

1. Confirm scope and repository state:

   ```powershell
   git status
   git pull
   ```

2. Implement and document the release intentionally.
3. Update `APP_VERSION`, changelog, roadmap, API docs, and README.
4. Run:

   ```powershell
   python -m pytest -q
   python start.py --validate
   ```

5. When runtime behavior changed, run a controlled paper validation:

   ```powershell
   python start.py --paper --minutes 30 --label "Release Validation"
   ```

6. Review dashboard readiness, risks, journal, and reports.
7. Inspect and stage:

   ```powershell
   git status
   git diff
   git add .
   git diff --staged
   ```

8. Commit and push:

   ```powershell
   git commit -m "Release StructureIQ vX.Y.Z"
   git push
   ```

9. Tag only after the pushed commit and evidence are verified.

## Semantic Versioning

- `6.0.3 → 6.0.4`: backward-compatible patch or documentation correction.
- `6.0.3 → 6.1.0`: backward-compatible new capability.
- `6.0.3 → 7.0.0`: intentionally breaking public contract or major boundary.

Never change a version without documenting it. Never present paper or research results as proof of profitability.

## Release Evidence

Record the test count, validation status, known limitations, and whether production behavior changed. Keep generated reports local unless deliberately sanitized.
