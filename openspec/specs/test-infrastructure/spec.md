# test-infrastructure Specification

## Purpose

Establish the foundational test dependencies, shared fixtures, and configuration required for running pytest-based tests across the backend, including async test support and mock database providers.

## Requirements

### Requirement: Test dependencies in requirements.txt
The `backend/requirements.txt` file SHALL include pytest, pytest-cov, and pytest-asyncio as dependencies.

#### Scenario: pytest installable in Docker
- **WHEN** `docker compose build` completes
- **THEN** `pytest --version` SHALL execute successfully inside the container

### Requirement: Shared test fixtures
A `tests/conftest.py` file SHALL provide shared fixtures for all tests.

#### Scenario: FastAPI test client fixture
- **WHEN** a test function declares a `test_client` parameter
- **THEN** it SHALL receive a `httpx.AsyncClient` or `starlette.testclient.TestClient` configured against the FastAPI app

#### Scenario: Mock database provider fixture
- **WHEN** a test function declares a `mock_db_provider` parameter
- **THEN** it SHALL receive a mock `DataProvider` that returns configurable DataFrames without requiring a real database connection

### Requirement: Pytest configuration
A `pytest.ini` file SHALL exist at the project root with test discovery and asyncio configuration.

#### Scenario: Test discovery
- **WHEN** `pytest` is invoked from the project root
- **THEN** it SHALL discover tests in the `tests/` directory
- **THEN** `asyncio_mode` SHALL be set to `auto` for async test support

## Synced From close-p0-p1-architecture-gaps

### Requirement: 默认 pytest 命令必须稳定完成 collect
系统 MUST 保证从仓库根目录执行默认 `pytest` 命令时能够稳定完成 collect，且不因脚本迁移、历史导入路径或退役模块而在收集阶段失败。

#### Scenario: 默认 pytest collect
- **WHEN** 从仓库根目录执行默认 `pytest`
- **THEN** 测试收集 MUST 完成
- **THEN** 收集阶段 SHALL NOT 出现由缺失脚本模块、退役导入路径或入口漂移导致的 ImportError

#### Scenario: smoke 测试默认排除
- **WHEN** 默认 `pytest` 配置排除了 smoke 测试
- **THEN** 默认 collect 与快速测试通过条件 MUST 仍然成立
- **THEN** 系统 SHALL NOT 以跳过 smoke 为理由接受收集阶段失败

### Requirement: 关键治理测试必须进入快速回归面
系统 MUST 为脚本面治理、公共 surface 收敛和前端 owner 边界提供快速回归测试，使本轮 `P0/P1` 收口在默认开发节奏下可被持续验证。

#### Scenario: 调整正式入口或 owner 边界
- **WHEN** 某次改动影响正式脚本入口、公共 surface 或前端 owner 边界
- **THEN** 对应治理测试 MUST 被更新并纳入快速回归面
- **THEN** 开发者 SHALL 能在不依赖真实数据库的前提下验证这些边界

#### Scenario: 新增治理门
- **WHEN** 本轮收口新增一个正式治理门
- **THEN** 系统 MUST 为其提供可自动执行的测试或断言
- **THEN** 该门 SHALL NOT 只停留在文档说明
