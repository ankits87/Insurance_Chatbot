import logging

from app.core.config import DATA_DIR
from app.core.embeddings import embed_documents
from app.core.vectorstore import get_client, rebuild_collection
from app.ingestion.chunking import chunk_document
from app.ingestion.cleaning import clean_text
from app.ingestion.identifiers import chunk_id
from app.ingestion.naming import derive_product_name
from app.rag.index_cache import invalidate as invalidate_index_cache

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _load_documents() -> list[tuple[str, str]]:
    documents = []
    for path in sorted(DATA_DIR.glob("*.md")):
        text = path.read_text(encoding="utf-8").strip()
        if not text:
            logger.warning("Skipping empty file: %s", path.name)
            continue
        documents.append((path.name, text))
    return documents


def run_ingestion() -> None:
    documents = _load_documents()
    if not documents:
        logger.warning("No documents found in %s", DATA_DIR)
        return

    ids: list[str] = []
    texts: list[str] = []
    metadatas: list[dict] = []

    for source_file, raw_text in documents:
        cleaned = clean_text(raw_text)
        for chunk in chunk_document(cleaned):
            ids.append(chunk_id(source_file, chunk.section, chunk.subsection, chunk.topic, chunk.chunk_index))
            texts.append(chunk.text)
            metadatas.append(
                {
                    "source_file": source_file,
                    "product_name": derive_product_name(source_file),
                    "section": chunk.section,
                    "subsection": chunk.subsection or "",
                    "topic": chunk.topic or "",
                    "chunk_index": chunk.chunk_index,
                }
            )
        logger.info("Chunked %s into %d chunks so far.", source_file, len(texts))

    logger.info("Embedding %d chunks via Ollama...", len(texts))
    embeddings = embed_documents(texts)

    client = get_client()
    collection = rebuild_collection(client)
    collection.add(ids=ids, embeddings=embeddings, documents=texts, metadatas=metadatas)
    invalidate_index_cache()
    logger.info("Stored %d chunks in Chroma collection '%s'.", len(texts), collection.name)


if __name__ == "__main__":
    run_ingestion()
