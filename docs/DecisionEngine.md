# Decision Engine

## Purpose

The Decision Engine converts analytical observations into an explainable assessment of directional opportunity and uncertainty. It does not predict outcomes or execute trades. It evaluates whether the current evidence supports a bullish thesis, a bearish thesis, waiting for confirmation, or taking no trade.

StructureIQ v0.4 implements this model in `core/decision_engine.py`. It is the primary source of `/analysis` action and confidence; the earlier scorer remains available only for compatibility.

The Decision Engine answers exactly: **buy, sell, wait, or avoid—and with what confidence?** It does not identify the specific setup, select a broader strategy playbook, or build the trader-facing trade plan.

## Weighted Evidence Model

| Evidence category | Weight |
| --- | ---: |
| Market structure | 35% |
| Multi-timeframe alignment | 25% |
| Support/resistance and liquidity context | 15% |
| Indicators | 15% |
| Risk/reward and volatility | 10% |
| **Total** | **100%** |

Market structure receives the greatest weight because it defines the thesis. Multi-timeframe alignment establishes whether execution context supports or conflicts with that thesis. Context, indicators, and trade quality refine the assessment without replacing the structural foundation.

## Evidence Scoring

Each category produces a normalized directional assessment and an evidence-quality value. A reference representation is a score from `-1.0` to `+1.0`:

- `+1.0`: strong bullish evidence.
- `0.0`: neutral, unavailable, or balanced evidence.
- `-1.0`: strong bearish evidence.

The directional composite is the sum of each category score multiplied by its weight. v0.4 exposes category contributions and total confidence on a `0–100` scale. The legacy top-level API confidence remains `0–10` and is derived by dividing decision confidence by ten.

Missing evidence must not automatically become supportive evidence. The engine should either reduce evidence coverage, lower confidence, or declare the result insufficient according to documented rules.

## Confidence Calculation

Confidence measures the quality and agreement of available evidence, not the probability of a guaranteed outcome. It should account for:

- Magnitude of the weighted composite.
- Agreement among independent categories.
- Data completeness and freshness.
- Structural clarity.
- Material conflicts or invalidation risk.
- Whether risk/reward and volatility conditions are measurable and acceptable.

A strong score with poor data coverage or major category conflict must not receive high confidence. Confidence thresholds and scaling must be versioned, deterministic, and calibrated through testing and backtesting.

## Evidence Ledger

Every decision must retain an evidence ledger containing:

- Category and configured weight.
- Raw observation and source timeframe.
- Directional contribution.
- Evidence quality and availability.
- Human-readable reason.
- Any conflict, warning, or invalidation condition.
- Rule and model version.

The ledger enables the Intelligence/Explanation Engine to explain a result without reconstructing or inventing reasoning.

## Decision States

- **Buy:** bullish evidence clears the directional confidence, structure, and timeframe gates. Execution may still be unavailable downstream.
- **Sell:** bearish evidence clears the equivalent directional gates. Execution may still be unavailable downstream.
- **Wait:** a plausible thesis exists, but confirmation, alignment, or trade quality is insufficient.
- **Avoid:** confidence is below 50 or evidence is too weak to justify a trade thesis. The legacy top-level API maps this to `no_trade`.

Directional score alone is never enough to authorize a buy or sell assessment. Strategy qualification, invalidation, and risk gates remain mandatory.

## Guardrails

- No single indicator can create a decision thesis.
- Higher-timeframe conflict must be visible and appropriately penalized.
- Liquidity sweeps must not be scored as confirmed breaks.
- Poor risk/reward can veto an otherwise strong directional thesis.
- Low volatility may make a setup unproductive; extreme volatility may make it unsafe or unmeasurable.
- The engine must prefer wait or no trade over false precision.
- Outputs are decision support and must not be presented as financial advice or guaranteed signals.

## v0.4 Scoring Rules

Each category contributes no more than its configured weight:

- **Market structure, 35 points:** rewards directional structure, impulse behavior, and a confirming BOS; penalizes opposing structure or CHOCH.
- **Multi-timeframe alignment, 25 points:** scales the v0.3 alignment score into the category weight. Direct conflict and unclear alignment also produce negative evidence.
- **Support/resistance and liquidity, 15 points:** rewards price at a relevant zone. A low sweep supports a bullish reversal thesis and a high sweep supports a bearish reversal thesis; the opposite sweep weakens the trade.
- **Indicators, 15 points:** currently interprets the already-supported RSI context as confirming, weakening, or unavailable evidence. It cannot create the thesis.
- **Risk/reward and volatility, 10 points:** rewards defined and favorable risk/reward. Missing or poor risk/reward reduces the category and creates a risk note. ATR-based volatility quality remains unavailable and is explicitly disclosed rather than assumed.

