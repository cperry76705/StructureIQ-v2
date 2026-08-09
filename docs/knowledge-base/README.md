# StructureIQ Knowledge Base v1.4

ID: KB-ROOT-0001  
Title: StructureIQ Knowledge Base  
Category: Knowledge Base  
Status: APPROVED  
Owner: Founder  
Created: 2026-08-09  
Last Updated: 2026-08-09  
Related Entries: [INDEX.md](INDEX.md)  
Related ADRs: [ADR-020](07-decisions/ADR-020-knowledge-base-source-of-truth.md)  
Related Releases: None

## Purpose

The StructureIQ Knowledge Base is the version-controlled source of truth for company, product, engineering, AI, business, validation, research, roadmap, release, operational, and decision knowledge.

It exists so the project does not depend on memory, scattered chat history, or undocumented assumptions.

## Folder Structure

- `01-company/` — mission, vision, founder story, philosophy, success definition.
- `02-product/` — product vision, landing page direction, Command Center, Market Intelligence, plans, AI partnership.
- `03-engineering/` — architecture, market structure, risk, research labs, environment lessons.
- `04-ai/` — AI behavior principles and trade lifecycle philosophy.
- `05-business/` — commercial model, multitenancy, growth, positioning.
- `06-timeline/` — chronological project history.
- `07-decisions/` — ADRs for meaningful architectural/product decisions.
- `08-validation/` — validation philosophy and major validation tracks.
- `09-research/` — research topic notes.
- `10-roadmap/` — current roadmap.
- `11-releases/` — release knowledge entries.
- `12-operations/` — development, documentation, release, and validation workflows.
- `templates/` — reusable entry templates.

## Naming Convention

Use stable IDs and descriptive filenames:

```text
KB-COMP-0001-company-mission.md
ADR-001-original-intellectual-property.md
TL-0001-initial-ai-trading-bot-question.md
VAL-0001-validation-philosophy.md
REL-v6.0.13.md
```

## ID System

- `KB-COMP` — company knowledge.
- `KB-PROD` — product knowledge.
- `KB-ENG` — engineering knowledge.
- `KB-AI` — AI behavior knowledge.
- `KB-BIZ` — business knowledge.
- `TL` — timeline entries.
- `ADR` — architecture/product/business decisions.
- `VAL` — validation entries.
- `REL` — releases.
- `OPS` — operations guides.

## Creating New Entries

1. Copy the closest template from [templates](templates/).
2. Assign the next stable ID.
3. Add metadata at the top.
4. Link related entries, ADRs, and releases.
5. Update [INDEX.md](INDEX.md).
6. Commit the documentation together with the related decision or release.

## Cross-References

Use relative Markdown links so the knowledge base works in GitHub, VS Code, and local Markdown readers.

## Relationship to Future Bibles and Manuals

The Knowledge Base is the source material for:

- Founder Manifesto
- StructureIQ Chronicles
- Engineering Bible
- Product Design Bible
- Business Bible
- Release Journal
- AI Behavior & Decision Bible
- Operating Manual

Those artifacts should be generated or updated from this Knowledge Base, not treated as separate competing sources of truth.
