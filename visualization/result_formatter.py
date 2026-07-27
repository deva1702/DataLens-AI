import pandas as pd


class ResultFormatter:
    """Formats verified query results for display."""

    DECIMAL_PLACES = 2

    @classmethod
    def format_dataframe(cls, dataframe: pd.DataFrame) -> pd.DataFrame:
        """Return a display-only copy with readable numeric precision."""

        display_df = dataframe.copy()

        for column in display_df.columns:
            if pd.api.types.is_float_dtype(display_df[column]):
                display_df[column] = display_df[column].round(
                    cls.DECIMAL_PLACES
                )

        return display_df