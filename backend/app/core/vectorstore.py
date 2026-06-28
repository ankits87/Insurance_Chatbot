import chromadb

from app.core.config import CHROMA_DB_DIR, COLLECTION_NAME


def get_client() -> chromadb.ClientAPI:
    return chromadb.PersistentClient(path=str(CHROMA_DB_DIR))


def rebuild_collection(client: chromadb.ClientAPI):
    existing = {c.name for c in client.list_collections()}
    if COLLECTION_NAME in existing:
        client.delete_collection(COLLECTION_NAME)
    return client.create_collection(COLLECTION_NAME, metadata={"hnsw:space": "cosine"})


def get_or_create_collection(client: chromadb.ClientAPI):
    return client.get_or_create_collection(COLLECTION_NAME, metadata={"hnsw:space": "cosine"})


def replace_source_file(collection, source_file: str, ids: list[str], embeddings: list[list[float]], texts: list[str], metadatas: list[dict]) -> None:
    collection.delete(where={"source_file": source_file})
    if ids:
        collection.add(ids=ids, embeddings=embeddings, documents=texts, metadatas=metadatas)
