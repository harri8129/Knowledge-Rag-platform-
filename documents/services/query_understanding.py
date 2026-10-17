from dataclasses import dataclass
import json

from documents.services.llm import generate_answer_with_usage


@dataclass
class Queryplan:
      original_query : str
      rewritten_query : str 
      expanded_queries : list[str]

QUERY_REWRITE_SYSTEM_PROMPT = """
You are a search query optimization system.

Your job is to improve a user's question for retrieving
relevant documents from a knowledge base.

Return ONLY valid JSON.

Required format:

{
    "rewritten_query": "string",
    "expanded_queries": [
        "string",
        "string"
    ]
}

Rules:

1. Preserve the original meaning.
2. Do not answer the question.
3. Do not invent facts.
4. Use important technical terms from the original query.
5. Prefer concise search queries.
6. Generate at most 3 expanded queries.
7. If the original query is already precise, keep it mostly unchanged.
""".strip()


def build_query_rewrite_prompt(query:str,) -> str :

    return f"""
      Optimize the following search query.

      Original query:

      {query}

      Return JSON only.
      """.strip()


def parse_query_plan(
    original_query: str,
    raw_response: str,
) -> Queryplan:

    try :
        data = json.loads(raw_response)
    except json.JSONDecodeError:
        return Queryplan(
            original_query=original_query,
            rewritten_query=original_query,
            expanded_queries=[],
        )

    rewritten_query = (
        data.get("rewritten_query",original_query,)
                 or original_query
    )

    expanded_queries = data.get(
        "expanded_queries",
        []
    )

    if not isinstance(expanded_queries,list,):
        expanded_queries = []

    cleaned_queries = []

    for item in expanded_queries:

        if not isinstance(item,str):
            continue

        if not item:
            continue

        if item == original_query:
            continue

        if item == rewritten_query:
            continue

        if item not in cleaned_queries:
            cleaned_queries.append(item) 

    return Queryplan(
        original_query=original_query,
        rewritten_query=rewritten_query.strip(),
        expanded_queries=cleaned_queries[:3],
    )       


def analyze_query(query : str,) -> Queryplan:
    plan, _ = analyze_query_with_usage(query)
    return plan


def analyze_query_with_usage(
    query: str,
) -> tuple[Queryplan, dict[str, int | float | None]]:

    query = query.strip()

    if not query:
        raise ValueError("Query cannot be empty")

    prompt = build_query_rewrite_prompt(query)

    response, usage = generate_answer_with_usage(
        system_prompt=(
            QUERY_REWRITE_SYSTEM_PROMPT
        ),
        user_prompt=prompt
    )

    return (
        parse_query_plan(
            original_query=query,
            raw_response=response,
        ),
        usage,
    )