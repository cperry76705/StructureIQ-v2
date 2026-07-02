# Git Operations

[Operations index](README.md) · [Releases](Releases.md) · [Troubleshooting](Troubleshooting.md)

## Recommended Workflow

```powershell
git status
git pull
git diff
python -m pytest -q
python start.py --validate
git add .
git diff --staged
git commit -m "Concise, specific change"
git push
```

Inspect the working tree and staged changes. Do not commit `.venv`, generated reports, journals, account state, logs, secrets, or credentials.

## Core Commands

- `git status`: show branch and working-tree state.
- `git add .`: stage all changes; use only after reviewing them.
- `git commit -m "message"`: create a local commit.
- `git push`: publish the current branch.
- `git pull`: fetch and integrate the upstream branch.
- `git log --oneline -10`: inspect recent commits.

## Recovering After Codespaces

1. Confirm Codespaces work was committed and pushed.
2. Locally run `git status`; preserve or commit local work first.
3. Check out the matching branch and run `git pull`.
4. Recreate `.venv` if necessary.
5. Run tests and `python start.py --validate`.

Codespaces may suspend or expire. GitHub commits are the durable handoff.

## Recovering After Local Changes

Use `git diff` to understand the changes. Commit a coherent checkpoint before pulling if the work must survive. For genuinely temporary work:

```powershell
git stash push -m "temporary local work"
git pull
git stash pop
```

Never use a destructive reset without confirming the exact files and backup strategy.

## Merge Conflicts

1. Run `git status` to list conflicts.
2. Resolve `<<<<<<<`, `=======`, and `>>>>>>>` sections deliberately.
3. Stage each resolved file with `git add <file>`.
4. Run tests and validation.
5. Complete the merge commit and push.

If intent is unclear, ask the author rather than guessing.
