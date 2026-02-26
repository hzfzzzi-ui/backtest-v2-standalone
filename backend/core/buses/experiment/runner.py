from __future__ import annotations

from typing import Any, Callable


def run_command(*args: Any, **kwargs: Any) -> None:
    raise RuntimeError(
        "Legacy experiment command runner has been removed. "
        "Use backend.core.tools.experiment_runner.run_experiment instead."
    )


def run_experiment(
    base_cfg_path: str,
    preset: str = "single",
    overrides: dict[str, Any] | None = None,
    progress_hook: Callable[[int, str], None] | None = None,
) -> dict[str, Any]:
    from backend.core.tools.experiment_runner import run_experiment as _run_experiment

    return _run_experiment(
        base_cfg_path=base_cfg_path,
        preset=preset,
        overrides=overrides,
        progress_hook=progress_hook,
    )
