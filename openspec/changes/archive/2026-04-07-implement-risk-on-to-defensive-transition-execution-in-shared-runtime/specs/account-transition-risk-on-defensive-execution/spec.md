# Capability: account-transition-risk-on-defensive-execution

## ADDED Requirements

### Requirement: Shared account transition execution policy must be injectable into ETF sleeve runtime

The system MUST allow the shared account transition execution policy to enter ETF sleeve runtime input before ETF sleeve execution begins.

### Requirement: Shared runtime must own sell-first execution on risk_on-to-defensive edges

The system MUST let the shared account execution runtime own sell-first execution for `risk_on -> defensive` edges.
