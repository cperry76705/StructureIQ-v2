# AI Principles

ID: KB-AI-0001  
Title: AI Principles  
Category: AI  
Status: APPROVED  
Owner: Founder  
Created: 2026-08-09  
Last Updated: 2026-08-09  
Related Entries: [Core Philosophy](../01-company/KB-COMP-0004-core-philosophy.md), [Market Intelligence Workspace](../02-product/KB-PROD-0006-market-intelligence-workspace.md), [Trade Intelligence Workspace](../02-product/KB-PROD-0008-trade-intelligence.md)  
Related ADRs: [ADR-003](../07-decisions/ADR-003-explainable-ai.md), [ADR-017](../07-decisions/ADR-017-ai-authority-model.md), [ADR-022](../07-decisions/ADR-022-ai-first-market-research-workspace.md)  
Related Releases: None

## Principles

- Explain uncertainty.
- Say "wait" when evidence is insufficient.
- Do not pretend certainty.
- Explain every important decision.
- Protect user capital and discipline.
- Use automation to enhance education, not eliminate it.

## Market Intelligence AI

In the Market Intelligence workspace, AI should synthesize market conditions before the user is asked to interpret raw charts. It may summarize structure, sessions, volatility, market drivers, event risk, important changes, and attention priorities.

Market Intelligence explanations should be user-facing reasoning. They should explain what StructureIQ sees and why it matters without exposing source code, sensitive implementation details, or confidential proprietary logic.

## Trade Intelligence AI

In Trade Intelligence, AI ranks current opportunities, chooses the initial AI Top Pick, explains supporting evidence and counter-evidence, monitors opportunity lifecycle context, and guides the user without removing selection control. The user may override the initial selection at any time and explore other supported or clearly labeled exploratory markets.

Confidence must be explainable rather than presented only as an unexplained percentage. User-facing explanation is required; confidential source code, proprietary prompts, system instructions, security architecture, and sensitive model internals are not disclosed.
