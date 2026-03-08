# dead-code-removal

## MODIFIED Requirements

### Requirement: Classified shrink-pass deletions

Zero-reference cleanup MUST distinguish between ad hoc deletion and
classification-gated shrink work.

When a file is removed under `v2-shrink-pass`, the deletion MUST satisfy all of
the following:
- the file was explicitly classified as `transitional` or `deprecated` by the
  March 7 support/inventory work
- no product-supported runtime imports the file
- compatibility behavior, if any, remains available through another supported
  path
- the March 7 baseline gate passes after the deletion

#### Scenario: Transition helper is folded into its owning runtime
- **WHEN** a transitional helper such as `backend/core/engine_vector/runtime_surface.py`
  is folded into its sole owning module
- **THEN** the helper file MAY be deleted without changing baseline runtime behavior

#### Scenario: Deprecated implementation file is removed after compatibility is preserved
- **WHEN** a deprecated implementation file such as `backend/core/strategies/adaptive_regime.py`
  is no longer imported and its alias behavior is preserved by registry/API compatibility logic
- **THEN** the file MAY be deleted as part of dead-code cleanup

#### Scenario: Purely unreferenced cleanup is not enough by itself
- **WHEN** a file has low or zero references but still belongs to a supported
  research or product contract
- **THEN** `dead-code-removal` MUST NOT delete it solely on reference count
