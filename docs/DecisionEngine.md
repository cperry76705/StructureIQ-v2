# Decision Engine

## Purpose

The Decision Engine converts analytical observations into an explainable assessment of directional opportunity and uncertainty. It does not predict outcomes or execute trades. It evaluates whether the current evidence supports a bullish thesis, a bearish thesis, waiting for confirmation, or taking no trade.

StructureIQ v0.4 implements this model in `core/decision_engine.py`. It is the primary source of `/analysis` action and confidence; the earlier scorer remains available only for compatibility.

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

- **Buy:** bullish evidence exceeds the configured threshold, confidence and data coverage are sufficient, a qualified strategy exists, and risk conditions are acceptable.
- **Sell:** bearish evidence exceeds the configured threshold under equivalent requirements.
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
- Missing or sub-1:1 risk/reward blocks an actionable decision even when the aggregate score is otherwise sufficient.

Every decision includes risk notes, structural invalidation notes, and a human-readable explanation. Confidence describes evidence quality and agreement; it is not a predicted win probability.
