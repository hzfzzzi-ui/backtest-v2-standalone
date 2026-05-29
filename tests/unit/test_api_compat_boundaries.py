from __future__ import annotations

import re
from pathlib import Path


_ROUTE_DECORATOR_RE = re.compile(
    r"@router\.(get|post|put|patch|delete|options|head)\(\s*[\"']([^\"']+)[\"']"
)


def _read_repo_file(*parts: str) -> str:
    repo_root = Path(__file__).resolve().parents[2]
    return (repo_root.joinpath(*parts)).read_text(encoding="utf-8", errors="ignore")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _api_python_files() -> list[Path]:
    root = _repo_root() / "backend" / "api"
    return [path for path in root.rglob("*.py") if "__pycache__" not in path.parts]


def _is_api_route_owner(path: Path) -> bool:
    rel = path.relative_to(_repo_root()).as_posix()
    return "/routes/" in rel or rel.endswith("/router.py")


def test_mobile_routes_depend_on_new_mobile_impl_only() -> None:
    for route_name in ["auth.py", "dashboard.py", "approvals.py", "tickets.py"]:
        source = _read_repo_file("backend", "api", "mobile", "routes", route_name)
        assert "from backend.api.mobile import impl" in source
        assert "_mobile_dashboard_impl" not in source


def test_removed_mobile_impl_compat_module_stays_deleted() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    assert not repo_root.joinpath("backend", "api", "endpoints", "_mobile_dashboard_impl.py").exists()


def test_removed_mobile_dashboard_compat_module_stays_deleted() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    assert not repo_root.joinpath("backend", "api", "endpoints", "mobile_dashboard.py").exists()


def test_removed_backtest_v2_compat_module_stays_deleted() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    assert not repo_root.joinpath("backend", "api", "endpoints", "backtest_v2.py").exists()


def test_removed_backtest_v2_artifacts_compat_module_stays_deleted() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    assert not repo_root.joinpath("backend", "api", "endpoints", "backtest_v2_artifacts.py").exists()


def test_removed_config_store_compat_module_stays_deleted() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    assert not repo_root.joinpath("backend", "api", "endpoints", "_config_store.py").exists()


def test_removed_public_contracts_compat_module_stays_deleted() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    assert not repo_root.joinpath("backend", "api", "endpoints", "_public_contracts.py").exists()


def test_removed_backtest_v2_data_impl_compat_module_stays_deleted() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    assert not repo_root.joinpath("backend", "api", "endpoints", "_backtest_v2_impl.py").exists()


def test_removed_experiment_runner_compat_module_stays_deleted() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    assert not repo_root.joinpath("backend", "api", "endpoints", "_experiment_runner_api.py").exists()


def test_removed_semantic_compiler_compat_module_stays_deleted() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    assert not repo_root.joinpath("backend", "api", "endpoints", "_semantic_config_compiler.py").exists()


def test_removed_experiment_history_compat_module_stays_deleted() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    assert not repo_root.joinpath("backend", "api", "endpoints", "_experiment_history.py").exists()


def test_removed_backtest_v2_protocol_compat_module_stays_deleted() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    assert not repo_root.joinpath("backend", "api", "endpoints", "backtest_v2_protocol.py").exists()


def test_removed_transactions_compat_module_stays_deleted() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    assert not repo_root.joinpath("backend", "api", "endpoints", "transactions.py").exists()


def test_removed_endpoints_helper_modules_stay_deleted() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    for filename in ["_paths.py", "_utils.py", "_job_store.py", "_mobile_access.py"]:
        assert not repo_root.joinpath("backend", "api", "endpoints", filename).exists()


def test_backtest_v2_routes_depend_on_new_impl_only() -> None:
    for route_name in [
        "artifacts.py",
        "configs.py",
        "execution_preview.py",
        "experiments.py",
        "experiment_jobs.py",
        "market_data.py",
        "validation.py",
    ]:
        source = _read_repo_file("backend", "api", "backtest_v2", "routes", route_name)
        if route_name == "configs.py":
            assert "from backend.api.backtest_v2 import configs_impl" in source
        else:
            assert "from backend.api.backtest_v2 import impl" in source
        assert "from backend.api.endpoints import " not in source


