# System Architecture

ID: KB-ENG-0001  
Title: System Architecture  
Category: Engineering  
Status: APPROVED  
Owner: Founder  
Created: 2026-08-09  
Last Updated: 2026-08-09  
Related Entries: [Risk-First Architecture](KB-ENG-0003-risk-first-architecture.md), [Research Laboratories](KB-ENG-0004-research-laboratories.md)  
Related ADRs: [ADR-004](../07-decisions/ADR-004-paper-before-live.md), [ADR-008](../07-decisions/ADR-008-risk-first-engineering.md)  
Related Releases: [v6.0.13](../11-releases/REL-v6.0.13.md), [v6.0.14](../11-releases/REL-v6.0.14.md)

## Current Architecture

StructureIQ is a modular backend intelligence service.

Current completed backend capabilities include analysis, research, calibration, adaptive routing, setup quality, execution modeling, paper trading, validation, reporting, observability, and continuous autonomous paper trading runtime.

The architecture separates decision intelligence, risk, execution, validation, and user-specific orchestration so each concern can evolve without weakening trading standards.

## v6.0.14 Architecture Update

The architecture now includes a centralized Symbol Registry and a read-only Opportunity Coverage Engine. The registry keeps canonical StructureIQ symbols stable while mapping provider symbols deterministically. Opportunity Coverage consumes existing candidate diagnostics and paper journal state to report pipeline attrition without altering trading behavior.
