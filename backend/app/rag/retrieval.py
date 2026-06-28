from dataclasses import dataclass

from app.core.config import COLLECTION_NAME, HYBRID_CANDIDATE_MULTIPLIER, RERANK_SPREAD_THRESHOLD, RRF_K, TOP_K
from app.core.embeddings import embed_query
from app.core.vectorstore import get_client
from app.rag.index_cache import expand_query_tokens, get_cache, tokenize
from app.rag.rerank import rerank_chunks


@dataclass
class RetrievedChunk:
    text: str
    source_file: str
    product_name: str
    section: str
    subsection: str
    topic: str
    score: float


@dataclass
class RetrievalResult:
    chunks: list[RetrievedChunk]
    top_vector_score: float


def _detect_product(query: str) -> str | None:
    cache = get_cache()
    query_tokens = set(tokenize(query))
    matches = [product for product, tokens in cache.product_tokens.items() if query_tokens & tokens]
    return matches[0] if len(matches) == 1 else None


def _vector_candidates(query_embedding: list[float], n: int, product_filter: str | None):
    client = get_client()
    collection = client.get_collection(COLLECTION_NAME)
    where = {"product_name": product_filter} if product_filter else None
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=n,
        where=where,
        include=["documents", "metadatas", "distances"],
    )
    ids = results["ids"][0]
    scores = [1 - distance for distance in results["distances"][0]]
    return ids, scores, results["documents"][0], results["metadatas"][0]


def _needs_rerank(vector_scores: list[float], top_k: int) -> bool:
    if len(vector_scores) < top_k:
        return True
    spread = vector_scores[0] - vector_scores[top_k - 1]
    return spread >= RERANK_SPREAD_THRESHOLD


def _bm25_candidate_indices(query: str, n: int, product_filter: str | None) -> list[int]:
    cache = get_cache()
    scores = cache.bm25.get_scores(expand_query_tokens(tokenize(query), cache.bm25))
    ranked = sorted(range(len(cache.records)), key=lambda i: scores[i], reverse=True)
    if product_filter:
        ranked = [i for i in ranked if cache.records[i].metadata["product_name"] == product_filter]
    return ranked[:n]


def retrieve(query: str, top_k: int = TOP_K) -> RetrievalResult:
    cache = get_cache()
    product_filter = _detect_product(query)
    candidate_n = top_k * HYBRID_CANDIDATE_MULTIPLIER

    vector_ids, vector_scores, vector_texts, vector_metas = _vector_candidates(
        embed_query(query), candidate_n, product_filter
    )
    top_vector_score = vector_scores[0] if vector_scores else 0.0
    bm25_indices = _bm25_candidate_indices(query, candidate_n, product_filter)

    fused_scores: dict[str, float] = {}
    chunk_lookup: dict[str, tuple[str, dict]] = {}

    for rank, (chunk_id, text, metadata) in enumerate(zip(vector_ids, vector_texts, vector_metas), start=1):
        fused_scores[chunk_id] = fused_scores.get(chunk_id, 0.0) + 1 / (RRF_K + rank)
        chunk_lookup[chunk_id] = (text, metadata)

    for rank, index in enumerate(bm25_indices, start=1):
        record = cache.records[index]
        fused_scores[record.chunk_id] = fused_scores.get(record.chunk_id, 0.0) + 1 / (RRF_K + rank)
        chunk_lookup.setdefault(record.chunk_id, (record.text, record.metadata))

    ranked_ids = sorted(fused_scores, key=lambda chunk_id: fused_scores[chunk_id], reverse=True)[:candidate_n]

    candidates = []
    for chunk_id in ranked_ids:
        text, metadata = chunk_lookup[chunk_id]
        candidates.append(
            RetrievedChunk(
                text=text,
                source_file=metadata["source_file"],
                product_name=metadata["product_name"],
                section=metadata["section"],
                subsection=metadata["subsection"],
                topic=metadata["topic"],
                score=fused_scores[chunk_id],
            )
        )

    if _needs_rerank(vector_scores, top_k):
        chunks = rerank_chunks(query, candidates, top_k)
    else:
        chunks = candidates[:top_k]

    return RetrievalResult(chunks=chunks, top_vector_score=top_vector_score)
