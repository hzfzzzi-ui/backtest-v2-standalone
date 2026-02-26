from __future__ import annotations

from typing import Any


class DatabaseError(Exception):
    """Base class for all database-related errors."""

    def __init__(self, message: str, context: dict[str, Any] | None = None) -> None:
        self.message = message
        self.context: dict[str, Any] = context or {}
        super().__init__(message)


class DatabaseConnectionError(DatabaseError):
    """Raised when a database connection cannot be established."""


class DatabaseQueryError(DatabaseError):
    """Raised when a database query fails during execution."""
