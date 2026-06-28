from dataclasses import dataclass
from pathlib import Path

from app.core.config import DATA_DIR
from app.core.embeddings import embed_documents
from app.core.vectorstore import get_client, get_or_create_collection, replace_source_file
from app.ingestion.chunking import chunk_document, reconstruct_headings
from app.ingestion.cleaning import clean_text, strip_repeated_lines
from app.ingestion.converters import extract_docx_markdown, extract_pdf_pages
from app.ingestion.identifiers import chunk_id
from app.ingestion.naming import derive_product_name
from app.rag.index_cache import invalidate as invalidate_index_cache

SUPPORTED_EXTENSIONS = {".pdf", ".docx"}


@dataclass
class IngestResult:
    source_file: str
    product_name: str
    chunks_added: int


def _convert_to_markdown(filename: str, content: bytes) -> str:
    extension = Path(filename).suffix.lower()
    if extension == ".pdf":
        pages = extract_pdf_pages(content)
        text = strip_repeated_lines(pages)
        return reconstruct_headings(text)
    if extension == ".docx":
        return extract_docx_markdown(content)
    raise ValueError(f"Unsupported file type: {extension}. Supported: {sorted(SUPPORTED_EXTENSIONS)}")


def ingest_uploaded_file(filename: str, content: bytes) -> IngestResult:
    extension = Path(filename).suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Unsupported file type: {extension}. Supported: {sorted(SUPPORTED_EXTENSIONS)}")

    markdown = _convert_to_markdown(filename, content)
    cleaned = clean_text(markdown)
    if not cleaned:
        raise ValueError("No extractable text found in the uploaded file.")

    snapshot_path = DATA_DIR / f"{Path(filename).stem}.md"
    snapshot_path.write_text(cleaned, encoding="utf-8")

    product_name = derive_product_name(filename)

    ids: list[str] = []
    texts: list[str] = []
    metadatas: list[dict] = []
    for chunk in chunk_document(cleaned):
        ids.append(chunk_id(filename, chunk.section, chunk.subsection, chunk.topic, chunk.chunk_index))
        texts.append(chunk.text)
        metadatas.append(
            {
                "source_file": filename,
                "product_name": product_name,
                "section": chunk.section,
                "subsection": chunk.subsection or "",
                "topic": chunk.topic or "",
                "chunk_index": chunk.chunk_index,
            }
        )

    embeddings = embed_documents(texts) if texts else []

    client = get_client()
    collection = get_or_create_collection(client)
    replace_source_file(collection, filename, ids, embeddings, texts, metadatas)
    invalidate_index_cache()

    return IngestResult(source_file=filename, product_name=product_name, chunks_added=len(texts))
