## ADDED Requirements

### Requirement: Job cancel button during polling
The frontend SHALL display a cancel button while a backtest job is running, allowing the user to stop it.

#### Scenario: Cancel button appears during run
- **WHEN** `pollJob()` starts polling a running job
- **THEN** the Run button (`wbRunBtn`) SHALL change its text to "取消运行" and its style to a danger/warning appearance

#### Scenario: Cancel button triggers API call
- **WHEN** the user clicks the cancel button during polling
- **THEN** the frontend SHALL send `POST /api/backtest_v2/jobs/{job_id}/cancel`
- **THEN** the polling loop SHALL exit and display "已取消" in `wbRunStatus`

#### Scenario: Button reverts after run completes
- **WHEN** the job completes (success, failed, or canceled)
- **THEN** the Run button SHALL revert to its original "Run" text and style
