import httpx

from app.core.config import NOMIC_API_KEY

_API_URL = "https://api-atlas.nomic.ai/v1/embedding/text"
_HEADERS = {"Authorization": f"Bearer {NOMIC_API_KEY}"}
_BATCH_SIZE = 16


def _embed_batch(texts: list[str]) -> list[list[float]]:
    response = httpx.post(
        _API_URL,
        headers=_HEADERS,
        json={"model": "nomic-embed-text-v1", "texts": texts},
        timeout=60.0,
    )
    response.raise_for_status()
    return response.json()["embeddings"]


def _embed(texts: list[str]) -> list[list[float]]:
    results = []
    for i in range(0, len(texts), _BATCH_SIZE):
        results.extend(_embed_batch(texts[i : i + _BATCH_SIZE]))
    return results


def embed_documents(texts: list[str]) -> list[list[float]]:
    return _embed([f"search_document: {text}" for text in texts])


def embed_query(text: str) -> list[float]:
    return _embed([f"search_query: {text}"])[0]
