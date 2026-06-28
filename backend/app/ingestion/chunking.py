import re
from dataclasses import dataclass

import tiktoken

from app.core.config import CHUNK_MAX_TOKENS, CHUNK_OVERLAP_TOKENS

_ENCODING = tiktoken.get_encoding("cl100k_base")

_SECTION_HEADER_RE = re.compile(r"^SECTION[-\s]?\d+", re.IGNORECASE)
_SUBSECTION_HEADER_RE = re.compile(r"^\d+(\.\d+)+\b")
_TOP_LEVEL_ITEM_RE = re.compile(r"^\d+\.\s+\S")


@dataclass
class Chunk:
    text: str
    section: str
    subsection: str | None
    topic: str | None
    chunk_index: int


def count_tokens(text: str) -> int:
    return len(_ENCODING.encode(text))


def reconstruct_headings(text: str) -> str:
    lines = []
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped.startswith("#"):
            lines.append(line)
        elif _SECTION_HEADER_RE.match(stripped) or _SUBSECTION_HEADER_RE.match(stripped):
            lines.append(f"## {stripped}")
        else:
            lines.append(line)
    return "\n".join(lines)


def _parse_header(line: str) -> str:
    return line.lstrip("#").strip().strip("*").strip()


def _split_into_sections(text: str) -> list[tuple[str, str | None, str | None, str]]:
    sections: list[tuple[str, str | None, str | None, str]] = []
    current_section = "UNTITLED"
    current_subsection: str | None = None
    current_topic: str | None = None
    buffer: list[str] = []

    def flush() -> None:
        body = "\n".join(buffer).strip()
        if body:
            sections.append((current_section, current_subsection, current_topic, body))
        buffer.clear()

    for line in text.split("\n"):
        if line.strip().startswith("##"):
            flush()
            header = _parse_header(line)
            if not header:
                continue
            if _SECTION_HEADER_RE.match(header):
                current_section = header
                current_subsection = None
                current_topic = None
            elif _SUBSECTION_HEADER_RE.match(header):
                current_subsection = header
                current_topic = None
            else:
                current_topic = header
        else:
            buffer.append(line)
    flush()
    return sections


def _split_into_items(body: str) -> list[str]:
    paragraphs = [p for p in re.split(r"\n\s*\n", body) if p.strip()]
    has_numbered_items = any(_TOP_LEVEL_ITEM_RE.match(p.strip()) for p in paragraphs)
    if not has_numbered_items:
        return [body.strip()]

    items: list[str] = []
    current: list[str] = []
    for paragraph in paragraphs:
        if _TOP_LEVEL_ITEM_RE.match(paragraph.strip()) and current:
            items.append("\n\n".join(current))
            current = [paragraph]
        else:
            current.append(paragraph)
    if current:
        items.append("\n\n".join(current))
    return items


def _split_oversized(item: str) -> list[str]:
    tokens = _ENCODING.encode(item)
    if len(tokens) <= CHUNK_MAX_TOKENS:
        return [item]

    pieces: list[str] = []
    step = CHUNK_MAX_TOKENS - CHUNK_OVERLAP_TOKENS
    start = 0
    while start < len(tokens):
        window = tokens[start : start + CHUNK_MAX_TOKENS]
        pieces.append(_ENCODING.decode(window))
        if start + CHUNK_MAX_TOKENS >= len(tokens):
            break
        start += step
    return pieces


def chunk_document(text: str) -> list[Chunk]:
    chunks: list[Chunk] = []
    for section, subsection, topic, body in _split_into_sections(text):
        for item in _split_into_items(body):
            for piece in _split_oversized(item):
                stripped = piece.strip()
                if not stripped:
                    continue
                chunks.append(
                    Chunk(
                        text=stripped,
                        section=section,
                        subsection=subsection,
                        topic=topic,
                        chunk_index=len(chunks),
                    )
                )
    return chunks
