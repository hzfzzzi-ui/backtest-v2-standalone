# Test Infrastructure

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
