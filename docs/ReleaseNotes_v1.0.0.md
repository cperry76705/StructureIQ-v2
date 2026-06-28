# StructureIQ v1.0.0 Release Notes

## Stable MVP Release Candidate

StructureIQ v1.0.0 is an explainable market-intelligence and trader decision-support platform. It interprets current price structure, weighs evidence, qualifies setups, compares playbooks, and presents a disciplined trade plan. It does not predict markets, guarantee outcomes, place orders, or manage live positions.

## Included Engines

- Market Data Engine with provider abstraction and friendly-symbol normalization.
- Market Structure Engine for swings, HH/HL/LH/LL, BOS, CHOCH, liquidity sweeps, trend, and phase.
- Two-timeframe Analysis Engine for directional context and execution alignment.
- Indicator Framework for supported confirmation evidence.
- Decision Engine using the documented `35/25/15/15/10` weighted model.
- Setup Engine for qualification, entry conditions, risk levels, and invalidation.
- Strategy Engine for ranked continuation, reversal, range, liquidity, and compression playbooks.
- Analysis/Explanation Engine for plain-English narratives and checklist plans.
- Journal and Backtesting Engine for local records and simplified historical evaluation.
- Calibration Engine for observational multi-run diagnostics and human-review recommendations.

## Public Endpoints

- `GET /health`
- `POST /analysis`
- `POST /journal`
- `GET /journal`
- `GET /journal/summary`
- `POST /backtest`
- `POST /calibrate`

The `/analysis` request remains unchanged. Existing top-level response fields remain available alongside internal engine blocks and the trader-facing `trader_analysis` block.

## Release Readiness

- The application and OpenAPI version are `1.0.0`.
- Public endpoint methods are protected by a release contract test.
- All engines retain focused deterministic tests; 126 tests pass in the release-candidate suite, which also runs in continuous integration.
- Repository contribution, security, licensing, and release guidance is present.

## Known Limitations

- Conclusions are deterministic heuristic interpretations, not forecasts or financial advice.
- Provider availability, revisions, interval coverage, and data quality can affect results.
- Backtesting uses simplified candle-based outcomes and omits spread, fees, slippage, latency, partial fills, position sizing, and portfolio interactions.
- When stop and target are touched in one candle, the simulator uses a documented conservative assumption rather than intrabar data.
- Calibration is descriptive, inherits backtest limitations, and does not establish statistical significance or tune the application.
- Journal storage is local JSONL without authentication, concurrency control, migrations, or multi-user isolation.
- This release has no dashboard, alerts, broker integration, order execution, or live-trading loop.

## Next Planned Improvements

- Stronger data-quality reporting and provider resilience.
- Walk-forward and out-of-sample validation with better execution-cost modeling.
- Durable, queryable journal storage for controlled multi-user deployments.
- Operational observability, authentication guidance, and deployment hardening.
- Trader-facing clients built against the stable API without coupling UI concerns to domain engines.

Before tagging, the project owner should confirm continuous-integration results, choose the final distribution license, and review the intended deployment's authentication and network controls.
