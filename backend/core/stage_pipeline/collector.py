from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .contracts import StageOutputs


STAGE_SUMMARY_SCHEMA_VERSION = "stage_pipeline_summary@1"


@dataclass(slots=True)
class StagePipelineCollector:
    records: list[StageOutputs] = field(default_factory=list)

    def record(self, output: StageOutputs) -> StageOutputs:
        self.records.append(output)
        return output

    def build_summary(
        self,
        *,
        execution_shell: str = "stage_pipeline_shell",
        daily_loop_mode: str = "single_day_loop",
    ) -> dict[str, Any]:
        warnings: list[str] = []
        for record in self.records:
            warnings.extend(record.warnings)
        return {
            "schema_version": STAGE_SUMMARY_SCHEMA_VERSION,
            "execution_shell": execution_shell,
            "daily_loop_mode": daily_loop_mode,
            "stage_order": [record.stage_key for record in self.records],
            "enabled_stages": [record.stage_key for record in self.records if record.enabled],
            "warnings": warnings,
            "stage_fragments": {
                record.stage_key: dict(record.summary_fragment)
                for record in self.records
            },
        }
