from unittest.mock import MagicMock

import pytest

from backend.core.services import ops_domain_pg


def test_schema_check_is_read_only_when_transaction_table_exists():
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchone.return_value = {"relation": "pams_transaction_lifecycle"}

    ops_domain_pg.ensure_tables(connection)

    cursor.execute.assert_called_once_with(
        "SELECT to_regclass(%s) AS relation", ("public.pams_transaction_lifecycle",)
    )
    connection.commit.assert_not_called()


def test_missing_transaction_table_raises_explicit_error_without_ddl():
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchone.return_value = {"relation": None}

    with pytest.raises(ops_domain_pg.OpsDomainSchemaMissing, match="schema must be provisioned separately"):
        ops_domain_pg.ensure_tables(connection)

    cursor.execute.assert_called_once_with(
        "SELECT to_regclass(%s) AS relation", ("public.pams_transaction_lifecycle",)
    )
    connection.commit.assert_not_called()
