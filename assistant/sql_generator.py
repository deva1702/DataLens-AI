import json

from groq import Groq

from config.settings import Settings


class SQLGenerationError(Exception):
    """Raised when SQL generation fails."""


class SQLGenerator:
    """
    Converts natural-language analytical questions
    into safe SQLite SELECT queries.

    The generator uses the database schema and a compact
    dataset profile so it can work with different datasets.
    """

    def __init__(self) -> None:
        Settings.validate()

        self.client = Groq(
            api_key=Settings.GROQ_API_KEY,
        )

        self.model = Settings.GROQ_MODEL

    def generate(
        self,
        question: str,
        schema: list[dict],
        dataset_profile: dict,
    ) -> str:
        """
        Generate a SQLite SELECT query for a user question.

        Args:
            question:
                Natural-language analytical question.

            schema:
                SQLite schema for the uploaded dataset.

            dataset_profile:
                Compact metadata describing the uploaded dataset,
                including column types and representative values.

        Returns:
            Generated SQLite SELECT query.

        Raises:
            SQLGenerationError:
                If SQL cannot be generated.
        """

        if not question or not question.strip():
            raise SQLGenerationError(
                "Question cannot be empty."
            )

        schema_text = self._format_schema(
            schema
        )

        profile_text = json.dumps(
            dataset_profile,
            indent=2,
            default=str,
            ensure_ascii=False,
        )

        system_prompt = f"""
You are the SQL generation component of DataLens AI.

Your task is to convert the user's analytical question into
one valid SQLite SELECT query.

DATABASE:
There is exactly one table named:

dataset

DATABASE SCHEMA:
{schema_text}

DATASET PROFILE:
{profile_text}

The dataset profile contains compact metadata and sample values.
Sample values are examples only and are not the complete dataset.

STRICT RULES:

1. Use only the table named dataset.

2. Use only columns present in the supplied schema.

3. Never invent columns, tables, values, or database results.

4. Generate SQLite-compatible SQL.

5. Generate only a read-only SELECT query.

6. Never generate INSERT, UPDATE, DELETE, DROP, ALTER,
   CREATE, REPLACE, TRUNCATE, PRAGMA, ATTACH, DETACH,
   VACUUM, or other database-modifying operations.

7. Perform calculations using SQL.

8. Use SUM, AVG, COUNT, MIN, MAX, GROUP BY, ORDER BY,
   WHERE, and LIMIT when appropriate.

9. Always include every column or computed metric needed to fully
   support the final answer.

   For ranking, highest, lowest, maximum, minimum, top, bottom,
   aggregation, and comparison questions, return both:
   - the identifying/grouping field, and
   - the value or calculated metric used to determine the result.

10. Use sample values only to understand the likely meaning
    and formatting of columns. Do not assume the samples
    represent all possible values.

11. Never invent a business formula.

12. If the user explicitly defines a calculation, use that
    definition when the required columns exist.

13. Do not assume that similarly named columns have a
    particular relationship unless it is reasonably supported
    by the schema, profile, or user's question.

14. When working with date-like TEXT columns, use
    SQLite-compatible date functions only when the stored
    sample format supports that operation.

15. Return only the SQL query.

16. Do not use Markdown or SQL code fences.

17. Do not explain the SQL.

18. If the question cannot be answered using the available
    dataset, return exactly:

CANNOT_GENERATE_SQL

19. When using aggregate functions such as SUM, AVG, COUNT, MIN,
or MAX, give the computed column a clear descriptive alias.

"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": system_prompt,
                    },
                    {
                        "role": "user",
                        "content": question.strip(),
                    },
                ],
                temperature=0,
            )

            sql = response.choices[0].message.content

        except Exception as exc:
            print(
                "SQL generation failure:",
                type(exc).__name__,
                getattr(exc, "status_code", None),
            )
            raise SQLGenerationError(
                "The SQL generation service could not complete the request."
            ) from exc

        if not sql:
            raise SQLGenerationError(
                "The model returned an empty response."
            )

        sql = sql.strip()

        # Defensive cleanup in case the model still returns
        # a Markdown SQL code block.
        if sql.startswith("```"):
            sql = self._remove_code_fence(sql)

        if sql.upper() == "CANNOT_GENERATE_SQL":
            raise SQLGenerationError(
                "This question cannot be answered "
                "from the available dataset."
            )

        return sql

    @staticmethod
    def _format_schema(
        schema: list[dict],
    ) -> str:
        """
        Convert the SQLite schema into compact text
        suitable for the LLM prompt.
        """

        if not schema:
            return "No columns available."

        return "\n".join(
            f"- {column['name']} ({column['type']})"
            for column in schema
        )

    @staticmethod
    def _remove_code_fence(
        text: str,
    ) -> str:
        """
        Remove accidental Markdown code fences
        from an LLM response.
        """

        cleaned = text.strip()

        if cleaned.startswith("```sql"):
            cleaned = cleaned[6:]

        elif cleaned.startswith("```"):
            cleaned = cleaned[3:]

        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]

        return cleaned.strip()