def test_backtest_v2_impl_stays_within_new_boundary_modules() -> None:
    source = _read_repo_file("backend", "api", "backtest_v2", "impl.py")
    assert "from backend.api.backtest_v2.data_impl import (" in source
    assert "from backend.api.backtest_v2.runner_impl import (" in source
    assert "backend.api.endpoints._backtest_v2_impl" not in source
    assert "backend.api.endpoints._experiment_runner_api" not in source


def test_api_method_path_pairs_have_single_owner() -> None:
    seen: dict[tuple[str, str], str] = {}
    duplicates: list[str] = []

    for path in _api_python_files():
        rel = path.relative_to(_repo_root()).as_posix()
        source = path.read_text(encoding="utf-8", errors="ignore")
        for method, api_path in _ROUTE_DECORATOR_RE.findall(source):
            key = (method.upper(), api_path)
            if key in seen:
                duplicates.append(f"{method.upper()} {api_path}: {seen[key]} and {rel}")
            else:
                seen[key] = rel

    assert duplicates == []


def test_http_decorators_stay_in_route_owner_modules() -> None:
    offenders: list[str] = []

    for path in _api_python_files():
        source = path.read_text(encoding="utf-8", errors="ignore")
        if "@router." in source and not _is_api_route_owner(path):
            offenders.append(path.relative_to(_repo_root()).as_posix())

    assert offenders == []


def test_api_impl_modules_do_not_declare_route_owners() -> None:
    offenders: list[str] = []

    for path in _api_python_files():
        rel = path.relative_to(_repo_root()).as_posix()
        if not (rel.endswith("/impl.py") or rel.endswith("_impl.py")):
            continue
        source = path.read_text(encoding="utf-8", errors="ignore")
        if "APIRouter" in source or "@router." in source or "router = APIRouter" in source:
            offenders.append(rel)

    assert offenders == []


def test_backtest_v2_legacy_impl_modules_are_not_route_owners() -> None:
    for filename in ["configs_impl.py", "data_impl.py", "history_impl.py", "runner_impl.py"]:
        source = _read_repo_file("backend", "api", "backtest_v2", filename)
        assert "APIRouter" not in source
        assert "@router." not in source
        assert "router = APIRouter" not in source
        assert ".include_router(" not in source


def test_backtest_v2_config_routes_are_owned_by_route_wrapper() -> None:
    source = _read_repo_file("backend", "api", "backtest_v2", "routes", "configs.py")
    assert "router = configs_impl.router" not in source
    assert "APIRouter" in source
    for path in [
        "/api/backtest_v2/configs",
        "/api/backtest_v2/configs/{config_id}",
        "/api/backtest_v2/baselines",
        "/api/backtest_v2/baselines/{baseline_id}",
    ]:
        assert path in source


def test_mobile_impl_does_not_import_backtest_v2_route_wrappers() -> None:
    source = _read_repo_file("backend", "api", "mobile", "impl.py")
    assert "backend.api.backtest_v2.routes" not in source
    assert "routes.execution_preview" not in source


def test_pams_transition_boundary_registry_covers_legacy_services() -> None:
    from backend.core.services.service_boundary_status import (
        SERVICE_BOUNDARY_BY_MODULE,
        SERVICE_BOUNDARY_STATUS,
    )

    required_modules = {
        "backend.api.mobile",
        "backend.core.services.mobile_dashboard_service",
        "backend.core.services.mobile_ops_service",
        "backend.core.services.mobile_execution_service",
        "backend.core.services.mobile_notification_service",
        "backend.core.services.mobile_cash_pool_service",
        "backend.core.services.sim_account_service",
        "backend.core.services.sim_account_reconcile_service",
        "backend.core.services.sim_account_domain_service",
        "backend.core.services.sim_account_auto_sync_service",
        "backend.core.services.transaction_lifecycle_service",
    }
    assert len(SERVICE_BOUNDARY_STATUS) == len(SERVICE_BOUNDARY_BY_MODULE)
    assert required_modules <= set(SERVICE_BOUNDARY_BY_MODULE)
    for module in required_modules:
        entry = SERVICE_BOUNDARY_BY_MODULE[module]
        assert entry.target_system == "pams"
        assert entry.launch_status in {"externalize_to_pams", "compat_audit_only"}
        assert entry.owner_note


