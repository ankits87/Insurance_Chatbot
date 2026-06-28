import json
from typing import TYPE_CHECKING

import httpx
from groq import Groq, GroqError

from app.core.config import RERANK_MODEL

if TYPE_CHECKING:
    from app.rag.retrieval import RetrievedChunk

_client = Groq()

SYSTEM_PROMPT = (
    "You rank candidate passages from insurance policy documents by relevance to a question. "
    "You will be given a question and a numbered list of passages. Respond with a JSON object "
    '{"ranked": [passage numbers, most relevant first]} listing only passages that are genuinely '
    "relevant to the question, most relevant first. Omit passages that are not relevant."
)


def _format_passages(chunks: list["RetrievedChunk"]) -> str:
    return "\n\n".join(
        f"[{i}] ({chunk.product_name} | {chunk.section} > {chunk.subsection})\n{chunk.text}"
        for i, chunk in enumerate(chunks)
    )


def rerank_chunks(query: str, chunks: list["RetrievedChunk"], top_k: int) -> list["RetrievedChunk"]:
    if len(chunks) <= top_k:
        return chunks

    prompt = f"Question: {query}\n\nPassages:\n{_format_passages(chunks)}"
    try:
        response = _client.chat.completions.create(
            model=RERANK_MODEL,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
        )
        order = json.loads(response.choices[0].message.content)["ranked"]
    except (httpx.ConnectError, httpx.HTTPError, ConnectionError, GroqError, json.JSONDecodeError, KeyError, TypeError):
        return chunks[:top_k]

    seen = set()
    reranked = []
    for index in order:
        if isinstance(index, int) and 0 <= index < len(chunks) and index not in seen:
            seen.add(index)
            reranked.append(chunks[index])

    return reranked[:top_k] if reranked else chunks[:top_k]
