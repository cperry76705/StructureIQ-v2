# Validation Philosophy

ID: VAL-0001  
Title: Validation Philosophy  
Category: Validation  
Status: APPROVED  
Owner: Founder  
Created: 2026-08-09  
Last Updated: 2026-08-09  
Related Entries: [Research Laboratories](../03-engineering/KB-ENG-0004-research-laboratories.md)  
Related ADRs: [ADR-004](../07-decisions/ADR-004-paper-before-live.md), [ADR-013](../07-decisions/ADR-013-research-before-production-change.md)  
Related Releases: None

## Philosophy

StructureIQ uses a research-first validation approach. Proposed changes should be measured before production behavior changes.

Validation should explain both performance and weakness: frequency, expectancy, drawdown, edge decay, execution realism, market regime behavior, and decision quality.

v6.0.19 requires execution changes to begin as measured counterfactuals. Fill tolerance, lifetime, approval-price, and confirmation-market models cannot become runtime behavior from a single sample.
