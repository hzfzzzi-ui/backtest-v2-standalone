# buy-cash-affordability-contract Specification

## Purpose

Define the formal BUY affordability contract so planning-stage BUY decisions use the same cost semantics as the actual fill stage.

## Requirements

### Requirement: BUY planning MUST use fill-equivalent cash affordability

The system SHALL evaluate BUY affordability with the same effective cost semantics used at fill time, including executable price, slippage, commission, and lot constraints. Planning SHALL NOT approve BUY orders that are affordable only under a cheaper or incomplete cost model.

#### Scenario: planning evaluates BUY orders with fill-equivalent cost
- **WHEN** execution planning estimates the cost of a BUY order
- **THEN** it uses the same cash semantics as the fill stage
- **THEN** only orders whose net cost is within available cash may enter the scheduled order set

### Requirement: unaffordable BUY orders MUST be clipped or rejected during planning

When a BUY order exceeds affordable cash, the system SHALL clip it to the maximum affordable lot-aligned quantity. If the clipped quantity is still below one lot, the BUY order SHALL be rejected during planning rather than allowed to fail one day later for the same cash reason.

#### Scenario: BUY quantity is clipped to the maximum affordable lot
- **WHEN** a BUY candidate exceeds available cash
- **THEN** planning computes the maximum affordable lot-aligned quantity
- **THEN** the scheduled order uses the clipped quantity if at least one lot remains

#### Scenario: insufficient cash leaves less than one lot
- **WHEN** clipping still leaves less than one lot
- **THEN** the BUY candidate is rejected during planning
- **THEN** the rejection is recorded as a cash-affordability failure rather than deferred to fill-time failure
