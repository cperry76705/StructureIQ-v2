# Setup Engine

## Purpose

The Setup Engine identifies the specific trade setup represented by current market conditions and determines whether that setup is qualified, developing, invalid, or absent.

It bridges directional decision and trader-facing planning. The Decision Engine may establish a bullish or bearish thesis, but only the Setup Engine determines whether a defined opportunity exists and which conditions remain before entry.

## Responsibilities

The Setup Engine is responsible for:

- Evaluating named setup definitions against internal engine output.
- Distinguishing qualified, developing, invalidated, and absent setups.
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

A setup result should contain:

- Setup type and direction.
- Qualification state: `qualified`, `developing`, `invalidated`, or `absent`.
- Setup quality or confidence distinct from Decision Engine confidence.
- Satisfied conditions.
- Missing entry conditions.
- Failed conditions and rejection reasons.
- Entry trigger and relevant zone.
- Invalidation level and rule.
- Potential target context and minimum risk/reward requirement.
- Supporting and conflicting evidence references.
- Rule version and timeframe metadata.
- A concise factual summary for downstream explanation.

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
- Missing entry, invalidation, or risk information prevents full qualification.
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
