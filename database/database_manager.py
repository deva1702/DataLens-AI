import sqlite3

import pandas as pd


class DatabaseError(Exception):
    """Raised when a database operation fails."""


class DatabaseManager:
    """
    Manages an in-memory SQLite database used for
    deterministic dataset analysis.
    """

    TABLE_NAME = "dataset"

    def __init__(self) -> None:
        """
        Create an in-memory SQLite database.

        The database exists only while the application
        session is active.
        """

        self._connection = sqlite3.connect(
            ":memory:",
            check_same_thread=False,
        )

    def load_dataframe(
        self,
        dataframe: pd.DataFrame,
    ) -> None:
        """
        Load a Pandas DataFrame into SQLite.

        Existing dataset data is replaced whenever
        a new dataset is loaded.
        """

        try:
            dataframe.to_sql(
                self.TABLE_NAME,
                self._connection,
                if_exists="replace",
                index=False,
            )

        except Exception as exc:
            raise DatabaseError(
                "Failed to load the dataset into the database."
            ) from exc

    def execute_query(
        self,
        query: str,
    ) -> pd.DataFrame:
        """
        Execute a SQL query and return the result
        as a Pandas DataFrame.

        Query safety will be handled separately by
        the SQLValidator before this method is called.
        """

        try:
            result = pd.read_sql_query(
                query,
                self._connection,
            )

            return result

        except Exception as exc:
            raise DatabaseError(
                f"Failed to execute SQL query: {exc}"
            ) from exc

    def get_schema(self) -> list[dict]:
        """
        Return column names and SQLite data types
        for the dataset table.
        """

        try:
            cursor = self._connection.execute(
                f'PRAGMA table_info("{self.TABLE_NAME}")'
            )

            schema = [
                {
                    "name": row[1],
                    "type": row[2],
                }
                for row in cursor.fetchall()
            ]

            return schema

        except Exception as exc:
            raise DatabaseError(
                "Failed to retrieve the database schema."
            ) from exc

    def get_row_count(self) -> int:
        """
        Return the number of rows stored in
        the dataset table.
        """

        try:
            cursor = self._connection.execute(
                f'SELECT COUNT(*) FROM "{self.TABLE_NAME}"'
            )

            result = cursor.fetchone()

            return int(result[0])

        except Exception as exc:
            raise DatabaseError(
                "Failed to count dataset rows."
            ) from exc

    def close(self) -> None:
        """Close the SQLite database connection."""

        self._connection.close()