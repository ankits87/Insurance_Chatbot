import io

import mammoth
import pdfplumber


def extract_pdf_pages(content: bytes) -> list[str]:
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        return [page.extract_text() or "" for page in pdf.pages]


def extract_docx_markdown(content: bytes) -> str:
    result = mammoth.convert_to_markdown(io.BytesIO(content))
    return result.value
