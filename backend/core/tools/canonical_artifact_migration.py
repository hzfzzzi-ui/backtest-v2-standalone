from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from backend.core.config.asset_profiles import UnsupportedAssetScopeError, build_asset_context

CANONICAL_TRADES_FILENAME = "portfolio_trades.csv"
LEGACY_TRADES_FILENAME = "trades.csv"
MANIFEST_ASSET_FIELD_NAMES: tuple[str, ...] = (
    "asset_scope",
    "asset_profile_id",
    "market_profile_id",
    "execution_profile_id",
)
CANONICAL_COUNTER_FIELDS: tuple[str, ...] = (
    "raw_signal",
    "blocked",
    "orders",
    "skipped",
    "closed_trades",
)
COUNTER_LEGACY_ALIASES: dict[str, tuple[str, ...]] = {
    "raw_signal": ("raw_signal_count",),
    "blocked": ("blocked_count",),
    "orders": ("orders_count",),
    "skipped": ("skipped_count",),
    "closed_trades": ("closed_trades_count",),
}
SHELL_LABEL_MIGRATIONS: dict[str, str] = {
    "stage_pipeline_shell_legacy_adapter": "stage_pipeline_shell_bridge",
}


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}
    return dict(payload) if isinstance(payload, dict) else {}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _manifest_artifact_rel(manifest: dict[str, Any], key: str, default_rel: str) -> str:
    artifacts = manifest.get("artifacts") if isinstance(manifest.get("artifacts"), dict) else {}
    value = str(artifacts.get(key) or "").strip()
    return value or default_rel


def _normalize_counters(counters: dict[str, Any] | None) -> tuple[dict[str, Any], int]:
    src = dict(counters or {})
    out = dict(src)
    hits = 0
    for key, aliases in COUNTER_LEGACY_ALIASES.items():
        if key in out:
            continue
        for alias in aliases:
            if alias in src:
                out[key] = src.get(alias)
                hits += 1
                break
    for aliases in COUNTER_LEGACY_ALIASES.values():
        for alias in aliases:
            out.pop(alias, None)
    for key in CANONICAL_COUNTER_FIELDS:
        out.setdefault(key, 0)
    return out, hits


def _rewrite_shell_label(value: Any) -> tuple[Any, bool]:
    label = str(value or "").strip()
    if not label:
        return value, False
    canonical = SHELL_LABEL_MIGRATIONS.get(label)
    if not canonical or canonical == label:
        return value, False
    return canonical, True


def _first_non_empty(*values: Any) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _manifest_has_complete_asset_context(manifest: dict[str, Any]) -> bool:
    if not isinstance(manifest, dict) or not manifest:
        return False
    asset_context = manifest.get("asset_context") if isinstance(manifest.get("asset_context"), dict) else {}
    if not asset_context:
        return False
    for key in MANIFEST_ASSET_FIELD_NAMES:
        if not str(manifest.get(key) or "").strip():
            return False
    return bool(str(asset_context.get("asset_scope") or "").strip())


