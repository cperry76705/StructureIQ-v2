# Setup Engine

## Purpose

The Setup Engine identifies the specific trade setup represented by current market conditions and determines whether it is confirmed, developing, waiting for confirmation, invalid, or absent.

It bridges directional decision and trader-facing planning. The Decision Engine may establish a bullish or bearish thesis, but only the Setup Engine determines whether a defined opportunity exists and which conditions remain before entry.

## Responsibilities

The Setup Engine is responsible for:

- Evaluating named setup definitions against internal engine output.
- Distinguishing confirmed, developing, waiting, invalid, and absent setups.
- Recording satisfied, missing, and failed conditions.
- Identifying relevant entry triggers and structural levels.
- Defining setup-specific invalidation.
- Rejecting setups that conflict with the Decision Engine or risk constraints.
- Returning machine-readable qualification evidence for explanation, strategy comparison, journaling, and backtesting.

It does not calculate the directional decision, write trader-facing narrative, select broker orders, or guarantee that a qualified setup will succeed.

## Inputs

The Setup Engine consumes typed internal output, including:

- Decision action, confidence, score breakdown, and evidence.
- Current and higher-timeframe trend and phase.
- Alignment classification and directional bias.
- Confirmed swings, BOS, CHOCH, liquidity sweeps, and structural levels.
- Support and resistance context.
- Indicator confirmation or contradiction.
- Risk/reward and volatility context where available.
- Current-price confirmation state and completed-candle timestamps.

Missing inputs must remain explicitly unavailable. They may reduce qualification but must never be silently inferred.

## Outputs

A `SetupResult` contains:

- `setup_type` and bullish, bearish, or neutral direction.
- `setup_status`: `confirmed`, `developing`, `waiting_for_confirmation`, `invalid`, or `no_setup`.
- `setup_quality_score` from `0–100`, distinct from Decision Engine confidence.
- Entry zone, stop loss, target, and estimated risk/reward when measurable.
- Checklist-style `EntryCondition` items with required, recommended, or optional importance.
- `InvalidationRule` items with optional trigger level and soft or hard severity.
- Supporting evidence, warning notes, and a factual summary.

## Setup Types

### Bullish BOS Retest

Price closes above a confirmed structural high, then returns toward the broken level while bullish context remains valid. Qualification requires the level to hold and the current timeframe to show bullish confirmation.

### Bearish BOS Retest

Price closes below a confirmed structural low, then returns toward the broken level while bearish context remains valid. Qualification requires rejection from the level and bearish confirmation.

### Pullback Continuation

A directional market corrects without invalidating its protected structural level. Qualification requires higher-timeframe direction, an orderly pullback into relevant context, and current-timeframe continuation evidence.

### Range Reversal

Price tests or sweeps a defined range boundary and rejects back toward the range interior. Qualification requires a validated range, boundary interaction, rejection, and acceptable reward toward the opposing range objective.

### Liquidity Sweep Reversal

Price trades through a confirmed swing or liquidity boundary, closes back inside, and provides reversal confirmation. The sweep must support the proposed direction rather than occur against it.

### Compression Breakout

Price contracts within identifiable boundaries and then closes beyond the compression with sufficient expansion and confirmation. A wick alone does not qualify, and failed breaks must be recorded explicitly.

## Setup Validation Rules

Every setup definition must specify:

1. Required market regime and directional context.
2. Required structural event or price-location condition.
3. Required timeframe alignment.
4. Required completed-candle confirmation.
5. Entry zone or trigger.
6. Structural invalidation.
7. Minimum measurable risk/reward.
8. Conditions that reject or defer the setup.

General validation rules:

- `avoid` decisions cannot produce a qualified setup.
- `wait` decisions may produce a developing setup but not an entry-ready recommendation.
- Buy decisions can qualify only bullish setups; sell decisions can qualify only bearish setups.
- Conflicting timeframe alignment prevents qualification unless a future setup definition explicitly and safely supports countertrend behavior.
- A liquidity sweep is not treated as BOS.
- Missing entry zone, stop loss, target, or risk/reward information prevents full qualification.
- Setup rules use completed candles and confirmed structural levels.
- Multiple candidates may be returned, but each must be evaluated independently before strategy comparison.

## Entry Condition Checklist

The Setup Engine produces structured checklist items rather than free-form instructions. A typical checklist includes:

- Directional decision remains valid.
- Higher-timeframe context supports the setup.
- Current-timeframe structure matches the setup direction.
- Required BOS, CHOCH, sweep, retest, or range event is confirmed.
- Price is within the defined entry zone.
- Required candle confirmation has completed.
- Invalidation level is known and has not been breached.
- Risk/reward meets the setup's minimum threshold.
- Volatility and data quality are acceptable or explicitly unresolved.

Each item has a state such as satisfied, pending, failed, or unavailable. The Analysis/Explanation Engine may rephrase these items but cannot change their state.

## Invalidation Rules

Invalidation must be structural and setup-specific. Examples include:

