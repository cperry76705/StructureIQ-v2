# StructureIQ Testing Strategy

## Quality Standard

Every engine must have focused unit tests. New features cannot break existing tests.

StructureIQ produces decision-support information, so deterministic behavior, transparent edge cases, and regression protection are core product requirements rather than optional cleanup.

## Test Layers

### Unit Tests

Each engine is tested independently with controlled inputs and no external network dependency. Unit tests should cover normal behavior, boundaries, ambiguous evidence, insufficient data, invalid data, and known failure modes.

Minimum focus by engine:

- **Market Data Engine:** normalization, provider errors, missing fields, ordering, and data quality.
- **Market Structure Engine:** swing confirmation, HH/HL/LH/LL, BOS versus sweep, CHOCH, phase classification, and unclear states.
- **Multi-Timeframe Engine:** aligned, conflicting, and neutral timeframe combinations.
- **Indicator Framework:** calculation fixtures, warm-up periods, missing volume, and interpretation boundaries.
- **Decision Engine:** weights, normalization, missing evidence, confidence penalties, decision thresholds, and evidence ledger integrity.
- **Strategy Engine:** qualification, rejection, confirmation, invalidation, and risk gates for each strategy.
- **Intelligence/Explanation Engine:** traceability to supplied evidence and faithful representation of conflicts.
- **Journal/Backtesting Engine:** persistence, reproducibility, look-ahead protection, fees, slippage, and outcome calculations.

### Integration Tests

Integration tests verify engine boundaries and typed contracts, including the full analysis pipeline with deterministic provider fixtures. They ensure that engines compose correctly without relying on live provider availability.

### API Contract Tests

API tests verify status codes, validation, response schemas, dependency injection, and informative failure behavior for `GET /health` and `POST /analysis`. Existing clients should not be broken by undocumented response changes.

### Regression Tests

Every confirmed defect should gain a test that fails before the fix and passes after it. Stable market fixtures should protect important structural classifications and scores against unintended change.

## Test Data Rules

- Use small, purpose-built candle sequences for precise structural behavior.
- Use larger deterministic fixtures for pipeline and regression tests.
- Keep live network requests outside the default test suite.
- Record timeframe, data assumptions, and expected event timing.
- Never use future candles in a way that introduces look-ahead bias beyond an explicitly defined confirmation window.

## Change Requirements

Before a feature is complete:

1. New domain behavior has focused unit tests.
2. Relevant integration and API contract tests pass.
3. The entire existing test suite passes.
4. Public contract changes are documented and intentionally versioned.
5. Test failures are fixed or explicitly understood; tests are not weakened merely to accept new output.

The standard local command is:

```powershell
python -m pytest
```

Continuous integration should run the complete suite for every pull request and block merging on failures.
