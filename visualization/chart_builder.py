import pandas as pd
import streamlit as st


class ChartBuilder:
    """Creates useful charts from verified analytics results."""

    MAX_CATEGORIES = 20

    @classmethod
    def render(cls, dataframe: pd.DataFrame) -> bool:
        """Render a chart when the result structure supports one."""

        if dataframe.empty:
            return False

        if len(dataframe) < 2 or len(dataframe) > cls.MAX_CATEGORIES:
            return False

        numeric_columns = dataframe.select_dtypes(
            include="number"
        ).columns.tolist()

        non_numeric_columns = [
            column
            for column in dataframe.columns
            if column not in numeric_columns
        ]

        # Require one category and one numeric metric.
        if len(non_numeric_columns) < 1 or len(numeric_columns) != 1:
            return False

        category_column = non_numeric_columns[0]
        value_column = numeric_columns[0]

        chart_data = dataframe[
            [category_column, value_column]
        ].copy()

        chart_data = chart_data.set_index(
            category_column
        )

        st.markdown("#### Visualization")

        st.bar_chart(
            chart_data,
            use_container_width=True,
        )

        return True