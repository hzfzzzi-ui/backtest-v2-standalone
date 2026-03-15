from __future__ import annotations

from pathlib import Path


def _read_repo_file(*parts: str) -> str:
    repo_root = Path(__file__).resolve().parents[2]
    return (repo_root.joinpath(*parts)).read_text(encoding="utf-8", errors="ignore")


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


def test_experiment_history_services_depend_on_new_history_impl_only() -> None:
    query_source = _read_repo_file("backend", "core", "services", "experiment_query_service.py")
    compare_source = _read_repo_file("backend", "core", "services", "experiment_compare_service.py")
    assert "from backend.api.backtest_v2 import history_impl" in query_source
    assert "from backend.api.backtest_v2 import history_impl" in compare_source
    assert "_experiment_history" not in query_source
    assert "_experiment_history" not in compare_source
