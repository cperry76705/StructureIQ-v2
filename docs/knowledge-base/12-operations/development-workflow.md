# Development Workflow

ID: OPS-0001  
Title: Development Workflow  
Category: Operations  
Status: APPROVED  
Owner: Founder  
Created: 2026-08-09  
Last Updated: 2026-08-09  
Related Entries: [Development Environment Lessons](../03-engineering/KB-ENG-0005-development-environment-lessons.md)  
Related ADRs: [ADR-020](../07-decisions/ADR-020-knowledge-base-source-of-truth.md)  
Related Releases: [v6.0.17](../11-releases/REL-v6.0.17.md)

## Workflow

Use a clean workspace, verify the active repository path, avoid duplicate project folders, keep `.venv` and pycache artifacts ignored, run tests before release claims, and commit/push regularly.

For recovery-test harness work, test stale snapshot, incomplete run, ambiguous current-run, explicit run ID, and cleanup scoping behavior before trusting restart-validation results.
