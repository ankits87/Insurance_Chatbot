import re
from pathlib import Path

_STOPWORDS = {"pw", "policy", "wordings", "revised"}


def derive_product_name(filename: str) -> str:
    stem = Path(filename).stem
    words = [word for word in re.split(r"[-_]+", stem) if word and word.lower() not in _STOPWORDS]
    return " ".join(word.capitalize() for word in words)
