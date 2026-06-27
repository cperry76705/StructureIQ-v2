# Market Structure

## Purpose

Market structure is the primary analytical language of StructureIQ. It describes observable relationships among price swings, breaks, reactions, and market phases. All classifications are timeframe-specific and should be based on completed data under deterministic confirmation rules.

## Swing Definitions

### Swing High

A confirmed local price peak whose high is greater than the highs in a configured number of completed candles on both sides. Because confirmation requires candles to its right, a swing high is recognized with an intentional delay.

### Swing Low

A confirmed local price trough whose low is lower than the lows in a configured number of completed candles on both sides. It is recognized only after the required confirmation candles have completed.

### Higher High (HH)

A confirmed swing high above the preceding comparable confirmed swing high. It indicates upward structural progression but does not, by itself, establish a complete bullish trend.

### Higher Low (HL)

A confirmed swing low above the preceding comparable confirmed swing low. In a bullish sequence, it represents defended demand and a potential continuation base.

### Lower High (LH)

A confirmed swing high below the preceding comparable confirmed swing high. In a bearish sequence, it represents failed upward progression and a potential continuation base for sellers.

### Lower Low (LL)

A confirmed swing low below the preceding comparable confirmed swing low. It indicates downward structural progression but does not, by itself, establish a complete bearish trend.

## Structural Events

### Bullish Break of Structure (Bullish BOS)

A completed candle closes above the relevant confirmed swing high in a market already exhibiting bullish structure. It is continuation evidence. A wick above the level without a close does not qualify as a BOS.

### Bearish Break of Structure (Bearish BOS)

A completed candle closes below the relevant confirmed swing low in a market already exhibiting bearish structure. It is continuation evidence. A wick below the level without a close does not qualify as a BOS.

### Bullish Change of Character (Bullish CHOCH)

A completed candle closes above the relevant lower high or protected structural high after established bearish structure. It is early evidence that bearish control may be failing, not proof that a bullish trend is established.

### Bearish Change of Character (Bearish CHOCH)

A completed candle closes below the relevant higher low or protected structural low after established bullish structure. It is early evidence that bullish control may be failing, not proof that a bearish trend is established.

### Liquidity Sweep High

Price trades above a relevant confirmed swing high, then closes back below that level. The wick demonstrates that liquidity above the high was reached, while the close back inside distinguishes a sweep from a confirmed bullish break.

### Liquidity Sweep Low

Price trades below a relevant confirmed swing low, then closes back above that level. The wick demonstrates that liquidity below the low was reached, while the close back inside distinguishes a sweep from a confirmed bearish break.

## Market Phases

### Pullback

A corrective move against the prevailing directional structure that does not invalidate its protected structural level. A pullback generally shows less directional progress than the impulse it retraces.

### Impulse

A decisive directional move characterized by strong price displacement, structural progress, and limited overlap relative to recent price action. An impulse often creates a new structural extreme or confirms a break.

### Range

A bounded market state in which price repeatedly rotates between identifiable support and resistance without sustained structural progression. Break attempts that close back inside remain range behavior until confirmed otherwise.

### Compression

A contraction in price movement, range, or volatility, often with overlapping candles and converging structural boundaries. Compression signals reduced expansion and stored potential, but it does not determine the direction of a future break.

### Expansion

An increase in price range, displacement, or volatility that moves price away from a prior balance or compression area. Expansion is directional evidence only when evaluated with closing behavior and surrounding structure.

## Classification Rules

- A bullish trend generally requires a meaningful sequence of higher highs and higher lows, supported by bullish continuation behavior.
- A bearish trend generally requires a meaningful sequence of lower highs and lower lows, supported by bearish continuation behavior.
- A range requires repeated boundary interaction and insufficient directional follow-through.
- CHOCH is a warning of possible transition; subsequent structure must confirm or reject it.
- BOS and sweeps are mutually distinct at the tested level: closing through supports a break, while closing back inside supports a sweep.
- When evidence is insufficient or contradictory, the correct classification is unclear rather than forced.

Thresholds such as swing window, break tolerance, and volatility normalization must be configurable, recorded in analysis metadata, and covered by tests.