def test_mobile_surface_declares_compat_internal_preview_boundary() -> None:
    from backend.api.mobile import (
        MOBILE_API_BOUNDARY_NOTE,
        MOBILE_API_BOUNDARY_OWNER,
        MOBILE_API_LAUNCH_STATUS,
    )

    assert MOBILE_API_LAUNCH_STATUS == "compat_internal_preview"
    assert MOBILE_API_BOUNDARY_OWNER == "pams"
    assert "PAMS" in MOBILE_API_BOUNDARY_NOTE

    mobile_ops_source = _read_repo_file("backend", "core", "services", "mobile_ops_service.py")
    lifecycle_source = _read_repo_file("backend", "core", "services", "transaction_lifecycle_service.py")
    assert "Compatibility-only mobile approval ticket service" in mobile_ops_source
    assert "Compatibility transaction lifecycle mirror" in lifecycle_source
    assert "PAMS owns the long-term transaction lifecycle truth" in lifecycle_source


def test_new_api_and_services_depend_on_shared_helpers_only() -> None:
    files = [
        ("backend", "api", "backtest_v2", "artifacts_impl.py"),
        ("backend", "api", "backtest_v2", "configs_impl.py"),
        ("backend", "api", "backtest_v2", "data_impl.py"),
        ("backend", "api", "backtest_v2", "history_impl.py"),
        ("backend", "api", "backtest_v2", "impl.py"),
        ("backend", "api", "backtest_v2", "runner_impl.py"),
        ("backend", "api", "backtest_v2", "semantic_config_compiler.py"),
        ("backend", "api", "mobile", "impl.py"),
        ("backend", "core", "services", "experiment_artifact_service.py"),
        ("backend", "core", "services", "experiment_runtime_service.py"),
        ("backend", "core", "services", "experiment_summary_service.py"),
        ("backend", "research", "study_runner.py"),
        ("backend", "main.py"),
    ]
    for parts in files:
        source = _read_repo_file(*parts)
        assert "backend.api.endpoints._" not in source


def test_shared_helper_surface_exists() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    for filename in ["__init__.py", "paths.py", "json_utils.py", "job_store.py", "mobile_access.py"]:
        assert repo_root.joinpath("backend", "api", "shared", filename).exists()


def test_main_mounts_transactions_from_new_surface_only() -> None:
    source = _read_repo_file("backend", "main.py")
    assert "from backend.api.transactions import router as transactions_router" in source
    assert "backend.api.endpoints.transactions" not in source


def test_experiment_history_services_depend_on_core_history_service() -> None:
    query_source = _read_repo_file("backend", "core", "services", "experiment_query_service.py")
    compare_source = _read_repo_file("backend", "core", "services", "experiment_compare_service.py")
    history_api_source = _read_repo_file("backend", "api", "backtest_v2", "history_impl.py")
    history_service_source = _read_repo_file("backend", "core", "services", "experiment_history_service.py")
    assert "from backend.core.services import experiment_history_service" in query_source
    assert "from backend.core.services import experiment_history_service" in compare_source
    assert "from backend.api.backtest_v2 import history_impl" not in query_source
    assert "from backend.api.backtest_v2 import history_impl" not in compare_source
    assert "from backend.core.services import experiment_history_service" in history_api_source
    assert "def list_experiments(*, experiments_root: Path | None = None)" in history_service_source
    assert "def compare_experiments(body: dict[str, Any], *, experiments_root: Path | None = None)" in history_service_source
    assert "_experiment_history" not in query_source
    assert "_experiment_history" not in compare_source
