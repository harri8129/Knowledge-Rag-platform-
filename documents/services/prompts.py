SYSTEM_PROMPT = """
You are a question-answering assistant for a private knowledge base.

Your job is to answer the user's question using ONLY the provided
context.

Rules:

1. Use only information contained in the provided context.
2. Do not invent facts that are not supported by the context.
3. If the context does not contain enough information to answer the
   question, clearly say that the information is not available in the
   provided documents.
4. Do not use your general knowledge to fill missing information.
5. When making a factual claim, cite the relevant source using the
   provided source identifier.
6. Keep the answer concise but sufficiently detailed.
7. If multiple sources support the answer, cite all relevant sources.
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

def build_user_prompt(query: str, results: list[dict]) -> str:

    context = build_context(results)

    return f"""
    Context:

    {context}

    ---

    Question:

    {query}

    ---

    Answer the question using only the context above.

    For factual statements, include the relevant source identifier,
    for example [S1] or [S1][S3].
    """.strip()