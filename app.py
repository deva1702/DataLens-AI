import hashlib
import logging

import streamlit as st

from assistant.orchestrator import AnalyticsAssistant, AnalyticsError
from database.database_manager import DatabaseManager, DatabaseError
from preprocessing.data_loader import DataLoader, DataLoaderError
from visualization.chart_builder import ChartBuilder
from visualization.result_formatter import ResultFormatter


# Configuration
MAX_UPLOAD_SIZE_MB = 50
MAX_UPLOAD_SIZE_BYTES = MAX_UPLOAD_SIZE_MB * 1024 * 1024
ALLOWED_EXTENSIONS = {"csv", "xlsx"}

logger = logging.getLogger(__name__)


# Page configuration
st.set_page_config(
    page_title="DataLens AI",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# Helpers
def get_file_extension(filename: str) -> str:
    """Return the normalized file extension."""
    if "." not in filename:
        return ""
    return filename.rsplit(".", 1)[-1].lower()


def calculate_file_hash(file_bytes: bytes) -> str:
    """Generate a SHA-256 identity for the uploaded dataset."""
    return hashlib.sha256(file_bytes).hexdigest()


def reset_analysis_state() -> None:
    """Clear analysis state when the active dataset changes."""
    st.session_state.last_analysis = None
    st.session_state.query_history = []
    st.session_state.question_input = ""


def initialize_session_state() -> None:
    """Initialize session-scoped application state."""
    if "database" not in st.session_state:
        st.session_state.database = DatabaseManager()

    if "dataset_hash" not in st.session_state:
        st.session_state.dataset_hash = None

    if "last_analysis" not in st.session_state:
        st.session_state.last_analysis = None

    if "question_input" not in st.session_state:
        st.session_state.question_input = ""

    if "query_history" not in st.session_state:
        st.session_state.query_history = []


# Session initialization
initialize_session_state()
database = st.session_state.database


# Header
st.title("📊 DataLens AI")
st.caption(
    "Upload a CSV or Excel dataset and ask questions "
    "about it using natural language."
)


# File upload
uploaded_file = st.file_uploader(
    "Upload dataset",
    type=["csv", "xlsx"],
    help=(
        f"Supported formats: CSV and XLSX. "
        f"Maximum file size: {MAX_UPLOAD_SIZE_MB} MB."
    ),
)

if uploaded_file is None:
    st.info("Upload a CSV or Excel dataset to begin.")
    st.stop()


# Upload validation
extension = get_file_extension(uploaded_file.name)

if extension not in ALLOWED_EXTENSIONS:
    st.error("Unsupported file type. Please upload a CSV or XLSX file.")
    st.stop()

file_bytes = uploaded_file.getvalue()

if not file_bytes:
    st.error("The uploaded file is empty.")
    st.stop()

if len(file_bytes) > MAX_UPLOAD_SIZE_BYTES:
    st.error(
        f"The uploaded file exceeds the {MAX_UPLOAD_SIZE_MB} MB limit."
    )
    st.stop()

current_dataset_hash = calculate_file_hash(file_bytes)


# Load dataset
try:
    uploaded_file.seek(0)

    dataframe = DataLoader.load(
        file=uploaded_file,
        filename=uploaded_file.name,
    )
    metadata = DataLoader.get_metadata(dataframe)

except DataLoaderError as exc:
    logger.warning("Dataset loading failed: %s", exc)
    st.error(
        "The dataset could not be loaded. "
        "Check that the file is a valid CSV or Excel file."
    )
    st.stop()

except Exception:
    logger.exception("Unexpected dataset loading error.")
    st.error("An unexpected error occurred while loading the dataset.")
    st.stop()

if dataframe.empty:
    st.error("The uploaded dataset contains no rows.")
    st.stop()

if len(dataframe.columns) == 0:
    st.error("The uploaded dataset contains no columns.")
    st.stop()


# Handle dataset changes
if st.session_state.dataset_hash != current_dataset_hash:
    try:
        database.load_dataframe(dataframe)
        st.session_state.dataset_hash = current_dataset_hash
        reset_analysis_state()

    except DatabaseError as exc:
        logger.warning("Database initialization failed: %s", exc)
        st.error("The dataset could not be prepared for analysis.")
        st.stop()

    except Exception:
        logger.exception("Unexpected database initialization error.")
        st.error(
            "An unexpected error occurred while preparing the dataset."
        )
        st.stop()


# Verify database
try:
    database_rows = database.get_row_count()

    if database_rows != metadata["rows"]:
        logger.error(
            "Dataset/database row mismatch. Dataset=%s Database=%s",
            metadata["rows"],
            database_rows,
        )
        st.error("The dataset could not be verified correctly.")
        st.stop()

except DatabaseError as exc:
    logger.warning("Database verification failed: %s", exc)
    st.error("The dataset database could not be verified.")
    st.stop()


# Dataset summary
st.success(f"Loaded {uploaded_file.name}")

metric1, metric2, metric3 = st.columns(3)
metric1.metric("Rows", f"{metadata['rows']:,}")
metric2.metric("Columns", f"{metadata['columns']:,}")
metric3.metric("Duplicate Rows", f"{metadata['duplicate_rows']:,}")

st.divider()


# 60 / 40 workspace
data_panel, assistant_panel = st.columns([3, 2], gap="large")


# LEFT: Analytics and evidence
with data_panel:
    st.subheader("Analytics")

    analysis = st.session_state.last_analysis

    if analysis is None:
        st.info(
            "Ask a question from the assistant panel "
            "to generate an analysis."
        )
    else:
        st.markdown(f"**Question:** {analysis.question}")
        st.markdown("#### Supporting Data")

        if analysis.data.empty:
            st.info("The query returned no matching records.")
        else:
            display_result = ResultFormatter.format_dataframe(
                analysis.data
            )

            st.dataframe(
                display_result,
                width="stretch",
                hide_index=True,
            )

            if len(analysis.data) >= 2:
                chart_rendered = ChartBuilder.render(display_result)

                if not chart_rendered:
                    st.caption(
                        "A visualization is not useful for this result."
                    )

    with st.expander(
        "Dataset Preview",
        expanded=analysis is None,
    ):
        st.dataframe(
            dataframe.head(20),
            width="stretch",
            hide_index=True,
        )

    with st.expander("Dataset Schema"):
        schema_data = [
            {
                "Column": column,
                "Type": metadata["data_types"][column],
                "Missing Values": metadata["missing_values"][column],
            }
            for column in metadata["column_names"]
        ]

        st.dataframe(
            schema_data,
            width="stretch",
            hide_index=True,
        )

    with st.expander("Data Quality"):
        total_missing = sum(metadata["missing_values"].values())

        quality1, quality2 = st.columns(2)
        quality1.metric("Missing Values", f"{total_missing:,}")
        quality2.metric(
            "Duplicate Rows",
            f"{metadata['duplicate_rows']:,}",
        )

# RIGHT: AI assistant
with assistant_panel:
    st.subheader("💬 Ask Your Data")
    st.caption("Ask analytical questions in plain English.")

    with st.form("analytics_form", clear_on_submit=False):
        question = st.text_area(
            "Question",
            key="question_input",
            placeholder="Ask a question about the uploaded dataset...",
            height=100,
            max_chars=500,
        )

        analyze_button = st.form_submit_button(
            "Analyze",
            type="primary",
            use_container_width=True,
        )

    if analyze_button:
        clean_question = question.strip()

        if not clean_question:
            st.warning("Enter a question before analyzing.")
        else:
            try:
                with st.spinner("Analyzing your data..."):
                    assistant = AnalyticsAssistant(
                        database=database,
                        dataframe=dataframe,
                    )
                    new_analysis = assistant.analyze(clean_question)

                st.session_state.last_analysis = new_analysis

                st.session_state.query_history.append(
                    {
                        "question": new_analysis.question,
                        "answer": new_analysis.insight,
                        "sql": new_analysis.sql,
                    }
                )

                st.rerun()

            except AnalyticsError as exc:
                logger.warning("Analytics request failed: %s", exc)
                error_message = str(exc)

                if "cannot be answered" in error_message.lower():
                    st.warning(
                        "This question cannot be answered "
                        "from the available dataset."
                    )
                else:
                    st.error(
                        "DataLens could not complete this analysis. "
                        "Try rephrasing the question."
                    )

            except Exception:
                logger.exception("Unexpected analytics error.")
                st.error(
                    "An unexpected analysis error occurred. "
                    "Please try again."
                )

    analysis = st.session_state.last_analysis

    if analysis is not None:
        st.markdown("### Answer")
        st.write(analysis.insight)

        with st.expander("View generated SQL"):
            st.code(
                analysis.sql,
                language="sql",
            )

    if st.session_state.query_history:
        st.markdown("### Recent Questions")

        recent_history = st.session_state.query_history[-5:]

        for item in reversed(recent_history):
            with st.expander(item["question"]):
                st.write(item["answer"])

                with st.expander("SQL"):
                    st.code(
                        item["sql"],
                        language="sql",
                    )