## Why

The simple CSI1000 trend rebuild showed that plain trend entry plus broad
market filtering still loses heavily. The next question is not how to raise
win rate, but how to make entry failures attributable.

## What Changes

- Add a research-only shadow attribution for stock entry quality.
- Use only information visible at entry time for factor buckets.
- Use future path and realized follow-up only as outcome labels, not as
  decision inputs.
- Include CSI800 versus CSI1000 membership attribution.

## Non-Goals

- No formal baseline mutation.
- No production signal, execution, fill, account, or portfolio change.
- No industry, theme, or market-state model.
- No parameter search for best performance.

## Validation

- Focused unit tests for bucket definitions and outcome path metrics.
- Docker run on the simple CSI1000 trend rebuild outputs.
- Report whether the attribution is reliable enough to guide the next design.
