# Contributing to the StructureIQ Knowledge Base

ID: KB-ROOT-0003  
Title: Knowledge Base Contribution Rules  
Category: Knowledge Base  
Status: APPROVED  
Owner: Founder  
Created: 2026-08-09  
Last Updated: 2026-08-09  
Related Entries: [README.md](README.md), [INDEX.md](INDEX.md)  
Related ADRs: [ADR-020](07-decisions/ADR-020-knowledge-base-source-of-truth.md)  
Related Releases: None

## Rules

- Do not add unsupported facts.
- Mark uncertain details as `Pending historical reconstruction.`
- Do not rewrite historical records without documenting the revision.
- Use ADRs for meaningful architecture, product, AI, or business decisions.
- Use relative Markdown links.
- Keep current architecture separate from historical narrative.
- Do not store secrets, tokens, broker credentials, API keys, customer PII, or proprietary model secrets.
- Update [INDEX.md](INDEX.md) when files are added.

## Documentation Workflow

1. A major decision occurs.
2. The relevant Knowledge Base entry is updated.
3. An ADR is added when reasoning changes.
4. The release entry is updated for code changes.
5. Generated Bibles/manuals are updated from the Knowledge Base.
6. The git commit includes documentation changes.
