import os

from dotenv import load_dotenv


load_dotenv()


class SettingsError(Exception):
    """Raised when required application configuration is missing."""


class Settings:
    """Application configuration loaded from environment variables."""

    GROQ_API_KEY = os.getenv("GROQ_API_KEY")
    GROQ_MODEL = os.getenv(
        "GROQ_MODEL",
        "llama-3.3-70b-versatile",
    )

    @classmethod
    def validate(cls) -> None:
        """Ensure required configuration values are available."""

        if not cls.GROQ_API_KEY:
            raise SettingsError(
                "GROQ_API_KEY is missing. "
                "Add it to your .env file."
            )