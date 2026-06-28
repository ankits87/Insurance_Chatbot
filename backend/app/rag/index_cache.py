import re
from dataclasses import dataclass

from rank_bm25 import BM25Okapi

from app.core.vectorstore import get_client, get_or_create_collection

_TOKEN_RE = re.compile(r"[a-z0-9]+")

_STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "if", "is", "are", "was", "were", "be", "been",
    "being", "to", "of", "in", "on", "at", "by", "for", "with", "about", "under", "over",
    "this", "that", "these", "those", "it", "its", "as", "from", "into", "than", "then",
    "what", "which", "who", "whom", "when", "where", "why", "how", "any", "all", "not",
    "no", "do", "does", "did", "can", "will", "shall", "may", "i", "s",
}


def tokenize(text: str) -> list[str]:
    return [token for token in _TOKEN_RE.findall(text.lower()) if token not in _STOPWORDS]


def expand_query_tokens(tokens: list[str], bm25: BM25Okapi) -> list[str]:
    known = set(bm25.idf.keys())
    expanded = list(tokens)
    for token in tokens:
        if len(token) < 6:
            continue
        for i in range(3, len(token) - 2):
            left, right = token[:i], token[i:]
            if left in known and right in known:
                expanded.extend([left, right])
                break
    return expanded


@dataclass
class ChunkRecord:
    chunk_id: str
    text: str
    metadata: dict


@dataclass
class IndexCache:
    records: list[ChunkRecord]
    bm25: BM25Okapi
    product_tokens: dict[str, set[str]]


_cache: IndexCache | None = None


def invalidate() -> None:
    global _cache
    _cache = None


def _build_product_tokens(product_names: set[str]) -> dict[str, set[str]]:
    name_tokens = {name: set(tokenize(name)) for name in product_names}
    token_counts: dict[str, int] = {}
    for tokens in name_tokens.values():
        for token in tokens:
            token_counts[token] = token_counts.get(token, 0) + 1
    return {
        name: {token for token in tokens if token_counts[token] == 1}
        for name, tokens in name_tokens.items()
    }


def _build_cache() -> IndexCache:
    client = get_client()
    collection = get_or_create_collection(client)
    result = collection.get(include=["documents", "metadatas"])

    records = [
        ChunkRecord(chunk_id=cid, text=text, metadata=metadata)
        for cid, text, metadata in zip(result["ids"], result["documents"], result["metadatas"])
    ]
    bm25 = BM25Okapi([tokenize(record.text) for record in records])
    product_tokens = _build_product_tokens({record.metadata["product_name"] for record in records})

    return IndexCache(records=records, bm25=bm25, product_tokens=product_tokens)


def get_cache() -> IndexCache:
    global _cache
    if _cache is None:
        _cache = _build_cache()
    return _cache
