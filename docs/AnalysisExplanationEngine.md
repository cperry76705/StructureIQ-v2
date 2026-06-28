# Analysis/Explanation Engine

## Purpose

The Analysis/Explanation Engine converts StructureIQ's internal engine output into trader-facing summaries, explanations, risks, and checklist-style trade plans.

It is a presentation boundary, not a decision maker. It explains the existing Decision Engine action and Setup Engine qualification without changing either one.

## Inputs

The v0.6 engine consumes:

- Symbol or market identifier for presentation.
- Current Market Structure result.
- Multi-Timeframe result and directional context.
- Decision result, confidence, evidence, and risk notes.
- Setup plan, status, levels, entry conditions, invalidation rules, evidence, and warnings.

Missing optional levels or risk/reward remain unavailable in the output. The engine uses fallback language rather than inventing values or failing.

## Outputs

`TraderAnalysis` contains:

- Headline and plain-English summary.
- Recommendation derived from existing decision and setup status.
- `MarketNarrative` with bias, phase, and timeframe context.
- Traceable reasons explaining the result.
- `TradePlan` with status, setup, direction, levels, risk/reward, wait checklist, invalidation, and notes.
- `KeyRisk` items with low, medium, or high severity and a reason.
- Confidence interpretation.
- Next best action implied by the current plan.

The plan status is one of `actionable`, `developing`, `waiting`, `avoid`, or `no_trade`.

## Relationship to Decision Engine

The Decision Engine remains the sole owner of buy, sell, wait, avoid, and numerical confidence. The Explanation Engine maps those results into readable language.

- Buy or sell plus a confirmed setup maps to an actionable plan.
- Wait maps to a waiting or developing plan.
- Avoid maps to avoid language and a stand-aside next action.

The Explanation Engine does not rescore evidence, create a different action, or upgrade confidence.

## Relationship to Setup Engine

The Setup Engine remains the sole owner of setup type, qualification status, checklist state, levels, and invalidation.

The Explanation Engine projects unmet required entry conditions into `wait_for` items and converts invalidation rules into readable plan notes. It does not mark conditions complete, invent levels, or turn a developing setup into a confirmed setup.

## Trader-Facing Response Design

Trader-facing output favors concise and conditional language:

- State what the market context currently supports.
- Explain whether a plan is actionable, developing, waiting, avoid, or no trade.
- Name the qualified setup without exposing implementation jargon unnecessarily.
- Show exactly which required conditions remain unmet.
- Preserve structural invalidation and risk warnings.
- Present the next review step rather than an unconditional command.

All statements must be traceable to internal engine output. Trader-facing explanations coexist with, rather than replace, detailed API fields.

## Confidence Interpretation Rules

| Decision confidence | Interpretation |
| ---: | --- |
| `0–49` | Weak or no edge; evidence does not support a trade. |
| `50–69` | Moderate but incomplete edge; more confirmation is required. |
| `70–84` | Strong evidence, but execution discipline and invalidation still matter. |
| `85–100` | High-conviction evidence, but the outcome is not guaranteed. |

Confidence describes evidence quality and agreement. It is not a predicted win rate.

## Limitations

- Language is generated from deterministic templates rather than a natural-language model.
- Risk severity is inferred from existing evidence impacts and warnings.
- Optional entry, stop, target, and risk/reward fields remain null when upstream engines cannot measure them.
- The engine currently explains one Setup Engine result; multi-strategy comparison belongs to version 0.7.
- It does not personalize plans to account size, risk tolerance, jurisdiction, or experience.
- It does not place orders, manage brokers, or perform live trading.
