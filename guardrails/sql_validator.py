import re


class SQLValidationError(Exception):
    """Raised when a SQL query violates safety rules."""


class SQLValidator:
    """
    Validates LLM-generated SQL before database execution.

    DataLens only permits read-only SELECT queries against
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
    }

    @classmethod
    def validate(cls, query: str) -> str:
        """
        Validate and normalize a SQL query.

        Returns:
            The cleaned SQL query.

        Raises:
            SQLValidationError:
                If the query is empty, unsafe, or unsupported.
        """

        if not query or not query.strip():
            raise SQLValidationError("SQL query cannot be empty.")

        cleaned_query = query.strip()

        # Remove one optional trailing semicolon.
        if cleaned_query.endswith(";"):
            cleaned_query = cleaned_query[:-1].strip()

        if not cleaned_query:
            raise SQLValidationError("SQL query cannot be empty.")

        # Prevent multiple SQL statements.
        if ";" in cleaned_query:
            raise SQLValidationError(
                "Multiple SQL statements are not allowed."
            )

        # Only SELECT statements are allowed.
        if not re.match(
            r"^\s*SELECT\b",
            cleaned_query,
            flags=re.IGNORECASE,
        ):
            raise SQLValidationError(
                "Only SELECT queries are allowed."
            )

        # Remove quoted strings before checking dangerous keywords.
        # This prevents values such as 'DELETE' from being incorrectly blocked.
        query_without_strings = re.sub(
            r"'(?:''|[^'])*'",
            "''",
            cleaned_query,
        )

        for keyword in cls.FORBIDDEN_KEYWORDS:
            if re.search(
                rf"\b{keyword}\b",
                query_without_strings,
                flags=re.IGNORECASE,
            ):
                raise SQLValidationError(
                    f"Forbidden SQL operation detected: {keyword}."
                )

        return cleaned_query