import httpx
from groq import Groq, GroqError

from app.core.config import QUERY_REWRITE_HISTORY_TURNS, QUERY_REWRITE_MODEL

_client = Groq()

SYSTEM_PROMPT = (
    "Given a conversation history and a follow-up question, rewrite the follow-up into a "
    "fully standalone question that resolves any references (e.g. product names, pronouns) "
    "using the history. If the follow-up is already standalone, return it unchanged. "
    "IMPORTANT: If the follow-up is asking which product to buy, which plan is better, "
    "or comparing products, do NOT inject product names from the history — return it exactly "
    "as written. Only carry forward product context when the follow-up is clearly a "
    "continuation about the same product or topic from the prior turn. "
    "Output ONLY the rewritten question, nothing else."
)


def _format_history(history: list[dict]) -> str:
    recent = history[-QUERY_REWRITE_HISTORY_TURNS:]
    return "\n\n".join(f"Q: {turn['query']}\nA: {turn['answer']}" for turn in recent)


def rewrite_query(query: str, history: list[dict]) -> str:
    if not history:
        return query

    prompt = f"Conversation history:\n{_format_history(history)}\n\nFollow-up question: {query}"
    try:
        response = _client.chat.completions.create(
            model=QUERY_REWRITE_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
        )
    except (httpx.ConnectError, httpx.HTTPError, ConnectionError, GroqError):
        return query

    rewritten = response.choices[0].message.content.strip()
    return rewritten or query
