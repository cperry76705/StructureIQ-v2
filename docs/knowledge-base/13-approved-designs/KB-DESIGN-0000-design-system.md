# KB-DESIGN-0000 — StructureIQ Design System

Design ID: KB-DESIGN-0000  
Page name: StructureIQ Design System  
Version: 1.0  
Status: APPROVED  
Purpose: Define the shared visual language derived from the approved StructureIQ v1.0 PNG designs.  
Implementation Status: APPROVED DESIGN / FRONTEND IMPLEMENTED / VISUAL FIDELITY REVIEW REQUIRED

## Visual Source of Truth

The approved PNG files in this directory are the authoritative visual specification for the frontend. This document extracts the shared design system; it does not replace the screenshots.

## Visual Language

- Dark navy/black application background.
- Elevated dark card surfaces with subtle blue borders.
- Bright StructureIQ blue for primary actions, active navigation, links, and key emphasis.
- AI purple accents for AI authority, AI Partner, coaching, and intelligence labels.
- Success green for positive status, market-open state, valid conditions, and completed steps.
- Warning amber/orange for caution, validation, watch states, and medium-impact events.
- Critical red for avoid states, invalidation, risk alerts, and negative outcomes.
- Muted slate/gray for secondary text, disabled states, supporting labels, and quiet UI.
- White primary text with strong financial-SaaS hierarchy.
- Rounded card corners with restrained shadows and glows.
- Dense but clean dashboard spacing.
- Institutional, premium, disciplined, modern tone.

## Implementation Notes

Frontend implementation should rebuild the approved screens using React, HTML, CSS, and reusable components. The PNGs must not be used as full-page UI backgrounds.

## Related KB-PROD Entry

- [Product Vision](../02-product/KB-PROD-0001-product-vision.md)

## Related ADRs

- [ADR-022 — AI-First Market Research Workspace](../07-decisions/ADR-022-ai-first-market-research-workspace.md)
