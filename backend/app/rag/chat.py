from dataclasses import dataclass

from groq import Groq

from app.core.config import GROQ_MODEL, RELEVANCE_THRESHOLD
from app.rag.query_rewrite import rewrite_query
from app.rag.retrieval import RetrievedChunk, retrieve

_client = Groq()

SYSTEM_PROMPT = (
    "You are a helpful assistant answering questions about insurance policy documents. "
    "Answer ONLY using the provided context. If the context doesn't contain the answer, say so honestly. "
    "Be precise and concise — exact wording matters in insurance policy language. "
    "Each passage is labeled with its product name and section for your reference only — do not "
    "quote these labels in your answer. If asked which product something applies to, state the "
    "product name in your own words rather than saying the product isn't specified. "
    "If the context contains facts from more than one product, do not blend them into one "
    "undifferentiated statement — clearly state which product each fact applies to."
)

COMPARISON_PROMPT_SUFFIX = (
    "\n\n(The user is asking which product to choose — for each product in the context, "
    "state whether and how it covers this, then conclude with a recommendation based on the context.)"
)

NOT_FOUND_ANSWER = "I couldn't find anything relevant to that in the policy documents."

_COMPARISON_SIGNALS = {
    "which product", "which plan", "which policy", "what product",
    "should i buy", "should i choose", "should i get", "should i take",
    "best for", "compare", "recommend", "which one",
}


def _is_comparison_query(query: str) -> bool:
    q = query.lower()
    return any(signal in q for signal in _COMPARISON_SIGNALS)


@dataclass
class ChatAnswer:
    answer: str
    sources: list[RetrievedChunk]
    grounded: bool
    products: list[str]


def _unique_products(chunks: list[RetrievedChunk]) -> list[str]:
    return list(dict.fromkeys(chunk.product_name for chunk in chunks))


def _build_prompt(query: str, chunks: list[RetrievedChunk], comparison: bool = False) -> str:
    context_blocks = []
    for chunk in chunks:
        section_path = " > ".join(part for part in (chunk.section, chunk.subsection, chunk.topic) if part)
        label = f"{chunk.product_name} | {section_path}" if section_path else chunk.product_name
        context_blocks.append(f"[{label}]\n{chunk.text}")
    context = "\n\n---\n\n".join(context_blocks)
    prompt = f"Context:\n{context}\n\nQuestion: {query}"
    if comparison:
        prompt += COMPARISON_PROMPT_SUFFIX
    return prompt


def answer_question(query: str, history: list[dict] | None = None) -> ChatAnswer:
    comparison = _is_comparison_query(query)

    if comparison:
        effective_query = query
    else:
        effective_query = rewrite_query(query, history) if history else query

    result = retrieve(effective_query)
    chunks = result.chunks
    if not chunks or result.top_vector_score < RELEVANCE_THRESHOLD:
        return ChatAnswer(answer=NOT_FOUND_ANSWER, sources=[], grounded=False, products=[])

    response = _client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": _build_prompt(effective_query, chunks, comparison=comparison)},
        ],
    )
    return ChatAnswer(
        answer=response.choices[0].message.content,
        sources=chunks,
        grounded=True,
        products=_unique_products(chunks),
    )
