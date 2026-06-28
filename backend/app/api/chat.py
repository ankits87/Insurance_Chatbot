import httpx
from fastapi import APIRouter, HTTPException
from groq import GroqError
from pydantic import BaseModel

from app.core.history import get_history, save_turn
from app.rag.chat import answer_question

router = APIRouter()


class ChatRequest(BaseModel):
    query: str
    session_id: str


class SourceOut(BaseModel):
    source_file: str
    product_name: str
    section: str
    subsection: str
    topic: str
    score: float


class ChatResponse(BaseModel):
    answer: str
    sources: list[SourceOut]
    grounded: bool
    products: list[str]


class HistoryTurn(BaseModel):
    query: str
    answer: str
    sources: list[SourceOut]
    grounded: bool
    products: list[str]
    created_at: str


class HistoryResponse(BaseModel):
    turns: list[HistoryTurn]


@router.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest) -> ChatResponse:
    history = get_history(payload.session_id)
    try:
        result = answer_question(payload.query, history)
    except (httpx.ConnectError, httpx.HTTPError, ConnectionError) as exc:
        raise HTTPException(status_code=503, detail="Embedding service unavailable. Please try again shortly.") from exc
    except GroqError as exc:
        raise HTTPException(status_code=502, detail=f"Groq error: {exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Unexpected server error.") from exc

    sources = [
        SourceOut(
            source_file=s.source_file,
            product_name=s.product_name,
            section=s.section,
            subsection=s.subsection,
            topic=s.topic,
            score=s.score,
        )
        for s in result.sources
    ]
    save_turn(payload.session_id, payload.query, result.answer, [s.model_dump() for s in sources], result.grounded)
    return ChatResponse(answer=result.answer, sources=sources, grounded=result.grounded, products=result.products)


@router.get("/history/{session_id}", response_model=HistoryResponse)
def history(session_id: str) -> HistoryResponse:
    turns = get_history(session_id)
    return HistoryResponse(
        turns=[
            HistoryTurn(
                **turn,
                products=list(dict.fromkeys(s.get("product_name") for s in turn["sources"] if s.get("product_name"))),
            )
            for turn in turns
        ]
    )
