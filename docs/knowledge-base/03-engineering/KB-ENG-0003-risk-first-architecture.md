# Risk-First Architecture

ID: KB-ENG-0003  
Title: Risk-First Architecture  
Category: Engineering  
Status: APPROVED  
Owner: Founder  
Created: 2026-08-09  
Last Updated: 2026-08-09  
Related Entries: [System Architecture](KB-ENG-0001-system-architecture.md), [Performance Positioning](../05-business/KB-BIZ-0004-performance-positioning.md)  
Related ADRs: [ADR-004](../07-decisions/ADR-004-paper-before-live.md), [ADR-008](../07-decisions/ADR-008-risk-first-engineering.md), [ADR-014](../07-decisions/ADR-014-expand-opportunity-set-before-lowering-quality.md)  
Related Releases: None

## Principles

Risk management is a first-class subsystem. Trade generation must remain separate from user-level execution approval.

Paper trading and validation precede live execution. The platform should not lower standards simply to increase trade count. If more opportunity is needed, expand the opportunity universe before weakening quality thresholds.
