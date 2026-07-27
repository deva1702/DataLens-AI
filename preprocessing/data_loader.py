from pathlib import Path
from typing import BinaryIO

import pandas as pd


class DataLoaderError(Exception):
    """Raised when a dataset cannot be loaded or validated."""


class DataLoader:
    """Loads and validates CSV and Excel datasets."""

    SUPPORTED_EXTENSIONS = {".csv", ".xlsx"}
    MAX_FILE_SIZE_MB = 50

    @classmethod
    def load(
        cls,
        file: BinaryIO,
        filename: str,
    ) -> pd.DataFrame:
        """
        Load an uploaded CSV or Excel file.

        Args:
            file:
                Uploaded file-like object.

            filename:
                Original filename.

        Returns:
            Cleaned and validated Pandas DataFrame.
        """

        extension = Path(filename).suffix.lower()

        if extension not in cls.SUPPORTED_EXTENSIONS:
            raise DataLoaderError(
                "Unsupported file type. "
                "Please upload a CSV or XLSX file."
            )

        cls._validate_file_size(file)

        try:
            if extension == ".csv":
                dataframe = pd.read_csv(file)

            else:
                dataframe = pd.read_excel(file)

        except Exception as exc:
            raise DataLoaderError(
                f"Unable to read '{filename}'. "
                "Check that the file is valid."
            ) from exc

        cls._validate_dataframe(dataframe)

        dataframe = cls._clean_columns(dataframe)

        return dataframe

    @classmethod
    def _validate_file_size(
        cls,
        file: BinaryIO,
    ) -> None:
        """
        Reject files larger than the configured limit.

        Uses standard seek/tell operations instead of relying
        on framework-specific attributes such as file.size.
        """

        try:
            current_position = file.tell()

            file.seek(0, 2)
            size_bytes = file.tell()

            file.seek(current_position)

        except (AttributeError, OSError):
            # Some file-like objects may not support seeking.
            # The application layer performs its own upload-size
            # validation before calling the loader.
            return

        max_size_bytes = (
            cls.MAX_FILE_SIZE_MB
            * 1024
            * 1024
        )

        if size_bytes > max_size_bytes:
            raise DataLoaderError(
                f"File is too large. Maximum size is "
                f"{cls.MAX_FILE_SIZE_MB} MB."
            )

    @staticmethod
    def _validate_dataframe(
        dataframe: pd.DataFrame,
    ) -> None:
        """Ensure the dataset contains usable data."""

        if dataframe.empty:
            raise DataLoaderError(
                "The uploaded dataset is empty."
            )

        if len(dataframe.columns) == 0:
            raise DataLoaderError(
                "The dataset contains no columns."
            )

    @staticmethod
    def _clean_columns(
        dataframe: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Normalize column names for safer SQL queries.

        Example:
            Total Revenue -> total_revenue
        """

        dataframe = dataframe.copy()

        cleaned_columns = (
            dataframe.columns
            .astype(str)
            .str.strip()
            .str.lower()
            .str.replace(
                r"[^\w]+",
                "_",
                regex=True,
            )
            .str.strip("_")
        )

        # Reject headers that become empty after normalization.
        #
        # Examples:
        # ### -> ""
        # !!! -> ""
        if (cleaned_columns == "").any():
            raise DataLoaderError(
                "One or more column names are invalid. "
                "Column names must contain letters, "
                "numbers, or underscores."
            )

        if cleaned_columns.duplicated().any():
            raise DataLoaderError(
                "Duplicate column names were found "
                "after normalization."
            )

        dataframe.columns = cleaned_columns

        return dataframe

    @staticmethod
    def get_metadata(
        dataframe: pd.DataFrame,
    ) -> dict:
        """Return metadata describing the dataset."""

        return {
            "rows": len(dataframe),

            "columns": len(dataframe.columns),

            "column_names": dataframe.columns.tolist(),

            "data_types": {
                column: str(dtype)
                for column, dtype
                in dataframe.dtypes.items()
            },

            "missing_values": {
                column: int(count)
                for column, count
                in dataframe.isna().sum().items()
            },

            "duplicate_rows": int(
                dataframe.duplicated().sum()
            ),
        }