import json

import pandas as pd
from groq import Groq

from config.settings import Settings


class InsightGenerationError(Exception):
    """Raised when a result explanation cannot be generated."""


class InsightGenerator:
    """
    Converts verified database results into concise,
    user-friendly explanations.

    The model is only allowed to explain values that were
    returned by SQLite.
    """

    MAX_RESULT_ROWS = 20

    def __init__(self) -> None:
        Settings.validate()

        self.client = Groq(
            api_key=Settings.GROQ_API_KEY,
        )

        self.model = Settings.GROQ_MODEL

    def generate(
        self,
        question: str,
        result: pd.DataFrame,
    ) -> str:
        """
        Generate a natural-language explanation of a verified result.

        Args:
            question:
                Original user question.

            result:
                DataFrame returned by SQLite.

        Returns:
            Concise explanation grounded only in the result.
        """

        if result.empty:
            return (
                "The query ran successfully, but no matching "
                "records were found."
            )

        result_for_prompt = result.head(
            self.MAX_RESULT_ROWS
        ).copy()

        # Normalize missing values before sending verified
        # results to the explanation model.
        result_for_prompt = result_for_prompt.astype(object)
        result_for_prompt = result_for_prompt.where(
            pd.notna(result_for_prompt),
            "Missing",
        )


        records = result_for_prompt.to_dict(
            orient="records"
        )

        result_json = json.dumps(
            records,
            default=str,
            ensure_ascii=False,
        )

        system_prompt = """
You are the result explanation component of DataLens AI.

The user's analytical question has already been converted to SQL,
validated, and executed against the actual dataset.

You will receive the VERIFIED DATABASE RESULT.

Your job is only to explain that result clearly.

STRICT RULES:

1. Use only information present in the verified result.
2. Never invent numbers, categories, dates, percentages, causes,
   trends, or business facts.
3. Never change the mathematical meaning of a number returned
   by the database.
4. You may format numbers for readability, but never perform
   new analytical calculations.
5. Never claim why something happened unless the database result
   explicitly provides evidence for that explanation.
6. If the result contains a ranking, clearly identify the ranking.
7. Keep the answer concise and useful.
8. Do not mention SQL unless the user specifically asked about SQL.
9. Do not say that you inspected rows that were not provided.
10. If the result is insufficient to fully answer the question,
    clearly say so.
11. Never assume a currency, unit, symbol, or measurement
    that is not explicitly present in the user's question,
    column names, or verified result.
12. If a numeric value has no explicit currency or unit,
    present the number without inventing one.
13. Preserve the meaning of the database values exactly.
14. When presenting floating-point numeric values, round them
    to a maximum of 2 decimal places unless additional precision
    is necessary to correctly answer the question.
15. Do not unnecessarily add decimal places to whole numbers.
16. Number formatting is for presentation only and must not
    change the meaning of the verified database result.
17. If the verified result contains a missing, null, NaN,
    or blank grouping value, describe it simply as "Missing".
18. Do not speculate about why a value is missing.
19. Do not explain technical representations such as NaN
    unless the user explicitly asks about them.
"""

        user_prompt = f"""
USER QUESTION:
{question}

VERIFIED DATABASE RESULT:
{result_json}

Explain the result to the user.
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
                        "content": user_prompt,
                    },
                ],
                temperature=0,
            )

            explanation = (
                response.choices[0]
                .message.content
            )

        except Exception as exc:
            raise InsightGenerationError(
                f"Failed to generate insight: {exc}"
            ) from exc

        if not explanation:
            raise InsightGenerationError(
                "The model returned an empty explanation."
            )

        return explanation.strip()