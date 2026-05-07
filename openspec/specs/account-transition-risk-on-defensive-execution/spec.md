# account-transition-risk-on-defensive-execution Specification

## Purpose

定义共享账户执行 runtime 在 `risk_on -> defensive` 边界上的第一条真实执行行为。

## Requirements

### Requirement: Shared account transition execution policy must be injectable into ETF sleeve runtime

The system MUST allow the shared account transition execution policy to enter ETF sleeve runtime input before ETF sleeve execution begins.

#### Scenario: shared transition policy reaches ETF runtime input
- **WHEN** the shared account runtime prepares ETF sleeve execution input
- **THEN** the ETF sleeve receives the shared transition execution policy before local execution begins

### Requirement: Shared runtime must own sell-first execution on risk_on-to-defensive edges

The system MUST let the shared account execution runtime own sell-first execution for `risk_on -> defensive` edges.

#### Scenario: sell-first release is shared-runtime-owned
- **WHEN** the account transition family is `risk_on -> defensive`
- **THEN** the shared account runtime emits sell-first de-risk execution
- **THEN** old local weak-state owners do not remain primary owners for the same edge