def _infer_manifest_asset_context(exp_dir: Path, manifest: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    config = _read_json(exp_dir / "config.json")
    run_config = _read_json(exp_dir / "run_config.json")
    compiled_plan = _read_json(exp_dir / "compiled_plan.json")
    compiled_runtime = (
        compiled_plan.get("runtime_config")
        if isinstance(compiled_plan.get("runtime_config"), dict)
        else None
    )
    manifest_asset = manifest.get("asset_context") if isinstance(manifest.get("asset_context"), dict) else {}
    config_asset = config.get("asset_context") if isinstance(config.get("asset_context"), dict) else {}
    run_config_asset = run_config.get("asset_context") if isinstance(run_config.get("asset_context"), dict) else {}
    compiled_asset = compiled_plan.get("asset_context") if isinstance(compiled_plan.get("asset_context"), dict) else {}
    workbench_config = (
        (config.get("overrides") or {}).get("workbench_config")
        if isinstance((config.get("overrides") or {}).get("workbench_config"), dict)
        else None
    )

    source_config = (
        compiled_runtime
        or run_config
        or workbench_config
        or config
    )
    source_scope = _first_non_empty(
        manifest.get("asset_scope"),
        manifest_asset.get("asset_scope"),
        compiled_plan.get("asset_scope"),
        compiled_asset.get("asset_scope"),
        run_config.get("asset_scope") if isinstance(run_config, dict) else None,
        run_config_asset.get("asset_scope"),
        config.get("asset_scope") if isinstance(config, dict) else None,
        config_asset.get("asset_scope"),
    )
    has_runtime_inputs = bool(compiled_runtime or run_config or workbench_config or config)
    if not has_runtime_inputs and not source_scope:
        return None, "missing_runtime_inputs"
    try:
        context = build_asset_context(
            asset_scope=source_scope or None,
            config_json=source_config if isinstance(source_config, dict) else None,
            metadata_scope=source_scope or None,
        )
    except UnsupportedAssetScopeError as exc:
        return None, str(exc)
    return context, None


def audit_experiment_dir(exp_dir: Path) -> dict[str, Any]:
    manifest_path = exp_dir / "manifest.json"
    manifest = _read_json(manifest_path)
    if not manifest:
        return {
            "exp_id": exp_dir.name,
            "manifest_exists": False,
            "needs_manifest_asset_backfill": False,
            "manifest_backfill_skip_reason": "missing_manifest",
            "needs_trade_migration": False,
            "needs_counter_migration": False,
            "needs_shell_label_migration": False,
            "legacy_counter_hits": 0,
            "legacy_trades_exists": False,
            "canonical_trades_exists": False,
        }

    run_meta_rel = _manifest_artifact_rel(manifest, "run_meta", "run_meta.json")
    run_meta = _read_json(exp_dir / run_meta_rel)
    counters = run_meta.get("counters") if isinstance(run_meta.get("counters"), dict) else {}
    _, counter_hits = _normalize_counters(counters)

    manifest_stage = manifest.get("stage_pipeline") if isinstance(manifest.get("stage_pipeline"), dict) else {}
    run_meta_stage = run_meta.get("stage_pipeline") if isinstance(run_meta.get("stage_pipeline"), dict) else {}
    _, manifest_shell_changed = _rewrite_shell_label(manifest_stage.get("execution_shell"))
    _, run_meta_shell_changed = _rewrite_shell_label(run_meta_stage.get("execution_shell"))
    inferred_asset_context, asset_skip_reason = _infer_manifest_asset_context(exp_dir, manifest)
    missing_manifest_asset_fields = [
        key for key in (*MANIFEST_ASSET_FIELD_NAMES, "asset_context")
        if not (
            isinstance(manifest.get(key), dict) and manifest.get(key)
            if key == "asset_context"
            else str(manifest.get(key) or "").strip()
        )
    ]
    needs_manifest_asset_backfill = bool(
        missing_manifest_asset_fields and inferred_asset_context is not None
    ) and not _manifest_has_complete_asset_context(manifest)

    artifacts = manifest.get("artifacts") if isinstance(manifest.get("artifacts"), dict) else {}
    trade_rel = str(artifacts.get("trades") or "").strip()
    trades_alias_rel = str(artifacts.get("trades_alias") or "").strip()
    canonical_trades = (exp_dir / CANONICAL_TRADES_FILENAME).resolve()
    legacy_trades = (exp_dir / LEGACY_TRADES_FILENAME).resolve()
    needs_trade_migration = bool(
        trade_rel == LEGACY_TRADES_FILENAME
        or trades_alias_rel
        or legacy_trades.exists()
        or (trade_rel == CANONICAL_TRADES_FILENAME and not canonical_trades.exists() and legacy_trades.exists())
    )

    return {
        "exp_id": str(manifest.get("exp_id") or exp_dir.name),
        "manifest_exists": True,
        "needs_manifest_asset_backfill": needs_manifest_asset_backfill,
        "manifest_missing_fields": missing_manifest_asset_fields,
        "manifest_backfill_skip_reason": asset_skip_reason,
        "needs_trade_migration": needs_trade_migration,
        "needs_counter_migration": counter_hits > 0,
        "needs_shell_label_migration": manifest_shell_changed or run_meta_shell_changed,
        "legacy_counter_hits": counter_hits,
        "legacy_trades_exists": legacy_trades.exists(),
        "canonical_trades_exists": canonical_trades.exists(),
        "trade_artifact_rel": trade_rel,
        "trades_alias_rel": trades_alias_rel,
        "run_meta_rel": run_meta_rel,
    }


def _same_file_bytes(left: Path, right: Path) -> bool:
    try:
        return left.read_bytes() == right.read_bytes()
    except Exception:
        return False


def migrate_experiment_dir(exp_dir: Path, *, dry_run: bool = True) -> dict[str, Any]:
    audit = audit_experiment_dir(exp_dir)
    if not audit.get("manifest_exists"):
        return {
            **audit,
            "changed": False,
            "changes": [],
        }

    manifest_path = exp_dir / "manifest.json"
    manifest = _read_json(manifest_path)
    run_meta_rel = str(audit.get("run_meta_rel") or "run_meta.json")
    run_meta_path = exp_dir / run_meta_rel
    run_meta = _read_json(run_meta_path)
    changes: list[str] = []

    inferred_asset_context, asset_skip_reason = _infer_manifest_asset_context(exp_dir, manifest)
    if audit.get("needs_manifest_asset_backfill") and inferred_asset_context is not None:
        manifest.setdefault("exp_id", str(manifest.get("experiment_id") or exp_dir.name))
        manifest.setdefault("experiment_id", str(manifest.get("exp_id") or exp_dir.name))
        manifest.setdefault("schema_version", "backtest_v2_experiment_manifest@2")
        manifest["asset_scope"] = str(inferred_asset_context.get("asset_scope") or "")
        manifest["asset_profile_id"] = str(inferred_asset_context.get("asset_profile_id") or "")
        manifest["market_profile_id"] = str(inferred_asset_context.get("market_profile_id") or "")
        manifest["execution_profile_id"] = str(inferred_asset_context.get("execution_profile_id") or "")
        manifest["asset_context"] = dict(inferred_asset_context)
        changes.append("backfilled_manifest_asset_context")

    canonical_trades = (exp_dir / CANONICAL_TRADES_FILENAME).resolve()
    legacy_trades = (exp_dir / LEGACY_TRADES_FILENAME).resolve()
    if audit.get("needs_trade_migration"):
        if legacy_trades.exists() and not canonical_trades.exists():
            if not dry_run:
                shutil.move(str(legacy_trades), str(canonical_trades))
            changes.append("promoted_trades_to_canonical")
        elif legacy_trades.exists() and canonical_trades.exists() and _same_file_bytes(legacy_trades, canonical_trades):
            if not dry_run:
                legacy_trades.unlink()
            changes.append("removed_legacy_trades_alias")
        artifacts = manifest.get("artifacts") if isinstance(manifest.get("artifacts"), dict) else {}
        if canonical_trades.exists() or legacy_trades.exists():
            artifacts["trades"] = CANONICAL_TRADES_FILENAME
        artifacts.pop("trades_alias", None)
        manifest["artifacts"] = artifacts

        core_artifacts = manifest.get("core_artifacts") if isinstance(manifest.get("core_artifacts"), dict) else {}
        if canonical_trades.exists() or legacy_trades.exists():
            core_artifacts["trades"] = CANONICAL_TRADES_FILENAME
        core_artifacts.pop("trades_alias", None)
        if core_artifacts:
            manifest["core_artifacts"] = core_artifacts

    counters = run_meta.get("counters") if isinstance(run_meta.get("counters"), dict) else {}
    normalized_counters, counter_hits = _normalize_counters(counters)
    if counter_hits > 0:
        run_meta["counters"] = normalized_counters
        changes.append("normalized_run_meta_counters")

    manifest_stage = manifest.get("stage_pipeline") if isinstance(manifest.get("stage_pipeline"), dict) else {}
    manifest_shell, manifest_shell_changed = _rewrite_shell_label(manifest_stage.get("execution_shell"))
    if manifest_shell_changed:
        manifest_stage["execution_shell"] = manifest_shell
        manifest["stage_pipeline"] = manifest_stage
        changes.append("rewrote_manifest_execution_shell")

    run_meta_stage = run_meta.get("stage_pipeline") if isinstance(run_meta.get("stage_pipeline"), dict) else {}
    run_meta_shell, run_meta_shell_changed = _rewrite_shell_label(run_meta_stage.get("execution_shell"))
    if run_meta_shell_changed:
        run_meta_stage["execution_shell"] = run_meta_shell
        run_meta["stage_pipeline"] = run_meta_stage
        changes.append("rewrote_run_meta_execution_shell")

    if not dry_run and changes:
        _write_json(manifest_path, manifest)
        if run_meta:
            _write_json(run_meta_path, run_meta)

    return {
        **audit,
        "manifest_backfill_skip_reason": asset_skip_reason or audit.get("manifest_backfill_skip_reason"),
        "changed": bool(changes),
        "changes": changes,
    }


def migrate_experiment_tree(
    experiments_root: Path,
    *,
    dry_run: bool = True,
    report_path: Path | None = None,
) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    for child in sorted(experiments_root.iterdir()) if experiments_root.exists() else []:
        if child.is_dir() and child.name.startswith("exp_"):
            results.append(migrate_experiment_dir(child, dry_run=dry_run))

    changed = [row for row in results if row.get("changed")]
    report = {
        "schema_version": "canonical_artifact_migration_report@2",
        "generated_at": datetime.now().isoformat(),
        "dry_run": bool(dry_run),
        "root": str(experiments_root),
        "summary": {
            "experiments_scanned": len(results),
            "experiments_changed": len(changed),
            "manifest_backfills": sum(1 for row in results if row.get("needs_manifest_asset_backfill")),
            "manifest_backfill_skips": sum(1 for row in results if row.get("manifest_backfill_skip_reason")),
            "trade_migrations": sum(1 for row in results if row.get("needs_trade_migration")),
            "counter_migrations": sum(1 for row in results if row.get("needs_counter_migration")),
            "shell_label_migrations": sum(1 for row in results if row.get("needs_shell_label_migration")),
            "legacy_counter_hits": sum(int(row.get("legacy_counter_hits") or 0) for row in results),
        },
        "experiments": results,
    }
    if report_path is not None:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report
