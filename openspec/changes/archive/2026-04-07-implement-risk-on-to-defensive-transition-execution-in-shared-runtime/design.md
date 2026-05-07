# Design

## Design intent

The goal is not to redesign all transition families at once. The goal is to implement the first real execution family under the shared account transition contract:

- `risk_on -> defensive`

This family is implemented as:

- bounded partial de-risk
- minimum defensive cash release
- diagnostics-only demotion of old ETF local edge ownership
