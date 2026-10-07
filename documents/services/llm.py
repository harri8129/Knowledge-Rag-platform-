from django.core.mail import message
from functools import lru_cache 

from django.conf import settings
from openai import OpenAI

@lru_cache(maxsize=1)
def get_llm_client() -> OpenAI:
    if not settings.OPENROUTER_API_KEY:
        raise RuntimeError(
            "OPENROUTER_API_KEY missing in .env"
        )
    return OpenAI(
        base_url=settings.OPENROUTER_BASE_URL,
        api_key=settings.OPENROUTER_API_KEY,
    )

def generate_answer(
    system_prompt: str,
    user_prompt: str,
) -> str:

    if not system_prompt.strip():
        raise ValueError(
            "System prompt cannot be empty."
        )

    if not user_prompt.strip():
        raise ValueError(
            "User prompt cannot be empty."
        )

    client = get_llm_client()

    try:

        response = client.chat.completions.create(
            model=settings.OPENROUTER_MODEL,
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
        )

    except Exception as exc:

        raise RuntimeError(
            f"OpenRouter request failed: {exc}"
        ) from exc

    if not response.choices:
        raise RuntimeError(
            "OpenRouter returned no choices."
        )

    content = response.choices[0].message.content

    if not content:
        raise RuntimeError(
            "OpenRouter returned an empty response."
        )

    return content.strip()