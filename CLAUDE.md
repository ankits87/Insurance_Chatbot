# CLAUDE.md — Chatbot Project

## What this is

A RAG chatbot for product documentation, starting with insurance policy docs.

- **Phase 1 — text chat**: ingest product docs (.md, converted from source PDFs) → chunk → embed → store in a vector DB → answer product questions via retrieval-augmented chat.
- **Phase 2 — voice chat**: speech-to-text in, text-to-speech out, same RAG backend underneath.

## Process Rules (non-negotiable)

1. **Pros/cons before recommending.** Whenever a tool, library, model, or architecture choice is on the table, lay out the realistic options with pros and cons before giving a recommendation. Never jump straight to "use X."
2. **Log every decision to Learning.md.** Once a decision is made, append it to `Learning.md` — what was decided, options considered, why, and the date — so it can be revisited later without re-litigating.
3. **Hobby-project budget.** This is a hobby project. Default to free/open-source models and tools. Whenever a paid option comes up, name the free/open alternative and the trade-off (quality, latency, setup effort, rate limits).
4. **Design before build.** Before implementing any module, share its design/interface/approach first. Do not start coding until explicitly confirmed. This applies every single time, with no exceptions — ask before writing or editing any code, even small changes, and wait for an explicit go-ahead before starting.

## Stack

- **Backend:** Python (FastAPI) — ingestion, chunking, embeddings, vector search, chat/RAG logic
- **Frontend:** Next.js — chat UI (and later voice UI)
- **Vector DB:** Chroma (embedded)
- **Embedding model:** Ollama (`nomic-embed-text`), local
- **Chat LLM:** Groq free tier
- **Hosting:** Local for development; Render (backend) + Vercel (frontend) free tiers for production later
- Remaining pieces (voice STT/TTS for Phase 2) not yet decided — see Learning.md for decisions as they're made.

## Conventions (inherited from parent CLAUDE.md)

- TypeScript strict mode, always
- No console.logs in production code
- Handle every state: loading, empty, error, success
- Mobile-first design, 44px minimum touch targets
- Confirm destructive actions, toast feedback for async ops
