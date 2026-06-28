# ROADMAP.md — Build Plan

Modules build in dependency order. Each module gets a short design write-up shared for confirmation before any code is written (see CLAUDE.md process rules). Check items off as they're completed.

## Phase 1 — Text chat (RAG)

- [x] 1. **Ingestion module** — read `data/*.md`, chunk, embed via Ollama, store in Chroma. Built 2026-06-19. Run with: `cd backend && .venv/Scripts/python -m app.ingestion.pipeline`.
- [x] 2. **Retrieval module** — hybrid search (vector + BM25 + RRF), product filtering, conditional reranking. Built 2026-06-20; hybrid search + product filtering added 2026-06-23; reranker added 2026-06-25; BM25 compound-word expansion added 2026-06-28. `backend/app/rag/retrieval.py`, `index_cache.py`, `rerank.py`.
- [x] 3. **Chat/RAG module** — assemble retrieved chunks + query into a prompt, call Groq, return answer. Multi-turn query rewriting added 2026-06-23. Comparison-query bypass (cross-product search + recommendation prompt) added 2026-06-28. `backend/app/rag/chat.py`, `query_rewrite.py`.
- [x] 4. **FastAPI endpoint** — `POST /chat`, `GET /history/{session_id}`, `GET /health`, `POST /ingest/upload`. Built 2026-06-20; upload endpoint added 2026-06-23. Run with: `cd backend && .venv/Scripts/python -m uvicorn app.main:app --reload`.
- [x] 5. **Frontend chat UI** — Next.js + Tailwind v4, day-wise session sidebar, mobile-friendly layout with slide-in drawer. Built 2026-06-20; sidebar + mobile polish added 2026-06-28. Run with: `cd frontend && npm run dev`.
- [x] 6. **End-to-end manual test** — completed 2026-06-23 (6 questions across all 3 products). Re-verified 2026-06-23 after hybrid search + product filtering. Re-verified 2026-06-28 after comparison-query fix and BM25 compound expansion.
- [x] 7. **Evals** — harness (`evals/run_evals.py`) built 2026-06-24 by Claude; ground truth (`evals/test_cases.yaml`, 8 cases) seeded and cleaned up 2026-06-28. Clean run: 5/8 accuracy, 0/8 hallucinated, 1.00 retrieval recall. User review of ground truth ongoing.

## Phase 1 — Polish (post-MVP)

- [x] Upload ingestion — `POST /ingest/upload`, PDF/DOCX → clean markdown → chunks → Chroma. Built + verified 2026-06-23.
- [x] Comparison-query fix — cross-product search + per-product recommendation answer when query asks "which product should I buy". Built + verified 2026-06-28.
- [x] Sidebar + mobile layout — day-wise session history, "New chat" button, slide-in drawer on mobile, 44px touch targets. Built 2026-06-28.
- [x] BM25 compound-word expansion — "daycare" → ["daycare", "day", "care"] at scoring time; fixes class of query/document tokenization mismatches. Built + verified 2026-06-28.
- [ ] Eval ground truth — user to review/expand `evals/test_cases.yaml` beyond the 8 starter cases.

## Phase 2 — Voice

- [ ] 8. Decide STT/TTS approach (pros/cons, revisit once Phase 1 works) — log to Learning.md when decided.
- [ ] 9. Voice input component (record audio in browser).
- [ ] 10. STT integration → feeds into the existing Phase 1 chat pipeline.
- [ ] 11. TTS integration → speaks the chat response.
- [ ] 12. Voice UI polish.

## Production deployment

Ready to deploy Phase 1 (all core tasks done, polish complete). Plan: Render (backend) + Vercel (frontend) free tiers — see Learning.md "Hosting/deployment" decision.
