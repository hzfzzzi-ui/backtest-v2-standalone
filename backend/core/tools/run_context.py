from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class RunContext:
    preset: str
    base_config_path: str
    overrides: dict[str, Any] = field(default_factory=dict)
    created_at_utc: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    _wall_t0: float = field(default_factory=time.perf_counter)
    _stage_t0: float | None = None
    _stage_name: str | None = None
    stage_seconds: dict[str, float] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def start_stage(self, name: str) -> None:
        if self._stage_name and self._stage_t0 is not None:
            self.end_stage(self._stage_name)
        self._stage_name = str(name)
        self._stage_t0 = time.perf_counter()

    def end_stage(self, name: str | None = None) -> None:
        if self._stage_t0 is None:
            return
        stage_name = str(name or self._stage_name or "unknown")
        elapsed = float(time.perf_counter() - self._stage_t0)
        self.stage_seconds[stage_name] = float(self.stage_seconds.get(stage_name, 0.0)) + elapsed
        self._stage_t0 = None
        self._stage_name = None

    def add_note(self, note: str) -> None:
        if note:
            self.notes.append(str(note))

    def to_profile(self, *, results_dir: str, extras: dict[str, Any] | None = None) -> dict[str, Any]:
        self.end_stage()
        extra_data = dict(extras or {})
        stage_seconds = dict(self.stage_seconds)
        total_wall_seconds = float(time.perf_counter() - self._wall_t0)
        row_count = int(extra_data.get("row_count", 0) or 0)
        variant_count = int(extra_data.get("variant_count", 0) or 0)
        symbols_count = int(extra_data.get("symbols_count", 0) or 0)
        trading_days = int(extra_data.get("trading_days", 0) or 0)
        rows_per_second = float(row_count) / max(total_wall_seconds, 1e-9) if row_count > 0 else 0.0
        bottleneck_stage = ""
        bottleneck_seconds = 0.0
        if stage_seconds:
            bottleneck_stage, bottleneck_seconds = max(stage_seconds.items(), key=lambda kv: float(kv[1] or 0.0))
        bottleneck_label = "BOTTLENECK_UNKNOWN"
        if bottleneck_stage in {"data_load", "universe_resolve"}:
            bottleneck_label = "BOTTLENECK_DATA_LOAD"
        elif bottleneck_stage in {"simulation"}:
            bottleneck_label = "BOTTLENECK_SIMULATION"
        elif bottleneck_stage in {"precompute"}:
            bottleneck_label = "BOTTLENECK_PRECOMPUTE"
        elif bottleneck_stage in {"output_write", "report_write"}:
            bottleneck_label = "BOTTLENECK_IO"

        profile = {
            "preset": self.preset,
            "created_at_utc": self.created_at_utc,
            "base_config_path": self.base_config_path,
            "results_dir": results_dir,
            "overrides": dict(self.overrides or {}),
            "stage_seconds": stage_seconds,
            "total_wall_seconds": total_wall_seconds,
            "symbols_count": symbols_count,
            "trading_days": trading_days,
            "variant_count": variant_count,
            "row_count": row_count,
            "rows_per_second": rows_per_second,
            "bottleneck_stage": bottleneck_stage,
            "bottleneck_stage_seconds": float(bottleneck_seconds),
            "bottleneck_label": bottleneck_label,
            "notes": list(self.notes),
        }
        if extras:
            profile.update(extra_data)
        return profile

    def write_profile(self, *, results_dir: str, extras: dict[str, Any] | None = None, filename: str = "run_profile.json") -> Path:
        out_dir = Path(results_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / filename
        import json

        path.write_text(
            json.dumps(self.to_profile(results_dir=results_dir, extras=extras), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return path
