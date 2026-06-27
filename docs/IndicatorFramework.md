# Indicator Framework

## Role of Indicators

Indicators confirm or weaken the market-structure thesis. They do not create the thesis by themselves.

StructureIQ evaluates indicators only after a structural interpretation exists. Indicator evidence may increase confidence when it aligns with structure, reduce confidence when it conflicts, or remain neutral when it is ambiguous. No isolated crossover, oscillator reading, or threshold is sufficient to produce a trade decision.

## Initial Indicators

### EMA 20, EMA 50, and EMA 200

Exponential moving averages describe short-, intermediate-, and long-term price location and trend context. The framework considers price position, average slope, separation, and ordered alignment. Crossovers are contextual evidence, not standalone signals.

### RSI

The Relative Strength Index describes recent momentum and the balance of gains and losses. It can confirm momentum, expose weakening participation, or identify stretched conditions. Overbought and oversold readings do not automatically imply reversal.

### MACD

Moving Average Convergence Divergence describes changes in momentum and trend acceleration through the MACD line, signal line, and histogram. Crosses and divergence are interpreted in relation to structure and timeframe.

### ATR

Average True Range measures realized volatility. It supports volatility classification, normalizes distance and break significance, and informs whether invalidation and target distances are realistic. ATR is non-directional.

### ADX

Average Directional Index estimates trend strength. It can support a trend or range classification but does not determine bullish or bearish direction by itself.

### Volume, Where Available

Volume describes participation and may confirm expansion, breakouts, rejection, or exhaustion. Because availability and meaning vary by instrument and provider, volume evidence must carry provenance and quality metadata. Missing or non-comparable volume must be treated as unavailable rather than zero.

## Standard Indicator Output

Each indicator adapter should return:

- Name, parameters, and calculation version.
- Source timeframe and candle timestamp.
- Current value and any necessary reference values.
- Bullish, bearish, or neutral interpretation.
- Evidence strength and data-quality status.
- A concise reason tied to the structural thesis.

## Framework Rules

- Calculations use completed candles unless an output is explicitly marked provisional.
- Lookback sufficiency and warm-up periods are validated.
- Parameters are configurable but recorded for reproducibility.
- Indicators derived from the same price series are correlated evidence and must not be treated as fully independent votes.
- Conflicting indicators reduce certainty; they are not selectively discarded.
- Indicator calculations remain separate from decision weights and strategy rules.
- Unit tests cover formula behavior, boundary cases, insufficient history, missing volume, and stable fixture outputs.
