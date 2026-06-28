import re

_NOISE_MARKERS = [
    "indusindinsurance.com",
    "irdai registration no",
    "~~ei~~",
    "download no",
    "corporate identity number",
    "whatsapp",
]

REPEATED_LINE_THRESHOLD = 0.3


def strip_repeated_lines(pages: list[str]) -> str:
    if len(pages) < 3:
        return "\n\n".join(pages)

    page_lines = [[line.strip() for line in page.split("\n")] for page in pages]

    counts: dict[str, int] = {}
    for lines in page_lines:
        for line in set(lines):
            if line:
                counts[line] = counts.get(line, 0) + 1

    min_count = REPEATED_LINE_THRESHOLD * len(pages)
    noisy = {line for line, count in counts.items() if count >= min_count}

    cleaned_pages = []
    for lines in page_lines:
        kept = [line for line in lines if line.strip() not in noisy]
        cleaned_pages.append("\n".join(kept))
    return "\n\n".join(cleaned_pages)


def clean_text(text: str) -> str:
    lines = text.split("\n")
    kept = [line for line in lines if not any(marker in line.lower() for marker in _NOISE_MARKERS)]
    cleaned = "\n".join(kept)
    return re.sub(r"\n{3,}", "\n\n", cleaned).strip()
