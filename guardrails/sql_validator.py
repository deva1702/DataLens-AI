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

        # Remove single-quoted string literals before security
        # checks. This avoids false positives when ordinary
        # dataset values contain words such as DELETE or
        # sqlite_master.
        #
        # Double-quoted identifiers are intentionally preserved
        # because SQLite permits quoted object names such as
        # "sqlite_master".
        query_for_security_check = re.sub(
            r"'(?:''|[^'])*'",
            "''",
            cleaned_query,
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

        # Prevent access to SQLite internal metadata objects.
        # Double-quoted identifiers remain visible here.
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

        # Block SQLite PRAGMA table-valued functions such as
        # pragma_table_info(...).
        if re.search(
            r"\bpragma_[A-Za-z0-9_]*\s*\(",
            query_for_security_check,
            flags=re.IGNORECASE,
        ):
            raise SQLValidationError(
                "Access to internal database metadata "
                "is not allowed."
            )

        # Detect tables referenced directly after FROM or JOIN.
        #
        # Commas are deliberately NOT treated as table-reference
        # markers because commas also occur normally in SELECT
        # column lists such as:
        #
        # SELECT employee_name, salary FROM dataset
        #
        # SQLite metadata objects in comma joins are already
        # rejected by the metadata checks above.
        table_references = re.findall(
            r"""
            (?:\bFROM\b|\bJOIN\b)
            \s*
            (?:
                "([^"]+)"
                |
                ([A-Za-z_][A-Za-z0-9_]*)
            )
            """,
            query_for_security_check,
            flags=re.IGNORECASE | re.VERBOSE,
        )

        normalized_tables = [
            quoted or unquoted
            for quoted, unquoted in table_references
        ]

        # Every directly referenced table must be dataset.
        for table_name in normalized_tables:
            if table_name.lower() != "dataset":
                raise SQLValidationError(
                    "Queries may only access the uploaded dataset."
                )

        # Require the query to access the uploaded dataset.
        if not normalized_tables:
            raise SQLValidationError(
                "Query must access the uploaded dataset."
            )

        return cleaned_query