- A bullish setup closes below its protected swing low.
- A bearish setup closes above its protected swing high.
- A BOS retest closes decisively back through the broken level.
- A range reversal closes and accepts outside the range boundary.
- A sweep reversal continues beyond the swept level instead of reclaiming it.
- A compression breakout closes back inside the compression and loses follow-through.

Invalidation is not the same as trade loss. It defines when the analytical setup thesis is no longer valid. If no reliable invalidation can be defined, the setup cannot be fully qualified.

## Relationship to Decision Engine

The Decision Engine runs before the Setup Engine and owns directional action and confidence. The Setup Engine accepts that decision as a constraint.

- The Decision Engine answers: **buy, sell, wait, or avoid?**
- The Setup Engine answers: **which specific setup is present, and are its conditions valid?**

The Setup Engine does not rescore or override the decision. It may determine that no setup qualifies even when the decision is bullish or bearish, in which case the platform should wait.

## Relationship to Analysis/Explanation Engine

The Analysis/Explanation Engine consumes Setup Engine output and converts it into trader-facing language and a checklist-style plan.

It may explain the setup, group conditions into a readable sequence, and highlight missing requirements. It may not invent a setup, mark a pending condition complete, change invalidation, or turn an unqualified setup into a recommendation.

## v0.5 Implementation

The v0.5 implementation lives in `core/setup_engine.py` and supports:

- Bullish and bearish BOS retests.
- Bullish and bearish pullback continuation.
- Long and short range reversals.
- Long and short liquidity-sweep reversals.
- Long and short compression breakouts.
- Explicit `no_valid_setup` output.

Candidate selection prioritizes liquidity sweeps, range-location setups, directional BOS retests, directional pullbacks, and then compression candidates. Every candidate remains constrained by the Decision Engine direction.

A setup is confirmed only when the Decision Engine action permits its direction, its pattern and price-location rules are present, the current timeframe confirms, entry zone, stop loss, and target are all available, structural invalidation holds, and estimated risk/reward is at least `1.5R`. Missing levels or insufficient risk quality keep the setup `developing` or `waiting_for_confirmation`. A `wait` decision can produce only developing or waiting status. An `avoid` decision always produces `no_valid_setup`.

Version 1.3 makes this engine the primary owner of execution-plan readiness. A directional buy or sell from the Decision Engine is necessary but not sufficient for setup confirmation.

## v1.5 Setup-Level Diagnostics

Every engine-generated setup now includes `setup_level_diagnostics`. It records the source of entry, stop, and target; latest confirmed swing levels; nearest support and resistance; and whether the level set is complete, partial, missing, or invalid.

Current source labels reflect the deterministic level builder:

- Bullish entry uses the support zone, stop uses a support-zone extension, and target uses resistance.
- Bearish entry uses the resistance zone, stop uses a resistance-zone extension, and target uses support.
- Missing fields are labeled `unavailable`; unresolved directional context is explicit.

Level quality describes availability and geometry, not setup profitability. A complete level set can still fail the `1.5R` requirement, while an invalid set has directionally inconsistent price ordering.

## v1.6 Instrument-Aware Levels

Level construction now infers asset class, decimal precision, tick or pip size, and a minimum zone width from the requested symbol. Zone half-width uses the smaller of a percentage-based width and one quarter of recent average true range, bounded by the instrument minimum.

EUR-USD and GBP-USD preserve five decimals; BTC-USD and ETH-USD preserve two. Risk/reward is calculated from numeric entry, stop, and target geometry before those values are formatted for API output. The `1.5R` requirement and setup-confirmation rules are unchanged.

Compression is approximated from contraction in recent candle ranges relative to a prior baseline. A compression candidate remains developing until price closes beyond the preceding compression range.

The current BOS-retest implementation uses the relevant support or resistance zone as a proxy for the broken level because the Market Structure Engine does not yet expose a dedicated persisted BOS level. This assumption is explicit and should be replaced when structural-level provenance is expanded.

## v1.9 Candidate Coverage Diagnostics

The production first-match selector is unchanged. A separate observational pass enumerates plausible BOS retest, pullback, range, liquidity-sweep, and compression candidates supported by current context. Each candidate records selection, status, direction, level availability, geometry, calculated R:R, minimum-R result, quality, and its primary blocker.

A non-selected candidate is counted as missed executable only when it independently passes the current direction, confirmation, level, geometry, and `1.5R` gates. Diagnostics cannot promote a setup or force a trade. BOS location failures are labeled `missing_retest_level`; bullish and bearish zone failures remain distinguishable.

## v2.0 Bearish BOS Retest Selection

When a bearish BOS retest and liquidity-sweep reversal short coexist, the Setup Engine compares them instead of unconditionally returning the sweep first. Bearish BOS can win only with bearish structure, a BOS among the three most recent events, a resistance retest, sell permission, confirmation, aligned-bearish or mixed-bearish context, valid production geometry, and at least `1.5R`.

Bearish continuation evidence favors BOS; a latest liquidity sweep during `reversal_attempt` favors the sweep. The winner receives explicit supporting evidence. An otherwise executable loser receives `stronger_candidate_selected`, remains counted as a missed executable candidate, and cannot execute. No candidate is promoted when a hard gate fails.
