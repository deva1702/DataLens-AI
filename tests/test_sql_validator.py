import pytest

from guardrails.sql_validator import (
    SQLValidator,
    SQLValidationError,
)


@pytest.mark.parametrize(
    "query",
    [
        "SELECT * FROM dataset",
        'SELECT * FROM "dataset"',
        (
            "SELECT employee_name, salary "
            "FROM dataset "
            "ORDER BY salary DESC "
            "LIMIT 1"
        ),
        (
            "SELECT department, "
            "AVG(experience_years) AS avg_experience "
            "FROM dataset "
            "GROUP BY department"
        ),
        (
            "SELECT region, "
            "COUNT(employee_id) AS employee_count "
            "FROM dataset "
            "GROUP BY region"
        ),
        (
            "SELECT * FROM dataset "
            "WHERE employee_name = 'sqlite_master'"
        ),
    ],
)
def test_valid_dataset_queries_are_allowed(query):
    """Normal read-only dataset queries should pass validation."""

    result = SQLValidator.validate(query)

    assert result == query


@pytest.mark.parametrize(
    "query",
    [
        "SELECT * FROM sqlite_master",
        'SELECT * FROM "sqlite_master"',
        "SELECT * FROM dataset, sqlite_master",
        'SELECT * FROM dataset, "sqlite_master"',
        "SELECT * FROM pragma_table_info('dataset')",
        (
            "SELECT * FROM dataset "
            "CROSS JOIN sqlite_master"
        ),
        (
            'SELECT * FROM dataset AS d '
            'CROSS JOIN "sqlite_master" AS m'
        ),
    ],
)
def test_metadata_access_is_blocked(query):
    """SQLite metadata access should be rejected."""

    with pytest.raises(SQLValidationError):
        SQLValidator.validate(query)


@pytest.mark.parametrize(
    "query",
    [
        "DROP TABLE dataset",
        "DELETE FROM dataset",
        "UPDATE dataset SET salary = 0",
        "INSERT INTO dataset VALUES (1)",
        "PRAGMA table_info(dataset)",
    ],
)
def test_non_read_only_operations_are_blocked(query):
    """Mutating or administrative SQL should be rejected."""

    with pytest.raises(SQLValidationError):
        SQLValidator.validate(query)


def test_multiple_statements_are_blocked():
    """Multiple SQL statements should not be accepted."""

    query = "SELECT * FROM dataset; DROP TABLE dataset;"

    with pytest.raises(SQLValidationError):
        SQLValidator.validate(query)


def test_sql_comments_are_blocked():
    """SQL comments should be rejected."""

    query = "SELECT * FROM dataset -- comment"

    with pytest.raises(SQLValidationError):
        SQLValidator.validate(query)


def test_query_must_access_dataset():
    """A SELECT query must reference the uploaded dataset."""

    query = "SELECT 1"

    with pytest.raises(SQLValidationError):
        SQLValidator.validate(query)


def test_empty_query_is_blocked():
    """Empty SQL should not pass validation."""

    with pytest.raises(SQLValidationError):
        SQLValidator.validate("")