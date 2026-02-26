## ADDED Requirements

### Requirement: Database connection error handling
The `PostgresDataProvider._conn()` method SHALL catch connection errors and raise a structured `DatabaseConnectionError` instead of raw psycopg exceptions.

#### Scenario: Database host unreachable
- **WHEN** `psycopg.connect()` raises `psycopg.OperationalError` due to network failure
- **THEN** a `DatabaseConnectionError` SHALL be raised with the original error message and host/port context

#### Scenario: Authentication failure
- **WHEN** `psycopg.connect()` raises an authentication error
- **THEN** a `DatabaseConnectionError` SHALL be raised with a message indicating credential failure (without exposing the password)

### Requirement: Database query error handling
The `PostgresDataProvider._exec_df()` method SHALL catch query execution errors and raise a structured `DatabaseQueryError` with query context.

#### Scenario: Query execution failure
- **WHEN** a SQL query fails (e.g., table not found, syntax error)
- **THEN** a `DatabaseQueryError` SHALL be raised with the table name, query type from `audit_meta`, and the original error message

#### Scenario: Statement timeout
- **WHEN** a query exceeds the configured `statement_timeout_ms`
- **THEN** a `DatabaseQueryError` SHALL be raised with a message indicating timeout and the configured limit

### Requirement: Custom exception module
A new `backend/core/data/errors.py` module SHALL define `DatabaseConnectionError` and `DatabaseQueryError` exception classes.

#### Scenario: Exception class structure
- **WHEN** a `DatabaseConnectionError` or `DatabaseQueryError` is raised
- **THEN** it SHALL be a subclass of a common `DatabaseError` base class
- **THEN** it SHALL carry `message`, `context` (dict) attributes for structured error reporting
