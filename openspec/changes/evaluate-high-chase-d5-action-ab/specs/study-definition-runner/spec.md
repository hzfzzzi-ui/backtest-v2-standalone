## ADDED Requirements

### Requirement: High Chase D5 study MUST isolate one research surface
The study definition runner MUST support a declarative High Chase D5 AB study where all variants share the same V3 stock runtime source and only patch High Chase D5 runtime parameters.

#### Scenario: Study plan is built
- **WHEN** the High Chase D5 study definition is loaded
- **THEN** the plan MUST include B0 replay, all-scope D5 immediate, High Chase immediate, High Chase watch, and High Chase delayed-confirm variants
- **AND** every variant MUST use the same `runtime_config_path`
- **AND** variant overrides MUST be limited to strategy runtime parameters for D5/high-chase behavior

### Requirement: High Chase D5 study MUST remain research-only
The High Chase D5 study MUST be marked research-only and MUST NOT modify baseline registration.

#### Scenario: Study metadata is inspected
- **WHEN** the study YAML is parsed
- **THEN** metadata MUST indicate `research_only=true`
- **AND** the study MUST record the source V3 stock component experiment and source High Chase shadow audit id
