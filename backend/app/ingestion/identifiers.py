import hashlib


def chunk_id(source_file: str, section: str, subsection: str | None, topic: str | None, chunk_index: int) -> str:
    raw = f"{source_file}|{section}|{subsection}|{topic}|{chunk_index}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
