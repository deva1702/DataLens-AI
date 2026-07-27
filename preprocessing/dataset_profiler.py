from typing import Any

import pandas as pd


class DatasetProfiler:
    """
    Creates compact metadata describing an uploaded dataset.

    The profile helps the LLM understand unfamiliar datasets
    without sending the complete dataset to the model.
    """

    MAX_SAMPLE_VALUES = 5
    MAX_TEXT_LENGTH = 80

    @classmethod
    def profile(
        cls,
        dataframe: pd.DataFrame,
    ) -> dict:
        """Create a compact profile of the dataset."""

        return {
            "row_count": len(dataframe),
            "column_count": len(dataframe.columns),
            "columns": [
                cls._profile_column(dataframe, column)
                for column in dataframe.columns
            ],
        }

    @classmethod
    def _profile_column(
        cls,
        dataframe: pd.DataFrame,
        column: str,
    ) -> dict:
        """Create metadata for one column."""

        series = dataframe[column]

        non_null = series.dropna()

        unique_count = int(series.nunique(dropna=True))
        missing_count = int(series.isna().sum())

        sample_values = cls._get_sample_values(
            non_null
        )

        return {
            "name": column,
            "pandas_type": str(series.dtype),
            "missing_count": missing_count,
            "unique_count": unique_count,
            "sample_values": sample_values,
        }

    @classmethod
    def _get_sample_values(
        cls,
        series: pd.Series,
    ) -> list[Any]:
        """
        Return a small set of representative unique values.

        Only a few values are included so that large datasets
        do not create unnecessarily large LLM prompts.
        """

        if series.empty:
            return []

        values = (
            series
            .drop_duplicates()
            .head(cls.MAX_SAMPLE_VALUES)
            .tolist()
        )

        return [
            cls._make_serializable(value)
            for value in values
        ]

    @classmethod
    def _make_serializable(
        cls,
        value: Any,
    ) -> Any:
        """Convert Pandas/NumPy values into prompt-safe values."""

        if pd.isna(value):
            return None

        if isinstance(value, pd.Timestamp):
            return value.isoformat()

        if hasattr(value, "item"):
            try:
                value = value.item()
            except (ValueError, AttributeError):
                pass

        if isinstance(value, str):
            value = value.strip()

            if len(value) > cls.MAX_TEXT_LENGTH:
                return (
                    value[: cls.MAX_TEXT_LENGTH]
                    + "..."
                )

        return value