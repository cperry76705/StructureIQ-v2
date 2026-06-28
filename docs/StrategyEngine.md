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

`StrategyResult` contains:

- Preferred strategy or `no_strategy`.
- Ranked `StrategyCandidate` items.
- Alignment with the Decision and Setup results.
- A factual selection summary for the Explanation Engine.

Each candidate contains direction, status, `0–100` score, score breakdown, supporting and opposing evidence, required conditions, invalidation, and notes.

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

Version 0.7 is implemented in `core/strategy_engine.py`. The existing strategy router remains compatibility logic and is not used by the primary analysis path.

## v0.7 Scoring Model

Every playbook is scored using five bounded components:

| Component | Maximum |
| --- | ---: |
| Structure fit | 25 |
| Timeframe fit | 25 |
| Setup fit | 25 |
| Risk fit | 15 |
| Indicator confirmation | 10 |
| **Total** | **100** |

- **Structure fit** measures trend, phase, BOS, range-boundary, sweep, or compression relevance.
- **Timeframe fit** rewards directional alignment or appropriate range context and penalizes conflict or uncertainty.
- **Setup fit** gives the greatest credit when the selected Setup Engine result directly maps to the playbook.
- **Risk fit** evaluates the existing estimated risk/reward without inventing new levels.
- **Indicator confirmation** consumes existing indicator evidence and cannot create a strategy independently.

Candidates are returned in descending score order. A candidate must score at least 50, match the Decision Engine direction, and remain consistent with the Setup Engine direction to become the preferred strategy. An avoid decision rejects every candidate. An invalid or absent setup prevents strategy preference.

For buy or sell decisions with confirmed setups, the selected candidate may be marked `preferred`. Under a wait decision, the leading candidate remains `developing` or `viable`; strategy ranking never upgrades it to an actionable decision.

## Setup-to-Strategy Mapping

| Setup type | Broader strategy |
| --- | --- |
| Bullish or bearish BOS retest | Breakout continuation |
| Bullish or bearish pullback continuation | Pullback continuation |
| Long or short range reversal | Range reversal |
| Long or short liquidity-sweep reversal | Liquidity-sweep reversal |
| Long or short compression breakout | Compression breakout |

Trend continuation remains a broader competing playbook when directional structure and timeframe context support it.

## Known Limitations

- Candidate weights and thresholds are deterministic heuristics and are not yet calibrated through backtesting.
- Production ranking compares one selected setup against broader playbooks. Version 1.9 exposes additional Setup Engine candidates only to diagnostics; they do not enter strategy selection.
- Version 2.0 leaves Strategy Engine scoring unchanged. A selected bearish BOS retest maps to `breakout_continuation`; a retained sweep maps to `liquidity_sweep_reversal`. Their conservative comparison happens upstream and cannot bypass strategy eligibility.
- Indicator fit currently reflects the existing RSI confirmation only.
- Risk fit uses the Setup Engine's approximate risk/reward.
- Market-regime history and performance statistics belong to later journal/backtesting work.
