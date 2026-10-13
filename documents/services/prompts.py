from documents.services.context import build_llm_context

SYSTEM_PROMPT = """
You are a grounded question-answering assistant.

You answer questions using ONLY the supplied context.

STRICT RULES:

1. Never use outside knowledge.
2. Never invent facts.
3. Every factual claim must be supported by the provided context.
4. Cite the source immediately after the claim.
5. Only use citation IDs that actually exist in the context.
6. Never create a citation ID that was not provided.
7. If the context does not contain enough information, say:
   "The provided documents do not contain enough information to answer this question."
8. Do not guess or infer unsupported facts.
9. When multiple sources support a statement, cite all relevant sources.
10. Prefer a concise answer over unnecessary explanation.

Citation format:

[S1]
[S2]
[S1][S3]

The citation IDs correspond exactly to the sources provided
in the context.
""".strip()


def build_context(results: list[dict]) -> str:
    
    if not results:
        return "No relevant context was found"

    context_parts = []

    for index, result in enumerate(results, start=1):
        document_title = result.get(
            "document_title",
            "Unknown document",   
        )

        page_number = result.get(
            "page_number"
        )

        content = result.get(
            "content",
            "",
        )

        source_id = f"S{index}"

        source_header = (
            f"[{source_id}] "
            f"Document: {document_title}"
        )

        if page_number is not None:
            source_header += f", Page: {page_number}"

        context_parts.append(
            f"{source_header}\n"
            f"{content}"
        )

    return "\n\n---\n\n".join(context_parts)  

def build_user_prompt(
    query: str,
    sources: list[dict],
) -> str:

    context = build_llm_context(
        sources
    )

    return f"""
Use the following sources to answer the question.

CONTEXT:

{context}

---

QUESTION:

{query}

---

Instructions:

- Answer using only the context.
- Cite factual claims using the source IDs.
- Do not invent source IDs.
- If the answer cannot be supported by the context,
  say that the provided documents do not contain enough
  information.

ANSWER:
""".strip()