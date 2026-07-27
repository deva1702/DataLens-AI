import pandas as pd

from assistant.insight_generator import (InsightGenerator,InsightGenerationError,)
from assistant.sql_generator import (SQLGenerator,SQLGenerationError,)
from database.database_manager import (DatabaseManager,DatabaseError,)
from guardrails.sql_validator import (SQLValidator,SQLValidationError,)
from preprocessing.dataset_profiler import DatasetProfiler


class AnalyticsError(Exception):
    """Raised when the analytics pipeline cannot complete."""


class AnalyticsResult:
    """Represents the output of a completed analytics request."""

    def __init__(
        self,
        question: str,
        sql: str,
        data: pd.DataFrame,
        insight: str,
    ) -> None:
        self.question = question
        self.sql = sql
        self.data = data
        self.insight = insight


class AnalyticsAssistant:
    """
    Orchestrates the complete DataLens analytics pipeline.

    Pipeline:
        Natural-language question
        -> dataset profiling
        -> SQL generation
        -> SQL validation
        -> SQLite execution
        -> grounded explanation
    """

    def __init__(
        self,
        database: DatabaseManager,
        dataframe: pd.DataFrame,
    ) -> None:
        self.database = database
        self.dataframe = dataframe

        self.sql_generator = SQLGenerator()
        self.insight_generator = InsightGenerator()

    def analyze(
        self,
        question: str,
    ) -> AnalyticsResult:
        """
        Run the complete analytics pipeline.

        Args:
            question:
                Natural-language analytical question.

        Returns:
            AnalyticsResult containing the generated SQL,
            verified data, and grounded explanation.

        Raises:
            AnalyticsError:
                If any stage of the analytics pipeline fails.
        """

        if not question or not question.strip():
            raise AnalyticsError(
                "Please enter a question."
            )

        question = question.strip()

        try:
            # Step 1: Inspect the uploaded dataset.
            schema = self.database.get_schema()

            dataset_profile = DatasetProfiler.profile(
                self.dataframe
            )

            # Step 2: Natural language -> SQL.
            generated_sql = self.sql_generator.generate(
                question=question,
                schema=schema,
                dataset_profile=dataset_profile,
            )

            # Step 3: Validate generated SQL.
            validated_sql = SQLValidator.validate(
                generated_sql
            )

            # Step 4: Execute verified computation.
            result = self.database.execute_query(
                validated_sql
            )

            # Step 5: Explain only the verified database result.
            # The validated SQL is supplied only as context so
            # the explanation model understands ranking,
            # filtering, grouping, and aggregation operations.
            insight = self.insight_generator.generate(
                question=question,
                result=result,
                sql=validated_sql,
            )

            return AnalyticsResult(
                question=question,
                sql=validated_sql,
                data=result,
                insight=insight,
            )

        except (
            SQLGenerationError,
            SQLValidationError,
            DatabaseError,
            InsightGenerationError,
        ) as exc:
            raise AnalyticsError(
                str(exc)
            ) from exc