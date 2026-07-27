import re


class SQLValidationError(Exception):
    """Raised when a SQL query violates safety rules."""


class SQLValidator:
    """
    Validates LLM-generated SQL before database execution.

    DataLens permits only read-only SELECT queries against
    the uploaded dataset.
    """

    FORBIDDEN_KEYWORDS = {
        "INSERT",
        "UPDATE",
        "DELETE",
        "DROP",
        "ALTER",
        "CREATE",
        "REPLACE",
        "TRUNCATE",
        "ATTACH",
        "DETACH",
        "VACUUM",
        "PRAGMA",
        "REINDEX",
        "ANALYZE",
    }

    FORBIDDEN_OBJECTS = {
        "SQLITE_MASTER",
        "SQLITE_SCHEMA",
        "SQLITE_TEMP_MASTER",
        "SQLITE_TEMP_SCHEMA",
    }

    MAX_QUERY_LENGTH = 5000

    @classmethod
    def validate(cls, query: str) -> str:
        """
        Validate and normalize a SQL query.

        Returns:
            The cleaned, validated SQL query.

        Raises:
            SQLValidationError:
                If the query is empty, unsafe, or unsupported.
        """

        if not isinstance(query, str) or not query.strip():
            raise SQLValidationError(
                "SQL query cannot be empty."
            )

        cleaned_query = query.strip()

        if len(cleaned_query) > cls.MAX_QUERY_LENGTH:
            raise SQLValidationError(
                "SQL query exceeds the allowed length."
            )

        # Remove one optional trailing semicolon.
        if cleaned_query.endswith(";"):
            cleaned_query = cleaned_query[:-1].strip()

        if not cleaned_query:
            raise SQLValidationError(
                "SQL query cannot be empty."
            )

        # Block multiple SQL statements.
        if ";" in cleaned_query:
            raise SQLValidationError(
                "Multiple SQL statements are not allowed."
            )

        # Block SQL comments.
        if re.search(
            r"(--|/\*|\*/)",
            cleaned_query,
        ):
            raise SQLValidationError(
                "SQL comments are not allowed."
            )

        # DataLens supports SELECT only.
        if not re.match(
            r"^\s*SELECT\b",
            cleaned_query,
            flags=re.IGNORECASE,
        ):
            raise SQLValidationError(
                "Only SELECT queries are allowed."
            )

        # Remove quoted string values before keyword checks.
        # Example:
        # WHERE action = 'DELETE'
        # should remain a valid read-only query.
        query_without_strings = re.sub(
            r"'(?:''|[^'])*'",
            "''",
            cleaned_query,
        )

        # Also remove double-quoted values/identifiers from
        # dangerous-keyword inspection.
        query_for_security_check = re.sub(
            r'"(?:""|[^"])*"',
            '""',
            query_without_strings,
        )

        # Block dangerous SQL operations.
        for keyword in cls.FORBIDDEN_KEYWORDS:
            if re.search(
                rf"\b{re.escape(keyword)}\b",
                query_for_security_check,
                flags=re.IGNORECASE,
            ):
                raise SQLValidationError(
                    f"Forbidden SQL operation detected: {keyword}."
                )

        # Prevent access to SQLite internal metadata tables.
        for object_name in cls.FORBIDDEN_OBJECTS:
            if re.search(
                rf"\b{re.escape(object_name)}\b",
                query_for_security_check,
                flags=re.IGNORECASE,
            ):
                raise SQLValidationError(
                    "Access to internal database metadata "
                    "is not allowed."
                )

        # Restrict queries to the application's dataset table.
        table_references = re.findall(
            r"\b(?:FROM|JOIN)\s+([A-Za-z_][A-Za-z0-9_]*)",
            query_for_security_check,
            flags=re.IGNORECASE,
        )

        for table_name in table_references:
            if table_name.lower() != "dataset":
                raise SQLValidationError(
                    "Queries may only access the uploaded dataset."
                )

        # Require the query to actually access the dataset.
        if not table_references:
            raise SQLValidationError(
                "Query must access the uploaded dataset."
            )

        return cleaned_query