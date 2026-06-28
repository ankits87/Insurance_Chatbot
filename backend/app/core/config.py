import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BACKEND_DIR.parent / "data"
CHROMA_DB_DIR = BACKEND_DIR / "chroma_db"

COLLECTION_NAME = "product_docs"
HF_EMBED_MODEL = "nomic-ai/nomic-embed-text-v1"
HUGGINGFACE_API_KEY = os.environ.get("HUGGINGFACE_API_KEY", "")

CHUNK_MAX_TOKENS = 300
CHUNK_OVERLAP_TOKENS = 75

TOP_K = 5
HYBRID_CANDIDATE_MULTIPLIER = 4
RRF_K = 60

GROQ_MODEL = "llama-3.3-70b-versatile"
RELEVANCE_THRESHOLD = 0.5
HISTORY_DB_PATH = BACKEND_DIR / "chat_history.db"

QUERY_REWRITE_MODEL = GROQ_MODEL
QUERY_REWRITE_HISTORY_TURNS = 2

RERANK_MODEL = GROQ_MODEL
RERANK_SPREAD_THRESHOLD = 0.035

FRONTEND_ORIGIN = os.environ.get("FRONTEND_ORIGIN", "http://localhost:3000")