`ScoreBreakdown.total` is the rounded sum of the five weighted contributions. `EvidenceItem` records category, message, and signed impact, and each item is separated into positive, negative, or neutral evidence on the result.

## v0.4 Action Gates

- Below 50 confidence: `avoid`.
- From 50 through 69.9: `wait`.
- From 70 through 84.9: `buy` or `sell` only when market structure and multi-timeframe direction agree and risk/reward is valid.
- At 85 or above: the explanation may describe high confidence, but the public action remains `buy` or `sell`.
- Conflicting or unclear timeframe alignment cannot produce `buy` or `sell`.
- Mixed alignment can act only when current structure matches the higher-timeframe thesis and current-timeframe confirmation is present.
- Missing risk/reward reduces confidence and creates a risk warning, but final execution readiness is evaluated downstream by Setup and Backtesting.

Every decision includes risk notes, structural invalidation notes, and a human-readable explanation. Confidence describes evidence quality and agreement; it is not a predicted win probability.

## v1.2 Decision Diagnostics, Refined in v1.3

`DecisionResult.decision_diagnostics` exposes the existing action gates without changing their evaluation. It contains the unrounded category sum (`raw_score`), final rounded confidence, intended direction, confidence band, required gates that failed, every gate result, and a readable summary.

Confidence bands are observational labels:

- Below 50: `avoid`.
- 50 through 69.9: `wait`.
- 70 through 84.9: `tradable`, subject to every other required gate.
- 85 through 100: `high_conviction`, which remains uncertain and is not a guarantee.

Required directional gates mirror the current action selector exactly:

- `directional_confidence`: final confidence is at least 70.
- `structure_alignment`: execution structure matches the intended direction.
- `multi_timeframe_alignment`: timeframes align, or mixed context has directional structure and current-timeframe confirmation.

Supporting diagnostics—`conflicting_evidence`, `liquidity_confirmation`, and `indicator_confirmation`—describe evidence but are not standalone action gates. `execution_readiness`, `risk_plan_available`, and `risk_plan_quality` are also non-required at decision time because the Setup Engine and Backtester run afterward. This distinction prevents diagnostics from inventing dependencies or misrepresenting downstream output as a cause of the directional decision.

Each `GateResult` records its name, pass state, whether it is required, observed and expected values, diagnostic impact, and blocking reason. For `wait` and `avoid`, `blocked_by` contains only failed required gates.

## v1.3 Risk/Reward Ownership

The Decision Engine answers whether evidence supports a bullish direction, bearish direction, waiting, or avoidance. Risk/reward remains in its 10% evidence category: favorable ratios strengthen confidence, poor ratios weaken it, and missing ratios now apply a moderate penalty with an explicit execution warning.

Missing or low risk/reward no longer acts as an independent directional veto. This does not make a trade executable. The Setup Engine must still produce entry, stop, target, confirmation, and at least `1.5R`; the Backtester independently validates those fields before simulation.

This boundary allows a strong directional thesis to return buy or sell while its setup remains developing or waiting. Trader-facing output and backtesting continue to withhold action until execution readiness is complete.

## v1.4 Threshold Sensitivity Boundary

Calibration may compare historical raw scores with alternative thresholds of 50, 55, 60, 65, and 70. This is a read-only research calculation over stored diagnostics. The production Decision Engine continues to use 50 for avoid, 70 for directional action, and every existing structure and timeframe gate.

Sensitivity eligibility is not a new decision and is never written back into `/analysis`, backtest outcomes, setup status, or strategy state. An estimated trade candidate must independently pass the recorded execution-readiness snapshot.

## Output Boundary

`DecisionResult` is internal engine output. It contains the directional action, weighted score breakdown, evidence ledger, risk notes, invalidation notes, decision diagnostics, and a factual summary suitable for downstream systems.

This output is intentionally analytical rather than a complete trader experience. A decision can be bullish without a qualified entry setup, and a high confidence score is not permission to trade.

## Relationship to Setup Engine

The Setup Engine runs after the Decision Engine. It uses decision direction and confidence as constraints while checking whether a named setup is actually present.

- `buy` permits evaluation of bullish setup candidates.
- `sell` permits evaluation of bearish setup candidates.
- `wait` permits developing candidates but not entry-ready qualification.
- `avoid` prevents setup qualification.

The Setup Engine may return no qualified setup even when the Decision Engine returns buy or sell. It cannot change the action or confidence.

## Relationship to Analysis/Explanation Engine

The Analysis/Explanation Engine explains the decision after it has received the relevant internal outputs. It translates evidence into plain language, combines the decision with setup and strategy results, and builds entry, invalidation, risk, and checklist views.

It does not recalculate confidence or choose a different action. Wait and avoid reasoning must come from Decision Engine evidence and downstream qualification failures, not from invented narrative.
