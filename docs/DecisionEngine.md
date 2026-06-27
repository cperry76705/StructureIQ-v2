# Decision Engine

## Purpose

The Decision Engine converts analytical observations into an explainable assessment of directional opportunity and uncertainty. It does not predict outcomes or execute trades. It evaluates whether the current evidence supports a bullish thesis, a bearish thesis, waiting for confirmation, or taking no trade.

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

The directional composite is the sum of each category score multiplied by its weight. Implementations may expose a user-facing scale such as `0–10` or `0–100`, but must retain the normalized internal contributions for auditability.

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
- **No trade:** evidence is materially conflicting, data is unreliable, no strategy qualifies, or risk constraints fail.

Directional score alone is never enough to authorize a buy or sell assessment. Strategy qualification, invalidation, and risk gates remain mandatory.

## Guardrails

- No single indicator can create a decision thesis.
- Higher-timeframe conflict must be visible and appropriately penalized.
- Liquidity sweeps must not be scored as confirmed breaks.
- Poor risk/reward can veto an otherwise strong directional thesis.
- Low volatility may make a setup unproductive; extreme volatility may make it unsafe or unmeasurable.
- The engine must prefer wait or no trade over false precision.
- Outputs are decision support and must not be presented as financial advice or guaranteed signals.
