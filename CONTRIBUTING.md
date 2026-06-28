# Contributing to StructureIQ

Thank you for helping improve StructureIQ. Contributions should preserve its identity as explainable decision-support software—not a signal guarantee, broker, or live-trading bot.

## Development Setup

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pytest
```

## Change Guidelines

- Keep domain engines modular and deterministic.
- Preserve the `/analysis` request and backward compatibility unless a change is explicitly versioned.
- Keep decisions, setup qualification, strategy comparison, and trader-facing explanation separate.
- Add focused tests for new behavior and regression tests for confirmed defects.
- Use synthetic candles and provider fixtures instead of live network calls in tests.
- Update the relevant blueprint documents and `docs/Changelog.md` when public behavior changes.
- Do not commit credentials, market-data tokens, personal journal data, or generated coverage/build artifacts.

## Pull Request Checklist

- [ ] The change has a narrow, documented purpose.
- [ ] Existing contracts remain compatible or the change is explicitly versioned.
- [ ] Focused tests cover meaningful behavior and edge cases.
- [ ] `python -m pytest` passes locally.
- [ ] Documentation and limitations are accurate.
- [ ] No broker execution, live trading, or financial-performance claims were introduced unintentionally.

Security issues should follow [SECURITY.md](SECURITY.md), not the public issue tracker.
