import httpx

from app.core.config import HF_EMBED_MODEL, HUGGINGFACE_API_KEY

_API_URL = f"https://api-inference.huggingface.co/models/{HF_EMBED_MODEL}"
_HEADERS = {"Authorization": f"Bearer {HUGGINGFACE_API_KEY}"}
_BATCH_SIZE = 16


def _embed_batch(texts: list[str]) -> list[list[float]]:
    response = httpx.post(
        _API_URL,
        headers=_HEADERS,
        json={"inputs": texts, "options": {"wait_for_model": True}},
        timeout=60.0,
    )
    response.raise_for_status()
    result = response.json()
    embeddings = []
    for item in result:
        # Normalize: HF returns [float,...] or [[float,...]] depending on model config
        emb = item[0] if isinstance(item[0], list) else item
        embeddings.append(emb)
    return embeddings


def _embed(texts: list[str]) -> list[list[float]]:
    results = []
    for i in range(0, len(texts), _BATCH_SIZE):
        results.extend(_embed_batch(texts[i : i + _BATCH_SIZE]))
    return results


def embed_documents(texts: list[str]) -> list[list[float]]:
    return _embed([f"search_document: {text}" for text in texts])


def embed_query(text: str) -> list[float]:
    return _embed([f"search_query: {text}"])[0]
