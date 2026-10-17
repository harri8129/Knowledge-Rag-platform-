from functools import lru_cache 
from time import sleep

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
        timeout=settings.OPENROUTER_TIMEOUT_SECONDS,
        max_retries=settings.OPENROUTER_MAX_RETRIES,
    )

def generate_answer(
    system_prompt: str,
    user_prompt: str,
) -> str:
    answer, _ = generate_answer_with_usage(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
    )
    return answer


def generate_answer_with_usage(
    system_prompt: str,
    user_prompt: str,
) -> tuple[str, dict[str, int | float | None]]:

    if not system_prompt.strip():
        raise ValueError(
            "System prompt cannot be empty."
        )

    if not user_prompt.strip():
        raise ValueError(
            "User prompt cannot be empty."
        )

    client = get_llm_client()

    response = None
    response_body = None
    for attempt in range(3):
        try:
            raw_response = (
                client.chat.completions.with_raw_response.create(
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
            )
        except Exception as exc:
            raise RuntimeError(
                f"OpenRouter request failed: {exc}"
            ) from exc

        response_body = raw_response.http_response.json()
        provider_error = response_body.get("error")
        if provider_error:
            error_code = provider_error.get("code")
            metadata = provider_error.get("metadata") or {}
            is_overloaded = (
                error_code == 503
                or metadata.get("error_type") == "provider_overloaded"
            )
            if is_overloaded and attempt < 2:
                sleep(2 ** attempt)
                continue
            raise RuntimeError(
                "OpenRouter provider error "
                f"{error_code}: {provider_error.get('message', 'unknown error')}"
            )

        response = raw_response.parse()
        break

    if response is None or response_body is None:
        raise RuntimeError(
            "OpenRouter request completed without a response."
        )

    if not response.choices:
        raise RuntimeError(
            "OpenRouter returned no choices for "
            f"completion {response.id} using model {response.model}."
        )

    content = response.choices[0].message.content

    if not content:
        raise RuntimeError(
            "OpenRouter returned an empty response."
        )

    usage = response.usage
    provider_usage = response_body.get("usage") or {}
    reported_cost = provider_usage.get("cost")
    cost_usd = (
        float(reported_cost)
        if isinstance(reported_cost, (int, float))
        and not isinstance(reported_cost, bool)
        else None
    )
    return (
        content.strip(),
        {
            "prompt_tokens": (
                usage.prompt_tokens if usage else None
            ),
            "completion_tokens": (
                usage.completion_tokens if usage else None
            ),
            "total_tokens": (
                usage.total_tokens if usage else None
            ),
            "cost_usd": cost_usd,
        },
    )