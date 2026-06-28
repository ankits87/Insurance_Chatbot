# Learning.md — Decision Log

Every decision made on this project: what was chosen, alternatives considered, why, and when. Newest entries on top.

---

## 2026-06-28 — BM25 compound-word expansion fix

**Problem:** Query "whats the limit on daycare procedure in health infinity" failed to retrieve section 3.1.3 "Day Care Procedures". Root cause: the tokenizer (`_TOKEN_RE = re.compile(r"[a-z0-9]+")`) splits "Day Care" (two words in the document) into `["day", "care"]`, but the query uses "daycare" (one word) which stays as `["daycare"]`. "daycare" happened to appear in the vocabulary (from a definitions section), so the previous `expand_query_tokens` guard (`token in known → skip`) prevented expansion. Section 3.1.3 scored zero for "daycare" because it only contains "day" and "care" as separate tokens.

**Fix (`backend/app/rag/index_cache.py`):** Removed the `token in known` guard from `expand_query_tokens`. Now any token ≥ 6 chars is tried for splitting regardless of whether it's already in the vocab. For each split, if both halves are in the BM25 vocabulary, both are appended to the query token list alongside the original. "daycare" → ["daycare", "day", "care"], giving section 3.1.3 the BM25 signal it needs.

**Why the guard was wrong:** A token being in the vocabulary doesn't mean it matches the right chunks. "daycare" (one word) exists in the vocabulary but appears only in definition-context chunks, not in section 3.1.3 which uses "Day Care" (two words). The expansion is needed precisely when the vocab contains the compound form but the relevant content uses the split form.

**Handles the whole class:** "daycare"/"day care", "inpatient"/"in-patient", "preexisting"/"pre-existing" — automatic, vocabulary-driven, no word list to maintain.

**Verified:** Section 3.1.3 now retrieved (ranked 4th). Answer correctly states Day Care Procedures are covered within the Sum Insured with no separate sub-limit. Cosmetic-exclusion regression check passed.

---

## 2026-06-28 — Comparison-query bypass: product-filter leakage fix + cross-product answer mode

**Problem found:** A cross-product recommendation question asked after a product-specific question was being incorrectly scoped to the previous turn's product. Example: "tell me about pre-existing disease for global health?" (turn 1) → "if I have to take maternity benefit which product should I buy?" (turn 2) — turn 2 only retrieved Global Health chunks, not all products.

**Root cause:** The query rewriter has a system-prompt instruction to not inject product names for comparison questions, but LLMs don't follow negative instructions reliably. The rewriter was producing something like "What are the maternity benefits under Indusind Global Health?" — which then hit `_detect_product()` in `retrieval.py` and silently scoped retrieval to one product. A second compounding issue: even with correct cross-product retrieval, the chat LLM had no explicit instruction to compare products and make a recommendation.

**Alternatives considered:**
- Strengthen the rewriter negative instruction further — rejected: still LLM-dependent, unreliable for a critical routing decision.
- Add a post-rewrite override to strip the product filter when the original query signals comparison — workable but adds indirection; the simpler path is to skip rewriting entirely.
- Skip rewriting only for comparison queries (chosen) — deterministic, zero extra Groq calls, original query has no product tokens so `_detect_product()` naturally returns None → unfiltered retrieval.

**What was built (2026-06-28, `backend/app/rag/chat.py`):**
- `_is_comparison_query(query)` — keyword check on the original query against `_COMPARISON_SIGNALS` (`"which product"`, `"which plan"`, `"which policy"`, `"what product"`, `"should i buy"`, `"should i choose"`, `"should i get"`, `"should i take"`, `"best for"`, `"compare"`, `"recommend"`, `"which one"`).
- In `answer_question()`: if comparison detected, skip `rewrite_query()` entirely and pass the original query to `retrieve()` — retrieval is naturally unfiltered because the original question has no product-specific tokens.
- `COMPARISON_PROMPT_SUFFIX` appended to the user-facing LLM prompt when comparison detected: instructs the LLM to cover each product in context separately and conclude with a recommendation.
- `_build_prompt()` accepts a `comparison: bool` flag to conditionally add the suffix.

**No changes to:** `retrieval.py`, `query_rewrite.py`, or the base `SYSTEM_PROMPT` — all existing grounding/honesty/attribution logic unchanged.

**Known limitation:** `_COMPARISON_SIGNALS` is a keyword heuristic — queries like "is maternity covered?" (no explicit comparison signal) will still follow the normal rewrite path. Acceptable for now; expand the list based on real usage.

**Verification needed:** Run both queries end-to-end against the live backend to confirm turn-2 now returns chunks from all three products and produces a comparative answer.

---

## 2026-06-28 — Eval re-run after Groq rate-limit recovery; ground-truth cleanup

