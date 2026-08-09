# ADR-025 — Decision Quality Over Outcome-Only Performance Evaluation

ID: ADR-025  
Title: Decision Quality Over Outcome-Only Performance Evaluation  
Category: Decision  
Status: APPROVED  
Owner: Founder  
Created: 2026-08-09  
Last Updated: 2026-08-09  
Related Entries: [Performance Intelligence](../02-product/KB-PROD-0009-performance-intelligence.md)  
Related ADRs: [ADR-003](ADR-003-explainable-ai.md), [ADR-018](ADR-018-command-center-decision-focus.md), [ADR-021](ADR-021-subscription-tiers-based-on-execution-authority.md)  
Related Releases: None

## Context

Broker-style P&L and win-rate reporting cannot distinguish repeatable skill from luck, disciplined losses from execution mistakes, or correct skips from missed valid opportunities. StructureIQ needs a performance model aligned with education, discipline, explainability, and long-term improvement.

## Decision

StructureIQ Performance Intelligence will evaluate trading process and Decision Quality alongside financial outcomes rather than treating P&L or Win Rate as the primary measure of trading quality.

Decision Quality, Discipline Intelligence, Missed Opportunity Intelligence, and AI Coach will provide the approved behavioral framework. Exact production scores and classifications remain subject to future engine definition and validation.

## Reasoning

1. Profitable trades can result from poor decisions.
2. Losing trades can result from disciplined, valid decisions.
3. StructureIQ's mission includes education and discipline, not just execution.
4. Users need feedback on repeatable behavior.
5. P&L-only analysis reinforces harmful short-term thinking.
6. Decision-quality analysis supports coaching and continuous improvement.
7. The approach creates clear differentiation from broker-style performance pages.

## Consequences

- Decision Quality is more prominent than P&L in Performance Intelligence.
- Traditional metrics remain available in Performance Summary as supporting evidence.
- Evaluation uses information available at decision time to limit hindsight bias.
- Good losses, bad wins, correct skips, execution misses, and override quality are conceptually distinct.
- This ADR approves the product framework, not an unvalidated scoring formula or implemented engine behavior.
