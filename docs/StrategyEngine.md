# Strategy Engine

## Purpose

The Strategy Engine selects and compares broader trading playbooks after the Setup Engine has evaluated specific opportunities. It helps StructureIQ decide how a qualified or developing setup fits the surrounding market regime.

A setup is a concrete pattern with explicit conditions. A strategy is the broader playbook for handling that pattern, including whether continuation, reversal, breakout, range, or observation is the most appropriate approach.

## Responsibilities

The Strategy Engine:

- Consumes qualified and developing setup candidates.
- Compares valid playbooks for the current regime.
- Ranks approaches using Decision Engine confidence, setup quality, alignment, and risk context.
- Identifies when observation is preferable to participation.
- Records why one playbook is preferred over another.
- Produces structured strategy output for explanation, journaling, and backtesting.

It does not detect raw structure, calculate the directional decision, qualify setup conditions, or write the final trader-facing plan.

## Inputs

- Decision action, confidence, and evidence.
- One or more Setup Engine results.
- Market regime, trend, phase, and structural events.
- Multi-timeframe alignment.
- Risk/reward, volatility, and data-quality context.
- Strategy configuration and version.

## Outputs

- Recommended playbook, or observation/no-playbook.
- Ranked alternative playbooks.
- Referenced setup candidates.
- Suitability score and comparison reasons.
- Required conditions and disqualifiers.
- Risk posture and regime assumptions.
- Rule and configuration version.

## Initial Playbook Families

- Trend continuation.
- Pullback continuation.
- Breakout continuation.
- Range rotation or reversal.
- Liquidity-driven reversal.
- Compression breakout.
- Observation while conditions develop.

These families organize qualified setups; they do not replace setup definitions.

## Selection Rules

- Strategy evaluation occurs after Setup Engine qualification.
- An invalidated or absent setup cannot support a strategy recommendation.
- A developing setup may support an observation playbook but not an entry-ready plan.
- The selected playbook must respect Decision Engine direction and confidence.
- A strategy cannot override structural invalidation or minimum risk requirements.
- Competing playbooks must expose their supporting evidence and tradeoffs.
- No valid edge produces observation, wait, or avoid—not a forced strategy.

## Relationship to Setup Engine

The Setup Engine answers which specific patterns are present and whether their rules are satisfied. The Strategy Engine then compares the broader ways those valid patterns could be approached.

This ordering prevents a strategy preference from bending market evidence to manufacture a setup.

## Relationship to Decision Engine

The Decision Engine owns buy, sell, wait, or avoid and the associated confidence. The Strategy Engine treats that result as a boundary. It may recommend among compatible playbooks but cannot change the decision.

## Relationship to Analysis/Explanation Engine

The Analysis/Explanation Engine presents the selected playbook, qualified setup, entry conditions, invalidation, risk notes, and alternatives in trader-facing language. It explains Strategy Engine output without recomputing rankings or inventing a recommendation.

## Current Status

The existing strategy router is foundational compatibility logic, not the completed Strategy Engine defined here. The full engine is planned for version 0.7, after Setup Engine and Analysis/Explanation Engine contracts are established.