**What happened:** Re-ran `evals/run_evals.py` for the first time since 2026-06-25 (blocked then by hitting Groq's 100k TPD rate limit mid-session). Two runs back-to-back: first with the stale `test_cases.yaml`, then after ground-truth fixes.

**First run result (`run_20260628T065758Z.json`):** 8 cases, 3/8 accuracy correct, 0/8 hallucinated, retrieval recall 1.00. The 1.00 recall confirmed the BM25 stopword fix (2026-06-25) is still holding across all cases — including the cosmetic-exclusion cases that previously scored 0/1. The 3/8 accuracy figure was misleading: most "partial"/"incorrect" verdicts were stale ground-truth, not model failures.

**Ground-truth fixes applied to `test_cases.yaml`:**
- `cosmetic-exclusion-global-health` / `health-infinity`: broadened `expected_answer` to include the OPD expenses exclusion detail the model correctly and consistently surfaces. Removed `must_include: ["Excl 08"]` from both — the model answers in natural language and doesn't parrot clause codes; the check was always failing even on correct answers.
- `cosmetic-exclusion-health-gain`: kept `expected_answer` unchanged (the "certified by the attending Medical Practitioner" detail is real and the model sometimes omits it). Changed `must_include` from `["Excl 08"]` to `["certified"]` to track the omission deterministically.
- `preexisting-waiting-period-global-health`: broadened `expected_answer` to explicitly accept the prior-continuous-coverage reduction detail the model correctly surfaces (it was grounded, not fabricated).
- `room-rent-limit-health-gain`: rewrote `expected_answer` from "KNOWN LIMITATION — figure doesn't surface" to the actual correct answer (Plus Plan: Single Private A.C. room; Power/Prime: actuals). Added `must_include: ["Single Private A.C"]`. This case is no longer a known gap — it was fixed by the BM25 stopword fix on 2026-06-25, which this re-run confirmed.

**Second run result (`run_20260628T072019Z.json`):** 8 cases, 5/8 accuracy correct, 0/8 hallucinated, retrieval recall 1.00. The 3 remaining "partial" verdicts are real model gaps, not ground-truth issues:
1. `cosmetic-exclusion-health-infinity` — model consistently drops the OPD exclusion clause for the Infinity product specifically, even when the right chunk is retrieved.
2. `preexisting-waiting-period-global-health` — model dropped the prior-coverage detail this run but included it in the previous run; LLM non-determinism, not a hard retrieval gap.
3. `room-rent-limit-health-gain` — model mentioned only one plan tier this run vs. all tiers in the previous run; also LLM non-determinism.

**Why:** The eval suite is now in a clean, honest state. Retrieval is solid (1.00 recall). The remaining "partial" verdicts reflect real generation-completeness variance worth tracking across future runs.

---

## 2026-06-24 — Eval harness built, first run surfaces a real new recall gap

**Decision:** Built `evals/run_evals.py` + `evals/test_cases.yaml` per the design agreed the same day (hand-rolled Python, no Ragas/DeepEval — see ownership-split entry below). Scores 4 dimensions per test case: retrieval recall (expected vs. actual `(product_name, section, subsection)` tuples, normalized comparison to tolerate punctuation differences like a trailing colon), answer accuracy (LLM-judge verdict: correct/partial/incorrect, plus a deterministic `must_include` substring check), citation quality (same chunk-match comparison applied to what's actually cited), and hallucination rate (separate LLM-judge call comparing the answer against the *actual retrieved context*, independent of whether that context was the right context). Judge calls reuse the existing Groq client/model (`GROQ_MODEL`) — accepting the known self-evaluation-bias caveat rather than paying for a separate "stronger judge" model. Seeded 8 starter test cases drawing on questions/answers already manually verified earlier in the project, each marked for the user's review/sign-off per the ownership split.

**Real bug found and fixed before trusting any results:** the first run flagged 4/8 cases as "hallucinated," but spot-checking showed at least 3 were judge-prompt false positives, not real fabrications — confirmed by checking the actual retrieved chunk text directly:
- Two refusal cases ("I couldn't find this in the docs") got their own honest refusal text flagged as an "unsupported claim" — the judge was treating any answer not copy-pasted from context as suspect, including honest hedging.
- The pre-existing-disease waiting period case flagged "12 months" as unsupported — but it's verbatim in the retrieved chunk text ("change the 36 months Waiting Period... to 24 months or 12 months"). Confirmed via direct lookup before concluding it was a judge error, not a model error.
Fixed by rewriting `HALLUCINATION_JUDGE_PROMPT` with explicit rules: refusals/hedging are never hallucinations by themselves; only flag claims asserting a specific fact (number/clause code/coverage detail) that contradicts or has no basis in the context; quote the specific fact, not the whole sentence or the question. Re-ran after the fix: hallucination rate dropped from 4/8 to 0/8, confirming these were prompt artifacts, not real findings.

**Real, reproducible finding the harness caught (not a harness bug):** "What is excluded under cosmetic treatment in the Global Health policy?" — with product-filtering correctly scoping retrieval to Global Health only, the actual top-5 chunks for this exact phrasing don't include the "4.1.7 Cosmetic or Plastic Surgery" exclusion clause at all; an OPD/out-patient-treatment chunk that happens to also mention "Cosmetic" wins the ranking instead. Confirmed reproducible via a direct, repeated call (not flaky/random). Distinct from the original task #12 cosmetic-treatment gap (that one was about boilerplate-similarity across documents in an *unfiltered* search; this one is specific to the *filtered*, single-product search — narrowing the candidate pool changed which chunk wins the ranking competition). Same underlying pattern affected the Infinity cosmetic-exclusion case too (0/1 retrieval recall). **Not fixed in this session** — logged as a new, real recall gap for the next retrieval-quality pass, found by the eval harness on its very first run.

**First clean run result (2026-06-24, `evals/results/run_20260624T170119Z.json`):** 8 cases, 6/8 answer-accuracy correct, 0/8 hallucinated, retrieval recall 0.67 average (dragged down specifically by the two cosmetic-exclusion-under-product-filter cases above). Room-rent-limit case (the known task-#12-era limitation) now scores "correct" — the model's honest "not specified, see Coverage Summary" answer matches the expected framing for that known gap.

**Why:** Validates the eval harness is finding real signal (a genuine new recall gap), not just noise — but only after the judge prompt itself was debugged, which is itself the kind of "test the full input space, don't trust the first result" lesson from the 2026-06-23 practice-change entry above, applied to the eval tooling itself.

---

## 2026-06-24 — Evals ownership revised: Claude builds the harness, user provides ground truth

**Decision:** Revises the 2026-06-18 "Evals placement" decision, which reserved `evals/` for the user to build entirely themselves. Split now: Claude builds the automated eval harness (test runner, scoring logic for all 4 quality dimensions, reporting), the user provides/reviews the ground-truth expected answers and expected chunks per question.

**Alternatives considered (asked directly):**
- Claude builds everything, including drafting the golden dataset by reading the policy PDFs — faster to get a running eval suite, but Claude's own reading of dense insurance clauses is exactly the kind of judgment call the original decision wanted to keep in the user's hands; would need heavy review regardless.
- Claude only designs (no code), user builds it all — keeps the original decision fully intact, but the user explicitly asked Claude to start building this time.

**Why:** Now that the pipeline is mature (Phase 1 complete, hybrid search + product filtering + multi-turn follow-ups all built), the eval *engineering* (harness, scoring logic, the four metrics' implementation) is substantial enough to be worth Claude's help, while *correctness judgment* about what a right answer/right chunk looks like for these specific policies stays the user's call — preserves the spirit of the original decision (domain judgment stays with the user) while removing the engineering bottleneck.

---

## 2026-06-23 — Practice change: verify generalizing logic across its full input space

**Decision:** When a feature is meant to generalize across multiple similar inputs (one detector across N products, one model choice for a class of queries, etc.), verify it against all of them before calling it done — not just the first/easiest case.

**Why:** Two real bugs this session shared the same root cause — testing only the first case that happened to work.
- Product-aware filtering was verified only against Health Gain when first built. It silently failed for the other two products: Health Gain's verbose original derived name ("Revised Indusind Health Gain Policy Wordings") made the generic word "policy" a false "distinguishing token," so any query saying "...policy?" matched two products and fell back to unfiltered search — invisible until Global Health/Infinity were actually tried (see the 2026-06-23 hybrid-search and re-upload entries below).
- The query-rewrite model (`llama-3.1-8b-instant`) was picked because rewriting "seemed like a simple task," without testing the actual substitution-style follow-up case it needed to handle. It garbled two products together, which then masqueraded as a regression in the product-filtering feature built earlier the same day (see the multi-turn follow-up entry below).

**How to apply going forward:** Test a generalizing feature against every distinct case in its input space (every product, every document type, every follow-up phrasing pattern) before marking it verified — not just N=1. When choosing a model/tool because a task "seems simple," validate with a real side-by-side test on the actual target case rather than reasoning from apparent simplicity alone.

---

## 2026-06-23 — Query-rewrite model: tried two models, the smaller one failed

**Decision:** `QUERY_REWRITE_MODEL` ended up set to `llama-3.3-70b-versatile` (same model used for answering), not the originally-planned `llama-3.1-8b-instant`.

**Models tried:**
- `llama-3.1-8b-instant` (tried first) — chosen on the assumption that rewriting a follow-up into a standalone question was a "simple" task not requiring the bigger model, plus it's faster/lighter on Groq's free tier. **Failed in testing**: given the follow-up "What about for Health Gain?" after a Global Health question, it produced garbled rewrites that merged both products into one nonsensical query instead of substituting one for the other — e.g. "What treatments for the enhancement of appearance are excluded under the Global Health policy's definition of Health Gain?" Tried twice with slightly different garbled phrasing both times, not a one-off fluke.
- `llama-3.3-70b-versatile` (switched to) — given the exact same prompt/history side-by-side, correctly produced "What is excluded under cosmetic treatment in the Health Gain policy?" on the first try.

**Why the smaller model failed:** Resolving a *substitution*-style reference ("what about X" replacing the prior subject, not appending to it) needs more reasoning than the 8b model reliably provides — the task only looked simple in the abstract; it wasn't simple for the model actually doing it.

**Why this mattered beyond just rewrite quality:** The bad rewrite didn't just give a worse answer — it silently broke a different, already-working feature. The garbled query contained tokens for both products, so the product-detection logic (built earlier the same day) saw two matches, treated it as ambiguous, and fell back to searching all three products unfiltered. A failure in one feature masqueraded as a regression in an unrelated one, which made it briefly confusing to diagnose until the rewrite output itself was inspected directly.

**Why:** Correctness of the rewrite matters more than the latency/cost savings of the smaller model, since the rewrite is a hard dependency for everything downstream of it (retrieval, product filtering, the final answer) — a cheap-but-wrong rewrite is worse than no rewrite at all.

---

## 2026-06-18 — Runtime/language for the app

**Decision:** Python backend (FastAPI) for ingestion/RAG/chat + Next.js frontend for UI.

**Alternatives considered:**
- Full TypeScript/Next.js — simplest single-codebase deploy, but free/open embedding models and local LLMs are much harder to run from Node; would likely force a paid embedding API.
- Python-only (Streamlit/Gradio) — fastest to build, all free RAG tooling native, but little control over UI/UX — conflicts with mobile-first/44px-touch-target conventions.

**Why:** Best access to free/open-source RAG tooling (sentence-transformers, FAISS/Chroma, Ollama) while still allowing a polished, mobile-first custom UI. Accepted cost: two services to run/deploy instead of one.

---

## 2026-06-18 — Vector DB

**Decision:** Chroma (embedded, in-process).

**Alternatives considered:**
- Qdrant — stronger filtering/scaling, but needs a running service (Docker/cloud); overkill for current dataset size.
- FAISS — fastest raw library, but no built-in metadata/text storage; would need a hand-rolled side store.
- Supabase pgvector — hosted free tier with relational DB included, but free-tier limits and couples hosting to Supabase.

**Why:** Dataset is currently 3-4 product docs (a few thousand chunks) — an embedded store needs zero infra and costs nothing. Migrating to Qdrant later is a straightforward swap if the catalog grows.

---

## 2026-06-18 — Embedding model

**Decision:** Ollama (`nomic-embed-text`).

**Alternatives considered:**
- Local sentence-transformers — also free/local, simpler (pip install, no background service), but doesn't double as a tool for future local LLM experimentation.
- Voyage AI — high quality, generous free tier, but sends document content to a third party.
- OpenAI text-embedding-3-small — very high quality, but not free and sends data externally.

**Why:** Free, fully local (insurance doc content never leaves the machine), and sets up Ollama as the local-model runtime we can reuse if we want a local LLM later. Accepted cost: Ollama needs to run as a background service.

---

## 2026-06-18 — Chat LLM

**Decision:** Groq free tier.

**Alternatives considered:**
- Ollama local — fully local/private and consistent with the embedding choice, but quality on modest hardware would likely be noticeably weaker for precise clause/numeric answers from policy docs.
- Google Gemini free tier — also free with generous limits, but Groq's inference speed and access to larger open models (e.g. Llama 3.1 70B) won out.
- Claude API — best quality, but not free; ruled out to keep the chat path at $0.

**Why:** Free tier with no local hardware constraint, runs larger/better open models than what's practical to self-host, and fast inference for a responsive chat experience. Accepted cost: queries leave the machine, and free-tier rate limits could be hit under heavy testing.

---

## 2026-06-18 — Hosting/deployment

**Decision:** Local only during development. Move to Render (backend) + Vercel (frontend) free tiers for production once the app is working end-to-end.

**Alternatives considered:**
- Fly.io free allowance — persistent volumes solve Chroma's disk-persistence problem cleanly, but more devops upfront (Dockerfile, fly.toml) than needed during active development.
- Railway free tier — "free" tier is trial credit, not indefinitely free; ruled out.

**Why:** No need to solve deployment before the RAG pipeline works. Render's free-tier ephemeral disk (risk to Chroma's persisted index) is a known tradeoff to handle when we get to production — likely via re-ingestion on deploy or switching the vector store/volume strategy at that point.

---

## 2026-06-18 — Repo layout

**Decision:** Monorepo — one repo with `backend/` (FastAPI) and `frontend/` (Next.js) as top-level folders.

**Alternatives considered:**
- Separate repos for backend and frontend — cleaner separation, but pure overhead for a solo hobby project and would split the decision log/CLAUDE.md across two places.

**Why:** No team-boundary reason to split; Render and Vercel both support deploying a subdirectory of a monorepo, so the hosting plan is unaffected.

---

## 2026-06-18 — Source docs folder and format

**Decision:** Renamed `Documents/` → `data/`. Ingestion only reads `.md` files; the 3 existing PDFs will be converted/replaced with `.md` manually rather than building a PDF→markdown conversion step.

**Alternatives considered:**
- Keep folder named `Documents/` — no real benefit, `data/` matches the rest of the structure.
- Build a PDF→markdown conversion step into ingestion — would let PDFs be dropped in directly, but adds a conversion module (and its own quality issues — tables/formatting often break) for a one-time/manual task.

**Why:** Manual conversion is a one-time cost for 3 docs; not worth building and maintaining a conversion module for it.

---

## 2026-06-18 — Evals placement

**Decision:** Reserve a top-level `evals/` folder. No content built yet — user will write evaluation test cases/scripts themselves once Phase 1's pipeline is working.

**Why:** Evals need real chunks/retrieval/answers to test against, so they come after the core pipeline works, not before.

---

## 2026-06-19 — Ingestion module design

**Decision:**
- Strip repeated boilerplate/footer noise (recurring contact/registration text, strikethrough conversion artifacts) before chunking.
- Structure-aware chunking: split by `##` headers first (Section/Subsection kept as metadata), then sub-split oversized sections (e.g. long numbered definition lists) by list-item boundaries, with a size cap as fallback only when no natural boundary exists.
- Fallback chunk size: ~200-300 tokens, with 75-token overlap between chunks for context continuity.
- Metadata per chunk: `source_file`, `section`, `subsection`, `chunk_index`.
- Deterministic chunk IDs (hash of `source_file`+`section`+`chunk_index`) so re-running ingestion upserts instead of duplicating.
- Script wipes and rebuilds the whole Chroma collection on each run (simplest at this dataset size).
- Empty/missing `.md` files (e.g. `HealthGain.md` currently) are skipped with a warning, not an error.

**Alternatives considered:**
- Chunk raw text without cleanup — rejected, noise repeats often enough to pollute embeddings/retrieval.
- Fixed-size recursive splitter ignoring document structure — rejected, would likely split numbered definitions/clauses apart given the doc's actual structure (one subsection is a single 50+ item numbered list).
- Larger fallback chunks (~500-800 tokens) — rejected in favor of smaller chunks since structure-aware splitting already preserves most real semantic units; the fallback should optimize for retrieval precision when it does trigger.

**Why:** Matches the actual structure observed in `data/indusind-global-health.md` (headers + long definition lists + repeated conversion noise) rather than a generic default; keeps each definition/clause as an intact, precisely retrievable unit.

---

## 2026-06-19 — Metadata: embedded vs. stored separately

**Decision:** Metadata (`source_file`, `section`, `subsection`, `chunk_index`) is stored separately as Chroma metadata fields, NOT prepended into the text that gets embedded. Embeddings are computed on the clean chunk text only.

**Alternatives considered:**
- Prepend metadata into the embedded text (e.g. `"[Section 2.1 Standard Definitions] <chunk text>"`) — would help disambiguate short/context-dependent chunks, but risks clustering many same-section chunks together in vector space by shared prefix rather than actual content, hurting retrieval precision.

**Why:** Our chunks are mostly self-contained definitions/clauses (structure-aware chunking), so the precision cost of polluting embeddings with repeated section-name prefixes outweighs the disambiguation benefit. Metadata remains available to the RAG module for prompt assembly/citation even though it didn't influence retrieval matching.

---

## 2026-06-19 — Ingestion: third heading tier + noise-marker fix (found while testing against real docs)

**Decision:** Added a third metadata tier — `section` → `subsection` → `topic` — since the real documents nest a level deeper than assumed (e.g. illness/procedure items like "Knee:", "PULMONARY ARTERY GRAFT SURGERY" under `2.3 SPECIFIED ILLNESSES`). Also broadened the noise-cleanup markers to catch standalone "(WhatsApp)" footer lines that were incorrectly being parsed as real `##` section headers.

**Alternatives considered:**
- Flatten all `##` headers to one undifferentiated label — simpler, but throws away real structure the document has.

**Why:** Discovered by running the chunker against the actual `data/indusind-global-health.md` — found chunks mislabeled with a phone-number/WhatsApp footer as their "section" (noise-header bug), and found real third-level headers (illness/procedure names) being flattened to top-level sections, losing their parent subsection context.

**Known accepted limitation:** A few spots nest even deeper (e.g. "Knee:"/"Hip:"/"Shoulder:" under "JOINT REPLACEMENT / RECONSTRUCTION") — the `topic` field captures only the immediate one, so "Knee:" loses the "JOINT REPLACEMENT" grouping. Not fixed — diminishing returns for a hobby project; the chunk text itself is still self-explanatory.

---

## 2026-06-20 — Retrieval module design

**Decision:**
- Add Nomic's recommended task prefixes before embedding: `"search_document: "` for chunks (ingestion), `"search_query: "` for incoming queries (retrieval). Requires re-running ingestion once to re-embed the existing 599 chunks with the new prefix.
- Top-k = 5 chunks returned per query.
- Chroma collection similarity metric set explicitly to cosine (was implicitly using the default squared-L2).
- Retrieval module lives in `backend/app/rag/retrieval.py`, signature `retrieve(query: str, top_k: int = TOP_K) -> list[RetrievedChunk]`, where `RetrievedChunk` carries chunk text + metadata + similarity score.

**Alternatives considered:**
- No embedding prefixes (current ingestion behavior) — zero rework, but mismatched with how `nomic-embed-text` was fine-tuned for asymmetric query/document retrieval.
- Top-k 3 — cheaper but risks missing a relevant chunk split across a boundary; top-k 8-10 — higher recall but bigger prompt for Groq's free-tier limits and more irrelevant-chunk noise.
- Keep default L2 metric — no change needed, but `nomic-embed-text` vectors aren't guaranteed unit-length, so ranking isn't guaranteed equivalent to cosine.

**Why:** Prefixes and cosine metric are both "use the model the way it was tuned to be used" choices with no real downside given we already do a full collection rebuild on every ingestion run. Top-k 5 balances answer context against prompt size/rate limits on Groq's free tier.

---

## 2026-06-20 — Chat/RAG module design

**Decision:**
- Groq model: `llama-3.3-70b-versatile`.
- Conversation reasoning is stateless per-question (no follow-up resolution) — `answer_question(query)` always retrieves fresh, independent of prior turns.
- Chat history (question, answer, sources, timestamp) is persisted server-side in SQLite (`backend/chat_history.db`), keyed by `session_id`, so customers can view past Q&A. This is a separate concern from reasoning — saving happens around the stateless `answer_question` call, wired in at the API layer (task #10).
- Grounding: threshold-based refusal — if the top retrieved chunk's cosine score is below `RELEVANCE_THRESHOLD` (starting at 0.5, tunable), skip the Groq call and return a fixed "not found in these documents" answer instead of risking a hallucinated response.
- Citations included: the response carries `sources` (section/subsection/topic/score per chunk used) alongside the answer text.

**Alternatives considered:**
- `llama-3.1-8b-instant` — faster, higher free-tier limits, but riskier on dense conditional insurance language.
- Multi-turn reasoning (LLM sees prior turns) — rejected for v1: real scope creep, opens an unresolved question of how retrieval should handle a follow-up query (re-embed combined turns vs. last N). Deferred to a later iteration.
- Client-side-only history (browser storage) — rejected since the user wants history to persist and be viewable reliably, not lost on a cleared browser/different device.
- Always answering from top-k regardless of relevance — rejected, risks confident hallucinated answers on off-topic questions.

**Why:** Keeps the core chat/RAG logic simple and stateless (one question in, one grounded answer out) while still meeting the requirement that customers can view their conversation history, by treating storage as a separate, bolted-on concern rather than threading session state through retrieval/reasoning.

---

## 2026-06-20 — FastAPI endpoint design

**Decision:**
- Session IDs are client-generated (frontend mints a UUID on first load, stores in localStorage, sends with every request) — no server-side session middleware.
- Error responses are granular: 503 for embedding/Chroma failures ("check Ollama is running"), 502 for Groq failures ("AI service busy"), 500 for generic/unexpected errors.
- CORS is restricted to the frontend's actual origin (`http://localhost:3000` for dev, configurable via env var for the Vercel URL once deployed) — not wide open.
- Routes: `POST /chat` (query + session_id in, answer + sources + grounded out, plus saves the turn to history), `GET /history/{session_id}` (returns saved turns), `GET /health` (liveness check for Render). Routes are plain `def`, not `async def`, since the underlying Ollama/Chroma/Groq calls are blocking I/O — FastAPI runs sync routes in a threadpool automatically.

**Alternatives considered:**
- Server-generated session IDs — more moving parts for no benefit given there's no auth/security boundary in this app.
- Generic catch-all error handling — less code, but vague messages for every failure mode, when we've already hit a real Ollama-not-running failure once in this project.
- Open CORS (`*`) — zero config, but lets any site call the Groq-backed endpoint if they find the URL.

**Why:** Matches the rest of the project's "simple but not careless" bar — no unnecessary session infrastructure, but error handling and CORS reflect real failure modes/security practice already relevant to this app.

---

## 2026-06-22/23 — Upload-ingestion module (replaces manual PDF→markdown conversion)

**Decision:** Built a `POST /ingest/upload` endpoint so PDF/DOCX policy docs can be uploaded directly instead of manually converting them to `.md` with an external tool first. Backend-only (no frontend UI) — this is an internal/admin tool for adding docs, not customer-facing.
- PDF text extraction: `pdfplumber` (MIT license). DOCX→markdown: `python-mammoth` (official Python port of `mammoth`, same heading-style mapping). Both run in the existing Python backend, reusing `cleaning.py`/`chunking.py` in-process.
- Header/footer noise: frequency-based detection (lines repeated verbatim across ≥30% of PDF pages get auto-stripped, `backend/app/ingestion/cleaning.py::strip_repeated_lines`), replacing the old hardcoded keyword blocklist as the primary defense (blocklist kept as a backstop). DOCX needs little stripping since `mammoth` already excludes Word header/footer parts.
- Heading reconstruction (PDF only): flat-text extraction has no real headers, so `chunking.py::reconstruct_headings` detects `SECTION X` / `X.Y.Z` numbered patterns (same regexes as the existing chunker) and prefixes them with `##` so the structure-aware chunker works unchanged. Known limitation: only reconstructs Section/Subsection tiers, not the free-text "topic" tier (no font-size signal from flat text).
- Product metadata: `product_name` auto-derived from filename (strip extension, swap `-`/`_` for spaces, title-case).
- Storage: incremental replace, not full rebuild — on upload, deletes existing Chroma chunks matching that `source_file`, then adds the freshly chunked/embedded ones (`vectorstore.py::replace_source_file`). Makes re-uploading a corrected file safe/idempotent. The existing CLI full-rebuild path (`pipeline.py`) is unchanged, kept for bulk/recovery use.
- Markdown snapshot saved to `data/<derived_name>.md` for inspection, same transparency as the old manual workflow.

**Alternatives considered:** PyMuPDF for PDF extraction — faster/more accurate, but AGPL/commercial-license, ruled out for this project's licensing comfort vs. `pdfplumber`'s MIT license. Node (`pdf-parse`/`mammoth` npm) — was the user's first instinct, but Node-only packages would've meant a second runtime; the Python ports keep everything in one backend.

**Why:** The original manual-conversion docs (`data/*.md`) had accumulated repeated header/footer noise and one doc (`HealthGain`) was never converted at all. Direct upload removes the manual external-tool step going forward and is more robust to new documents/insurers than a hardcoded noise blocklist.

**Verified 2026-06-23:** Uploaded `revised-indusind-health-gain-policy-wordings.pdf` (previously un-ingested) end-to-end — 312 chunks added, correct `product_name`/`section`/`subsection`/`topic` metadata, section headers (`SECTION-1 PREAMBLE`, `2.1 STANDARD DEFINITIONS`, etc.) correctly reconstructed, zero noise-marker leakage in the snapshot. Collection count went 599→911. Re-uploaded the same file to confirm idempotency — count stayed at 911 (replaced, not duplicated).

---

## 2026-06-23 — Hybrid search (vector + keyword) + product-aware filtering + citation transparency

**Decision:** Three related changes to retrieval, prompted by two real findings: (1) the still-open cosmetic-treatment recall gap from task #12's e2e test (a real exclusion clause ranked 10th on pure vector similarity, outside top_k=5), and (2) the user noticing that `product_name` was stored in metadata but never actually used — so a query naming one product could silently pull in chunks from a different, similarly-worded product.

- **Hybrid retrieval**: added `rank_bm25` (pure Python, MIT license) as an in-memory keyword-search index alongside the existing Chroma vector search. Both retrieve more candidates than needed (`top_k * 4`), then are fused via Reciprocal Rank Fusion (RRF, k=60) — chosen over a weighted-score blend because cosine similarity and BM25 scores live on incomparable scales; RRF only needs each list's *rank*, not its raw score.
- **Grounding-threshold gate left untouched in semantics**: the existing `RELEVANCE_THRESHOLD` refusal check now reads a new `RetrievalResult.top_vector_score` field — the raw cosine score of the single best vector match — computed independently of the final RRF-fused chunk ordering, so hybrid ranking only changes *which chunks answer an in-domain question*, not the *is this even about our docs* gate.
- **Product-aware filtering**: added dynamic "distinguishing token" detection — at index-build time, compute each product's name-words that aren't shared with any other product's name (e.g. "Gain", "Infinity", "Global" vs. shared words like "Indusind"/"Health"). If a query contains a token unique to exactly one product, both the vector and BM25 searches are scoped to that product (`where={"product_name": ...}`); otherwise search runs unfiltered across all products, same as before. Zero LLM cost, zero manual alias-list maintenance — automatically derives from whatever's currently ingested.
- **Citation transparency**: `product_name` now flows through `RetrievedChunk` → API `SourceOut` → frontend `Source` type → `SourceCitations.tsx`, so even an unfiltered/ambiguous multi-product answer shows which product each cited chunk came from.
- **New cache module** (`backend/app/rag/index_cache.py`): lazily builds the BM25 index + product-token map from Chroma's current contents on first use; invalidated and rebuilt whenever ingestion writes (both the CLI full-rebuild path and the upload-endpoint incremental-replace path call `invalidate()`).

**Alternatives considered (product detection):** LLM-based detection (ask Groq which product a query mentions) — more robust to paraphrasing, but an extra round-trip on every query for what's usually exact name-matching; rejected for cost/latency. Manual alias list — more precise, but reintroduces the per-document manual maintenance the upload module was built to eliminate; rejected.

**Alternatives considered (hybrid backend):** Switching the vector DB to one with native hybrid support (Qdrant/Weaviate) — would need a running service, re-litigating the embedded-Chroma decision for zero real benefit at this dataset size; rejected. SQLite FTS5 for the keyword side — reuses the existing SQLite dependency, but is yet another index to keep in sync for no real ranking benefit over `rank_bm25` at ~1000 chunks; rejected.

**Data-consistency fix found mid-build:** the original two manually-ingested docs (`indusind-global-health.md`, `indusind-health-infinity.md`, 599 chunks) had no `product_name` metadata at all — only chunks ingested through the newer upload endpoint had it. Backfilled via a one-off `collection.update()` (metadata-only, no re-embedding). Also discovered the original `.md` source files for those two docs no longer exist in `data/` (only the original PDFs remain) — meaning the documented full-rebuild CLI command (`python -m app.ingestion.pipeline`) is currently **destructive**: it would silently wipe those 599 chunks since it only re-adds whatever `.md` files it finds. Not fixed in this session (no rebuild was run) — flagged as a known risk. The safe fix, if/when needed, is re-uploading the original PDFs through `/ingest/upload` instead of relying on the CLI rebuild path.

**Why:** Hybrid search directly fixes a real, demonstrated recall failure (exact-term exclusion clauses losing to vector similarity ranking) without touching the existing grounding-safety behavior. Product filtering closes a real cross-document leakage risk the user identified by inspection, at zero ongoing cost given the dynamic token approach.

**Verified 2026-06-23:** Re-ran the exact task #12 cosmetic-treatment query — now correctly surfaces "4.1.7. Cosmetic or Plastic Surgery (Code: Excl 08)" from `indusind-global-health.md` (previously missed). Verified product-aware filtering: a query naming "Health Gain" returned all 5 sources exclusively from that product's own distinct clause (numbered 4.1.8 there, vs. 4.1.7 in Global Health — confirms it's pulling the right document, not reusing another's match). Verified an ambiguous query (no product named) still searches all products and shows per-citation `product_name`. Verified the existing grounding defense (threshold fast-path + LLM honesty backstop) still correctly refuses off-topic and gibberish queries under the new scoring. Frontend lint/type-check pass; visual confirmation in-browser still pending (no browser-automation tool available in this environment, same limitation as prior frontend work).

---

## 2026-06-23 — Re-ingested global-health/health-infinity via upload endpoint + product-name stoplist fix

**Decision:** Re-uploaded `indusind-global-health-pw.pdf` and `indusind-health-infinity-pw.pdf` through `/ingest/upload` (the new generic upload pipeline) instead of relying on their old manually-converted `.md` files, which no longer exist on disk. This closes out the destructive-CLI-rebuild risk noted in the hybrid-search entry above and gives all 3 products the same noise-cleaning quality.

Two follow-on fixes made during this:
- **`-pw` filename suffix**: `derive_product_name()` was turning `indusind-global-health-pw.pdf` into "Indusind Global Health **Pw**" — the suffix (short for "policy wordings") leaked into the product name as a literal word. Fixed in `backend/app/ingestion/naming.py` by adding a stopword filter (`{"pw", "policy", "wordings", "revised"}`) applied to every filename-derived word, not just a trailing-suffix regex — simpler and catches the word regardless of position.
- **Distinguishing-token collision (real bug, not just cosmetic)**: the HealthGain product's *original* derived name, "Revised Indusind Health Gain Policy Wordings," made "policy" a token unique to that one product (since the other two products' short names don't contain it) — so any natural question mentioning "...policy?" (e.g. "the Global Health **policy**") matched *two* products and the detector fell back to unfiltered search, silently defeating the just-built product filtering for 2 of 3 products. The same stopword fix above resolves this too, since "policy"/"wordings"/"revised" no longer become part of any product's name or its distinguishing tokens. Product names are now clean and short: "Indusind Global Health", "Indusind Health Infinity", "Indusind Health Gain".

**Why caught:** Verifying product-aware filtering for all 3 products (only Health Gain had been tested when the feature was first built) immediately surfaced the collision — a reminder to test every branch of automatically-derived logic, not just the first one that happened to work.

**Mechanics:** Old orphaned chunks for `indusind-global-health.md`/`indusind-health-infinity.md` (599 total) deleted from Chroma via `collection.delete(where=...)`. `product_name` backfilled in place via `collection.update()` for the re-uploaded/renamed chunks (no re-embedding needed, metadata-only). Backend restarted after each data change so the in-memory BM25/product-token cache (`index_cache.py`) rebuilds fresh — `invalidate()` only affects the process that calls it, so one-off backfill scripts run in a separate process don't reach the live server's cache.

**Verified 2026-06-23:** Collection now holds 811 chunks (312 Health Gain + 230 Health Infinity + 269 Global Health), zero orphaned source files, all three with clean `product_name`. Re-tested product-filtered queries for all three products (previously only Health Gain had been tested) — each now correctly scopes to exactly one product's sources.

---

## 2026-06-23 — Task #12 closed: full e2e re-run after hybrid search + product filtering

**Decision:** Re-ran a 6-question e2e test of the full stack to close out task #12, which had been left open since 2026-06-21 pending the cosmetic-treatment recall-gap decision. Note: the original 6 questions from the 2026-06-21 run were never recorded verbatim (only a summary was logged) — this run uses a new, more thorough 6-question set deliberately covering all 3 products individually (the 2026-06-21 run effectively only had 1 clean product's data), plus the regression-tested cosmetic question and both refusal modes.

**Results:**
1. Cosmetic-treatment exclusion (no product named) — correct clause cited (4.1.8 Cosmetic/Plastic Surgery), grounded. Confirms the hybrid-search recall fix holds.
2. Global Health pre-existing-disease waiting period — correct, all 5 sources scoped to Global Health only.
3. Infinity OPD coverage — correct Plan A/B breakdown, all sources scoped to Infinity only.
4. Health Gain room rent limit — **partial**: didn't fabricate a number, honestly stated the exact limit isn't in the retrieved context and pointed to "Coverage Summary"/"Policy Schedule" instead. All sources correctly scoped to Health Gain. Likely cause: the actual limit value lives in a table elsewhere in the document that the current chunking doesn't surface for this query — a new, distinct recall gap from the cosmetic-treatment one, not a hallucination. **Not fixed, logged as a known limitation** — tables/structured data within policy PDFs may need different handling than prose clauses if this becomes a recurring pattern.
5. Off-topic (pasta) — correctly refused via the LLM honesty backstop.
6. Gibberish — correctly identified as nonsense and refused.

History persistence verified: all 6 turns retrievable via `GET /history/{session_id}` in order with correct timestamps. CORS verified: `Access-Control-Allow-Origin` correctly echoes `http://localhost:3000` only.

**Why considered closed:** 5/6 fully correct, 1/6 honestly partial (no hallucination) — consistent with (better than) the original 4/6 + 2 refusals bar, and the specific gap that originally kept #12 open is now fixed and reverified. The Q4 room-rent finding is a new, separate, minor limitation rather than a blocker.

---

## 2026-06-23 — Multi-turn follow-up support via LLM query rewriting

**Decision:** Added conversational continuity for follow-up questions (e.g. "What about for Health Gain?" after a question about Global Health), which the system previously couldn't handle at all — `answer_question` always reasoned and retrieved fresh per-query with zero awareness of prior turns, a deliberate v1 scope decision (logged 2026-06-20).

- **New module** `backend/app/rag/query_rewrite.py`: `rewrite_query(query, history)` takes the last `QUERY_REWRITE_HISTORY_TURNS=2` turns and asks Groq to rewrite the follow-up into a fully standalone question, resolving references (product names, pronouns) using the history. Returns the query **unchanged** if `history` is empty — skips the Groq call entirely for the common first-turn-in-session case, so single-shot queries pay zero added latency/cost.
- **Fails open**: wrapped in the same exception types already used elsewhere in this app for known external failure modes (`httpx.ConnectError`, `httpx.HTTPError`, `ConnectionError`, `GroqError`) — falls back to the raw query unchanged rather than breaking the request.
- **Wiring**: `answer_question(query, history=None)` now calls `rewrite_query` when history is present and uses the *rewritten* query for both retrieval and the Groq answering prompt. `api/chat.py`'s `/chat` route fetches `get_history(session_id)` before calling `answer_question` (reusing the function already used by `/history`) and passes it through. Critically, **the original raw user query (not the rewritten one) is still what gets saved to `chat_history.db`** — the rewrite is purely an internal retrieval/reasoning aid, invisible to the user.

**Alternatives considered (laid out before building):** (A, chosen) LLM query rewriting before retrieval — fixes retrieval and product-detection follow-ups together, costs one extra Groq call per follow-up only. (B) "Sticky product" memory — remember the last detected product per session, fall back to it when a query doesn't itself match one; nearly free but only fixes product-omission follow-ups, not richer conversational references. (C) Do nothing, document as a known limitation. Chose A for broader coverage despite the added per-follow-up cost.

**Model choice — corrected mid-build after testing:** Originally planned `llama-3.1-8b-instant` for the rewrite call (cheaper/faster, seemed like a "simple" task). **Testing immediately surfaced a real bug**: for a substitution-style follow-up ("what about for Health Gain?" after asking about Global Health), the 8b model garbled the two products together — e.g. "...the Global Health policy's **definition of Health Gain**?" — instead of replacing the subject. Side-by-side test with the same prompt on `llama-3.3-70b-versatile` got it exactly right on the first try: "What is excluded under cosmetic treatment in the Health Gain policy?" Switched `QUERY_REWRITE_MODEL` to alias `GROQ_MODEL` (same 70b model used for answering) — correctness matters more than the latency/cost savings here, and a wrong rewrite doesn't just give a worse answer, it actively defeats the product-filtering work already built (a garbled query naming both products makes the distinguishing-token detector see 2 matches and fall back to unfiltered search across all 3 products).

**Why:** A documentation chatbot for insurance policies is exactly the kind of tool where users naturally ask a sequence of related questions about one plan ("what about X", "and Y?") — leaving this unhandled was a real, likely-to-recur UX gap, not a hypothetical one.

**Verified 2026-06-23:** Re-ran the originally-broken scenario after the model fix — follow-up "What about for Health Gain?" after a Global Health cosmetic-exclusion question now correctly rewrites to a standalone Health Gain question, retrieves the right product's correct exclusion clause (4.1.8), and all 5 sources are scoped to that one product (the rewrite fix also restored the product-filtering benefit it had been breaking). Confirmed first-turn queries (no history) skip the rewrite call entirely (`rewrite_query([], ...)` returns instantly with no Groq call). Confirmed `chat_history.db` still stores the user's verbatim original query, not the rewritten one.

---

## 2026-06-20 — Frontend chat UI design

**Decision:**
- Styling: Tailwind CSS.
- Toast feedback for async ops: `sonner`.
- Data fetching: plain `fetch` + React state (no SWR/React Query).
- App Router (not Pages Router) — current Next.js standard, no real alternative worth debating.
- Backend error codes (503/502/500) are mapped to friendly, non-technical toast copy for the end customer ("Document search is temporarily unavailable" etc.) rather than exposing backend-debugging detail like "Is Ollama running?".
- No "clear history" or other destructive actions in this module — not requested, so not built.

**Alternatives considered:**
- CSS Modules — zero dependency, but materially slower to hand-write mobile-first/44px-touch-target rules.
- Hand-rolled toast component — full control, but real effort to match a maintained library's accessibility/animation handling.
- SWR — useful caching/revalidation, but solves a multi-view-cache problem this single chat thread doesn't have.

**Why:** All three picks reduce hand-written code for things (responsive styling, accessible toasts) that directly serve the project's existing mobile-first/toast-feedback conventions, with no real downside at this app's scale.

---

## 2026-06-25 — Fixed product-filtered cosmetic-exclusion retrieval gap: stopword filtering in BM25 tokenizer

**Decision:** Added English stopword filtering to `tokenize()` in `backend/app/rag/index_cache.py` (used for both BM25 indexing and query scoring, and shared with product-name detection in `retrieval.py`).

**Root cause (confirmed via direct diagnostics against the live Chroma collection, not guessed):** BM25 had no stopword removal. For a query like "What is excluded under cosmetic treatment in the Infinity policy?", common filler words ("the", "is", "in", "treatment", "policy") appear in nearly every chunk in the corpus — "treatment" has IDF 0.41, "policy" has IDF 1.26, vs. 4.16 for "cosmetic" (the only real distinguishing term). Despite the low IDF, raw term-frequency from these filler words still added up across the whole chunk, outscoring chunks that matched the one truly relevant word. Confirmed: the actual exclusion clause (4.1.8 Cosmetic or Plastic Surgery) ranked 15th in BM25 candidates and 13th in vector candidates — both inside the existing top-20 candidate pool (`HYBRID_CANDIDATE_MULTIPLIER=4`), but too far down for RRF fusion to place it in the final top-5 sent to the LLM. An OPD chunk that happened to repeat "treatment"/"policy" frequently won instead. This confirmed `HYBRID_CANDIDATE_MULTIPLIER`/pool size was not the problem — the chunk was already in the pool; ranking quality was.

**Alternatives considered:** (A, chosen) hardcoded English stopword list (~40 words), zero new dependency. (B) pull in `nltk`'s stopword list — more comprehensive but adds a dependency + a data-download step for a small, well-known list; overkill for a hobby project. (C) do nothing, document as a known limitation — rejected because this is a generalizable bug (any query phrased with common filler words around a rare distinguishing term would hit it), not a one-off.

**Verified 2026-06-25:** Re-ran the actual `retrieve()` function (not a standalone simulation) for all 3 cosmetic-exclusion queries — the correct exclusion clause (4.1.7/4.1.8 depending on product) now appears in the top-5 for Global Health, Infinity, and Health Gain. Re-ran the full eval harness (`evals/run_evals.py`): avg retrieval recall went 0.67 → **1.00**, hallucination rate stayed 0/8, no regressions on the other 5 cases (waiting period, OPD coverage, room rent, both refusal cases). Bonus: the room-rent query (previously logged as a separate minor known limitation) now also surfaces a more directly relevant chunk ("3.7.5 Change in Room Rent Limits").

**New, separate finding (not fixed, not in scope):** accuracy dropped to 6/8 (was 6/8 before too, but for a different reason now) — the 2 "partial" cases are the LLM correctly including a true detail from the real policy text (e.g. the Medical Practitioner certification clause) that's simply missing from the hand-drafted `expected_answer` ground truth in `test_cases.yaml`. This is a ground-truth precision gap in the eval set, not a retrieval or grounding bug — flagged for the user's eval review (per the existing user-owns-ground-truth split), not changed by Claude.

---

## 2026-06-25 — Two more user-found issues: missing product attribution in answers + LLM reranking step added

**Context:** User manually tested the just-fixed app and found 2 more issues: (1) "In which product are travel and stay expenses covered?" should answer from `product_name` metadata but didn't; (2) "What's the waiting period in the global product?" should surface section 4.3.1 of `indusind-global-health-pw` but failed. Asked for a systemic approach since "these are common problems," not one-off bugs.

**Issue 1 root cause (confirmed):** retrieval was correct — the right chunk (3.1.6 TRAVEL EXPENSES, Global Health) ranked #1. But `_build_prompt` in `backend/app/rag/chat.py` only included `section`/`subsection`/`topic` in each context block, never `product_name`. The LLM had zero access to which product a chunk belonged to in the text it reasons over — `product_name` only ever reached the separate `sources` array used for UI citations. Live-verified: the broken answer literally said *"The specific product name is not specified in the provided context."*

**Issue 2 root cause (confirmed, harder problem):** the target chunk (4.3.1, Initial 90-day Waiting Period) ranked 7th in pure vector similarity and 18th in BM25 — both outside the existing top-5 RRF fusion cutoff but inside the already-fetched top-20 candidate pool. Two clearly irrelevant chunks ("5.1.9 Withdrawal of Policy", "5.1.11 Premium Payment in Instalments") were crowding out legitimate matches in both rankings, purely from coincidental rare-word overlap (e.g. "product", "90 days") — not the same stopword-pollution bug as the earlier cosmetic-exclusion fix (confirmed: stripping stopwords from the query didn't move this chunk's vector rank at all, since vector search doesn't use the BM25 tokenizer).

**Decision (chosen after laying out pros/cons — see prior turn): two systemic fixes,** not query-specific patches, since the user named this as a recurring problem class:
1. **Always include full provenance in context** — `_build_prompt` now labels every block `f"{product_name} | {section_path}"` instead of just section/subsection/topic. Fixes the whole class of "which product..." questions, not just this one.
2. **Added an LLM reranking step** (`backend/app/rag/rerank.py::rerank_chunks`) — retrieval now keeps the full RRF candidate pool (`candidate_n`, already fetched, no new fetch) instead of slicing to `top_k` immediately, and asks Groq (`RERANK_MODEL = GROQ_MODEL`, same 70b model as query rewriting, for the same accuracy-over-cost reason logged on 2026-06-23) to pick and reorder the true top-`top_k` from that larger pool via a JSON-mode response. Fails open to `chunks[:top_k]` (the old behavior) on any Groq/JSON error. This is the standard "retrieve-then-rerank" pattern — reuses the existing fused candidate pool, no re-embedding or new infra.

**Alternatives considered:** patch case-by-case (rejected — doesn't scale, user explicitly flagged this as recurring); swap to a stronger embedding model (rejected for now — requires re-embedding the whole corpus, no guaranteed fix, doesn't address issue 1 at all); expand eval harness only (necessary regardless, but detection-only, doesn't fix anything by itself — deferred to a later pass).

**Real regression caught and fixed during verification:** the first version of the Class-A system-prompt addition ("If asked which product something applies to, answer using that label...") was too broad — the LLM started parroting the literal `[Product | Section > Subsection]` bracket label into its prose for unrelated questions (e.g. "...as certified... (SECTION-4 EXCLUSIONS > 4.1.8)"). Since that label text isn't in the raw chunk text the hallucination judge checks against, this correctly tripped 2 new hallucination flags on the next eval run (hallucination rate 0/8 → 2/8) — a real regression from my own change, not a judge bug this time. Fixed by tightening the instruction: "labeled... for your reference only — do not quote these labels in your answer... state the product name in your own words." Re-verified live after the fix: both re-tested answers are clean natural-language prose with no bracket artifacts.

**Verification status:** Class-A fix and the de-citation fix both confirmed live, twice, against the running server. Reranker confirmed live once via direct function call (eliminated both false-positive chunks from the issue-2 query) and previously via direct retrieval-layer testing pre-rate-limit. **Full eval-suite re-run could not be completed** — ran into Groq's free-tier daily token budget (100k TPD) mid-session from the combined volume of today's testing (diagnostics + 2 eval runs + reranking added a 3rd Groq call per query, ~50% more token usage per request than before). Confirmed via direct traceback this is a rolling 24h window, not a fixed-time reset — repeated retries over ~15 min stayed pinned at the cap rather than clearing. **Action item for next session: re-run `evals/run_evals.py` once quota recovers (next day) to get a clean before/after comparison and confirm no other regressions.**

**Operational note (new, worth tracking):** reranking permanently adds one Groq call to every single query (previously: rewrite [conditional] + answer; now: rewrite [conditional] + rerank + answer). On the free tier's 100k TPD budget, this lowers the number of test queries available per day before hitting the limit — worth keeping in mind during future heavy manual-testing or eval sessions.

---

## 2026-06-25 — Tested moving reranking to a cheaper/separate-budget Groq model, reverted

**Context:** Groq's TPD rate limits are per-model, not account-wide (confirmed via Groq's official rate-limits docs) — `llama-3.3-70b-versatile` has its own 100k TPD bucket, separate from other free models like `llama-3.1-8b-instant` or `openai/gpt-oss-120b`/`20b` (200k TPD). Since reranking now fires on every query and shares the same 70b bucket as answering and query rewriting, moving just the reranker to a different model would draw from an independent budget — directly addressing the rate-limit issue hit earlier today, without touching the answer-quality-critical 70b calls.

**Tested, with real candidate pools (not synthetic), via direct `rerank_chunks`/raw Groq calls — not just assumed:**
- `llama-3.1-8b-instant`: produces structurally malformed JSON on the rerank task — `{"ranked": [[680], [7]]}` (nested garbage, not a flat int array) on one query, and a separate run silently selected only 2 of 5 truly relevant chunks on another. The malformed-JSON case triggers `rerank_chunks`'s fail-open path (`TypeError` on iterating a non-list), silently falling back to the pre-rerank RRF order — meaning the failure is invisible in production without this kind of direct testing.
- `openai/gpt-oss-120b` and `openai/gpt-oss-20b`: produced syntactically valid JSON but picked confidently *wrong* answers — for the "waiting period in the global product" query, both selected only `[17]`, "3.1 Global Cover (Applicable outside India)" (a section header), and completely ignored all 5 legitimate waiting-period clauses in the same 20-chunk candidate pool (4.1.1, 4.1.2, 3.3.3, 4.3.1, 4.4.1). Likely pattern-matched on the literal word "Global" rather than judging actual relevance to "waiting period."
- `llama-3.3-70b-versatile` on the same pool: rate-limited mid-test (couldn't get a fresh side-by-side), but its previously-recorded behavior on this exact query (earlier in the session) correctly excluded the 2 known false-positive chunks and surfaced multiple genuine waiting-period clauses.

**Decision: reverted `RERANK_MODEL` back to `GROQ_MODEL` (`llama-3.3-70b-versatile`).** Not a borderline call — both cheaper alternatives failed for different, concrete reasons (one breaks structurally, the other reasons confidently wrong), not just "feels a bit worse." Trading a rate-limit inconvenience for actually-wrong grounding chunks is a worse outcome than the status quo. No code change needed beyond the config revert — the live server was never restarted with the cheaper model during testing (all comparisons ran via standalone scripts), so production was unaffected throughout.

**Why this matters beyond this one decision:** confirms the project's existing pattern (first seen 2026-06-23 with query rewriting) generalizes — Groq's smaller free models are not reliable for structured/precision-sensitive sub-tasks in this pipeline, even ones that seem "simple" (picking/ordering from a list) on paper. Default to `llama-3.3-70b-versatile` for any new LLM-based step unless explicitly tested otherwise.

**Still open:** the root problem (reranking adds a 3rd 70b call per query, tightening the shared 100k TPD budget) is unresolved by this experiment. Lower-risk alternatives not yet tried: making reranking conditional (skip when the top fused result clearly dominates, mirroring how query rewriting already skips when there's no history), or simply accepting the cost as a hobby-project tradeoff. Revisit if rate-limiting becomes a recurring practical problem rather than a one-off heavy-testing-day issue.

---

## 2026-06-25 — Considered NVIDIA Nemotron Rerank VL via OpenRouter, rejected before building; made reranking conditional instead

**Context:** user proposed switching the reranker to `nvidia/llama-nemotron-rerank-vl-1b-v2:free` via OpenRouter, calling it "the best open ranking model available," as a fix for the recurring Groq rate-limit pressure.

**Researched before building (not assumed):**
- The model is real and free, but is a **vision-language** reranker purpose-built for visual documents (screenshots, slides, charts/infographics-as-images) — a domain mismatch for this project's plain extracted-text chunks. It would likely still accept text-only input, but isn't tuned or benchmarked for it.
- OpenRouter's free tier (`:free` models) is capped at **50 requests/day combined across all free models** (1000/day if $10 of credit is purchased) — tighter than Groq's per-model 100k TPD bucket, so moving reranking here risked making rate-limiting *worse*, not better, without a paid top-up.
- The text-appropriate option on the same OpenRouter rerank API, `cohere/rerank-v3.5`, is paid ($0.001/search) — not free, contradicting the hobby-project default.
- One real positive found: OpenRouter's dedicated `/api/v1/rerank` endpoint returns structured `relevance_score` per document directly (true cross-encoder pattern), avoiding the JSON-parsing failure mode that broke `llama-3.1-8b-instant` and `gpt-oss` on Groq (see prior entry same day). This part of the idea has merit, just not with this specific free model + free-tier combo for this project's text-only data.

**Decision:** did not adopt the NVIDIA OpenRouter model. Instead, implemented **conditional reranking** — the lower-risk alternative already flagged as "not yet tried" in the entry above, which addresses the same root problem (reranking's 3rd Groq call per query draining the shared 70b budget) without introducing a new account, a tighter request cap, or a domain-mismatched model.

**Design (laid out and confirmed before building):** looked for a score-based signal that could reliably predict "this query needs reranking" using the two already-diagnosed real cases (cosmetic-exclusion = didn't need it, waiting-period-ambiguity = did need it) as calibration points:
- RRF fused-score margin (top1 vs top-k): **not usable** — `1/(60+rank)` compresses to a near-identical tiny gap regardless of query, by construction of the RRF formula itself.
- Raw top vector score alone: **not usable** — nearly identical (~0.68-0.70) for both the case that needed reranking and the case that didn't.
- **Spread of raw vector scores across the top-5 candidates (max−min): usable** — 0.029 (cosmetic, didn't need rerank) vs. 0.048 (waiting period, did need rerank). Real, measurable, directionally-correct difference, though calibrated off only 2 data points — flagged to the user as a first-pass heuristic, not a validated one, same caveat-handling as the existing `RELEVANCE_THRESHOLD`.

**Built:** `RERANK_SPREAD_THRESHOLD = 0.035` in `backend/app/core/config.py` (picked as the rough midpoint between the two calibration points). New `_needs_rerank(vector_scores, top_k)` in `backend/app/rag/retrieval.py` — computes `vector_scores[0] - vector_scores[top_k-1]`; skips the Groq rerank call (uses the RRF-fused order directly) when spread is below threshold, calls `rerank_chunks` as before when at/above it. Treats "fewer than `top_k` candidates available" as needing rerank by default (not enough data to judge confidently).

**Verified 2026-06-25:** ran the gating logic (no Groq calls needed for this part) across all 8 known eval-style queries: cosmetic-exclusion ×3, room-rent, and the cross-product travel-expense question all correctly **skip** reranking now (5/8 total) — saving a Groq call on each. The actual target case ("waiting period in the global product") still correctly **triggers** reranking. Two borderline cases (PED waiting period, OPD coverage) also trigger it — both already worked fine without reranking, so this is an unnecessary-but-harmless extra call, not a correctness problem; they're in the same naturally high-variance "waiting period"/"coverage" topic family. Live end-to-end re-test of the target query through the full `/chat` endpoint after restarting the server: still produces a correct, fully-grounded answer ("24/36 months... 36 months... 30 days...") with no false-positive sources.

**Not yet done:** the full eval-suite re-run is still pending (blocked by the same Groq daily quota exhaustion as the prior entry — confirmed via a live request hitting the rate limit again mid-verification). Carries over as the top priority for next session, now also serving to validate this new gating threshold against the full eval set, not just the 8 manually-checked queries above.

**Follow-up attempt same day:** tried again later — a trivial test message ("hi", 212 total tokens) succeeded, which looked like the quota had cleared, but running the actual eval suite immediately after failed all 8/8 cases with 429s (still ~99,450/100,000 used). **Lesson: a trivial test request is not a valid signal that the daily quota has recovered enough for real ~1000+ token RAG requests** — this is the second time in one day a tiny probe gave false confidence; always test with a realistically-sized prompt before trusting quota is available. Deferred to next session per user's call — by then the rolling 24h window should have genuinely rolled past today's heavy usage.

---

## 2026-06-25 — Issue 3: product name not visible enough in the chat response

**Context:** user found that even after the Class-A fix (product name in LLM context + system-prompt nudge), it was still hard to tell which product a given answer was about unless the LLM happened to mention it in prose or the user expanded the collapsed "Sources (N)" citation list.

**Decision:** rather than relying further on LLM prose (same reliability concern raised throughout this session — see the rerank-model testing entries), added a **deterministic backend-derived field**, no LLM involved, zero extra Groq cost:
- `backend/app/rag/chat.py`: `ChatAnswer` gained a `products: list[str]` field — unique product names from the answer's retrieved chunks, order of first appearance, computed via `_unique_products()`. Empty for the not-found/refusal case.
- `backend/app/api/chat.py`: threaded `products` into both `ChatResponse` (live chat) and `HistoryTurn` (history replay) — the history endpoint derives it from the stored `sources` JSON at read time rather than a DB migration, since `product_name` was already being stored per source.
- Frontend: `lib/types.ts` (`products: string[]` on `ChatResponse`/`HistoryTurn`/`Message`), `app/page.tsx` (threads the field through both the live-send and history-load paths), `components/MessageBubble.tsx` (renders a small pill/badge per product above the answer text, visible immediately, not buried behind the collapsible citations like before).

**Real pre-existing bug found and fixed while verifying (in scope, since it broke verification):** `app/api/chat.py`'s `/history` endpoint crashed with a `KeyError`/Pydantic validation error on old debug session IDs (`ce9d839e-...`, `verify-hybrid-*`) whose stored `sources` JSON predates the `product_name` field being added (pre-2026-06-23, before product filtering existed). Fixed with a defensive `.get("product_name")` + filter instead of a direct dict-key/required-field access, so old history rows degrade to an empty `products` list instead of a 500.

**Separate, pre-existing bug found but NOT fixed (out of scope, no user-facing impact):** the same legacy sessions also fail `SourceOut` Pydantic validation entirely (`product_name` is a required field with no default) — this would have 500'd on the original `/history` code too, before today's change. Only affects old Claude-created debug session IDs, not real user sessions (the real user's session ID is a `crypto.randomUUID()` created after product filtering existed). Flagged to the user, not fixed — not worth touching dead debug data for a hobby project.

**Verified 2026-06-25:** `npx tsc --noEmit` and `npx eslint .` both clean on the frontend. Backend: confirmed via `GET /history/diag-test-final` (a real session from earlier today's testing) that `products` correctly returns `["Indusind Global Health"]` derived from that turn's sources, with zero additional Groq calls (pure backend logic, verified during the ongoing Groq quota outage without needing to wait for it).

---

## 2026-06-25 — Conflicting-queries discussion: shipped the cheap cross-product disambiguation fix, flagged a deeper chunking gap

**Context:** discussed how to handle genuinely ambiguous/conflicting queries. Distinguished two different cases: cross-product ambiguity (already well-supported — `product_name` is reliable in every chunk's metadata) vs. within-product sub-scope ambiguity (the one concrete example found: "Global Cover" vs "India Cover" each having their own different initial waiting period — 90 days vs 30 days — within the same Indusind Global Health product).

**Real blocker found before building anything:** checked the actual stored chunk metadata for the Global-Cover/India-Cover example specifically, and the qualifier that distinguishes them ("4.3 Specific Exclusions (**Applicable to 3.1 Global Cover**)" / "4.4 ... (**Applicable to 3.2 India Cover**)") lives in a *parent* heading that was never captured by chunking — `topic` is empty for both `4.3.1` and `4.4.1` chunks, and the chunk text is otherwise identical apart from "90" vs "30". **No prompt instruction can fix this** — the LLM has no way to know which clause is which, because that information doesn't exist in what it's shown. Same root cause as the already-accepted "4th-tier nesting" limitation logged 2026-06-19. A real fix would mean touching `chunking.py` to capture parent "Applicable to X" headings and re-running ingestion — out of scope for what was agreed (cheap prompt-only fix), and not worth doing off a single observed instance per the project's evidence-based approach this session. Logged as a known, deeper limitation, not fixed.

**What was actually built:** broadened the existing Class-A system-prompt instruction in `backend/app/rag/chat.py` from "only mention the product if explicitly asked" to **always** attributing facts to their product when context spans more than one: `"If the context contains facts from more than one product, do not blend them into one undifferentiated statement — clearly state which product each fact applies to."` This works because `product_name` is reliably present for every chunk (unlike the Global/India Cover case above).

**Verified 2026-06-25:** live test of "Is cosmetic surgery covered?" (an unfiltered query that pulls chunks from all 3 products into context) — the same exclusion rule applies to all 3 products, and the answer correctly named all three explicitly: *"This applies to Indusind Health Gain, Indusind Health Infinity, and Indusind Global Health"* rather than silently stating the rule once with no attribution. **Not yet verified:** the harder case where products have genuinely *different* values (e.g. room rent limit, which likely differs by product) — attempted but hit the Groq daily rate limit again mid-test. Carries over to next session alongside the eval-suite re-run already pending.

---

## 2026-06-25 — Generating a new Groq API key does not reset the rate limit

**Finding:** user generated a new Groq API key hoping for fresh quota. Tested it directly — both the old and new key resolve to the same organization ID (`org_01kv641dr5ebx8ad1eksqxkcy8`). **Groq's TPD rate limits are scoped to the organization, not the individual API key** — a new key on the same account shares the exact same exhausted 100k-token bucket (confirmed still at ~99,159/100,000 used immediately after switching keys and restarting the backend). A genuinely separate quota pool would require a different Groq account (different email/org), not just a new key.

**Action:** none taken — reverted to waiting for the existing 24h rolling window to clear, per user's call. Worth remembering for any future "let's just get a new key" instinct on this or other per-org-rate-limited providers (this is standard behavior, not Groq-specific — same model as Anthropic/OpenAI org-level limits).

---

## 2026-06-25 — Tried NVIDIA's nv-rerankqa-mistral-4b-v3 (build.nvidia.com), blocked by account permissions, reverted

**Context:** user proposed a second NVIDIA reranker candidate — `nv-rerankqa-mistral-4b-v3`, a purpose-built text QA cross-encoder (not the vision-language model already rejected). Architecturally promising: dedicated `/reranking` endpoint returning structured `relevance_score` floats directly (same favorable pattern as OpenRouter's `/rerank`), 512-token passage limit comfortably fits this project's 300-token chunks, free tier needs no credit card.

**Tested directly, not just read about:** user signed up and added `NVIDIA_API_KEY` to `backend/.env`. Confirmed the key itself is valid — `GET https://integrate.api.nvidia.com/v1/models` returns 200 with 121 models visible. But calling the actual reranking endpoint (`POST https://ai.api.nvidia.com/v1/retrieval/nvidia/nv-rerankqa-mistral-4b-v3/reranking`) returned `404: "Function '...': Not found for account '...'"`, and zero rerank-category models appear in that same `/v1/models` list for this account.

**Root cause (confirmed via NVIDIA's own developer forums, not assumed):** this is a known, recurring issue — personal/free `build.nvidia.com` accounts often lack a "Public API Endpoints" permission that specifically gates the retrieval/reranking endpoint category, separate from the chat-completion models (which work fine). Multiple active forum threads describe the identical error for the identical reason. Fixing it requires NVIDIA support manually enabling the permission on the account — not something fixable via request format, code, or model choice on our side.

**Decision: left as-is, did not pursue further.** Realistic options were (a) file a request with NVIDIA and wait on an unknown timeline, (b) self-host the NIM container, which needs real GPU hardware — a much heavier lift than anything else this session, or (c) keep the already-working conditional-reranking-on-Groq-70b setup (built and verified earlier 2026-06-25). User chose (c). The `NVIDIA_API_KEY` env var and standalone test script remain unused; no production code was touched by this exploration. Revisit only if the NVIDIA permission issue resolves itself or gets manually granted later, and only if Groq's shared-budget rate-limiting becomes a recurring practical problem rather than today's one-off heavy-testing-day issue.

---
