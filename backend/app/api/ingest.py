import httpx
from fastapi import APIRouter, HTTPException, UploadFile
from pydantic import BaseModel

from app.ingestion.upload_pipeline import ingest_uploaded_file

router = APIRouter()


class IngestResponse(BaseModel):
    source_file: str
    product_name: str
    chunks_added: int


@router.post("/ingest/upload", response_model=IngestResponse)
def upload(file: UploadFile) -> IngestResponse:
    content = file.file.read()

    try:
        result = ingest_uploaded_file(file.filename, content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except (httpx.ConnectError, httpx.HTTPError, ConnectionError) as exc:
        raise HTTPException(status_code=503, detail="Embedding/vector service unavailable. Is Ollama running?") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Unexpected server error.") from exc

    return IngestResponse(source_file=result.source_file, product_name=result.product_name, chunks_added=result.chunks_added)
