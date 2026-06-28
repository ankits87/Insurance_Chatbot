"""
Eval harness for the Chatbot RAG pipeline.

Run from the backend/ directory so .env / venv resolve correctly:
    cd backend && .venv/Scripts/python.exe ../evals/run_evals.py

Scores each test case in test_cases.yaml on 4 dimensions:
1. Retrieval quality — did the expected chunks get retrieved?
2. Answer accuracy — does the generated answer match the expected answer? (LLM-judged)
3. Citation quality — are the cited sources the right ones?
4. Hallucination rate — does the answer claim anything not in the retrieved context? (LLM-judged)
"""

import json
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

EVALS_DIR = Path(__file__).resolve().parent
BACKEND_DIR = EVALS_DIR.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

import httpx
import yaml
from groq import Groq, GroqError

from app.core.config import GROQ_MODEL
from app.rag.chat import answer_question

_judge_client = Groq()

ACCURACY_JUDGE_PROMPT = """You are evaluating a RAG chatbot's answer against a ground-truth expected answer.

Question: {query}

Expected answer: {expected_answer}

Generated answer: {generated_answer}

Judge whether the generated answer is factually consistent with the expected answer's substance. \
Paraphrasing or extra detail is fine; missing or contradicting key facts is not.

Respond with ONLY valid JSON, no other text:
{{"verdict": "correct" | "partial" | "incorrect", "reason": "<one sentence>"}}"""

HALLUCINATION_JUDGE_PROMPT = """You are checking a RAG chatbot's answer for hallucinations \
— specific factual claims (numbers, dates, named clauses/codes, coverage amounts or conditions) \
that are NOT supported by the provided source context.

Source context:
{context}

Generated answer: {generated_answer}

Rules:
- If the answer declines to answer, says the information isn't available, or hedges, that is \
NOT a hallucination by itself — even if that exact refusal wording doesn't appear in the context.
- Only flag a claim if it asserts a specific fact (a number, a clause code, a coverage detail, a \
named condition) that contradicts the context or has no basis in it at all.
- Do not flag paraphrasing, summarization, or restating the question as a claim.
- Quote the specific unsupported fact itself, not the whole sentence or the question.

Respond with ONLY valid JSON, no other text:
{{"hallucinated": true | false, "unsupported_claims": ["<specific fact>", ...]}}"""


def _normalize(text: str) -> str:
    return re.sub(r"[\s:.,;]+$", "", text.strip().lower())


def _subsection_matches(expected: str, actual: str) -> bool:
    e, a = _normalize(expected), _normalize(actual)
    return e == a or e in a or a in e


def _parse_judge_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"parse_error": True, "raw": text}


def score_chunk_match(expected_chunks: list[dict], actual_chunks: list) -> dict:
    if not expected_chunks:
        return {"applicable": False}

    hits = 0
    for expected in expected_chunks:
        found = any(
            _normalize(expected["product_name"]) == _normalize(actual.product_name)
            and _normalize(expected["section"]) == _normalize(actual.section)
            and _subsection_matches(expected["subsection"], actual.subsection)
            for actual in actual_chunks
        )
        hits += int(found)

    return {
        "applicable": True,
        "expected_count": len(expected_chunks),
        "hits": hits,
        "recall": hits / len(expected_chunks),
    }


def judge_answer_accuracy(query: str, expected_answer: str, generated_answer: str) -> dict:
    if not expected_answer:
        return {"verdict": "skipped"}
    prompt = ACCURACY_JUDGE_PROMPT.format(
        query=query, expected_answer=expected_answer, generated_answer=generated_answer
    )
    response = _judge_client.chat.completions.create(model=GROQ_MODEL, messages=[{"role": "user", "content": prompt}])
    return _parse_judge_json(response.choices[0].message.content)


def judge_hallucination(context_text: str, generated_answer: str) -> dict:
    prompt = HALLUCINATION_JUDGE_PROMPT.format(
        context=context_text or "(no context retrieved)", generated_answer=generated_answer
    )
    response = _judge_client.chat.completions.create(model=GROQ_MODEL, messages=[{"role": "user", "content": prompt}])
    return _parse_judge_json(response.choices[0].message.content)


@dataclass
class CaseResult:
    id: str
    query: str
    generated_answer: str
    grounded: bool
    retrieval: dict
    citation: dict
    accuracy: dict
    hallucination: dict
    error: str | None = None


def run_case(case: dict) -> CaseResult:
    try:
        result = answer_question(case["query"])
    except (httpx.ConnectError, httpx.HTTPError, ConnectionError, GroqError) as exc:
        return CaseResult(
            id=case["id"],
            query=case["query"],
            generated_answer="",
            grounded=False,
            retrieval={"applicable": False},
            citation={"applicable": False},
            accuracy={"verdict": "error"},
            hallucination={"hallucinated": None},
            error=str(exc),
        )

    expected_chunks = case.get("expected_chunks", [])
    retrieval_score = score_chunk_match(expected_chunks, result.sources)
    citation_score = score_chunk_match(expected_chunks, result.sources)

    must_include = case.get("must_include", [])
    must_include_hits = [kw for kw in must_include if kw.lower() in result.answer.lower()]
    accuracy = judge_answer_accuracy(case["query"], case.get("expected_answer", ""), result.answer)
    accuracy["must_include_ok"] = len(must_include_hits) == len(must_include)
    accuracy["must_include_hits"] = must_include_hits

    context_text = "\n\n".join(chunk.text for chunk in result.sources)
    hallucination = judge_hallucination(context_text, result.answer)

    return CaseResult(
        id=case["id"],
        query=case["query"],
        generated_answer=result.answer,
        grounded=result.grounded,
        retrieval=retrieval_score,
        citation=citation_score,
        accuracy=accuracy,
        hallucination=hallucination,
    )


def print_report(results: list[CaseResult]) -> None:
    for r in results:
        print(f"\n=== {r.id} ===")
        print(f"Q: {r.query}")
        if r.error:
            print(f"  ERROR: {r.error}")
            continue
        if r.retrieval["applicable"]:
            print(f"  Retrieval recall: {r.retrieval['hits']}/{r.retrieval['expected_count']}")
        else:
            print("  Retrieval: N/A (no expected chunks)")
        print(f"  Accuracy verdict: {r.accuracy.get('verdict')} (must_include_ok={r.accuracy.get('must_include_ok')})")
        if r.accuracy.get("reason"):
            print(f"    reason: {r.accuracy['reason']}")
        print(f"  Hallucinated: {r.hallucination.get('hallucinated')}")
        if r.hallucination.get("unsupported_claims"):
            print(f"    unsupported claims: {r.hallucination['unsupported_claims']}")

    total = len(results)
    correct = sum(1 for r in results if r.accuracy.get("verdict") == "correct")
    hallucinated = sum(1 for r in results if r.hallucination.get("hallucinated") is True)
    applicable_retrieval = [r for r in results if r.retrieval.get("applicable")]
    avg_recall = (
        sum(r.retrieval["recall"] for r in applicable_retrieval) / len(applicable_retrieval)
        if applicable_retrieval
        else None
    )
    print("\n=== Summary ===")
    print(f"Cases: {total} | Accuracy correct: {correct}/{total} | Hallucination rate: {hallucinated}/{total}")
    if avg_recall is not None:
        print(f"Avg retrieval recall (where applicable): {avg_recall:.2f}")


def write_json_report(results: list[CaseResult]) -> Path:
    results_dir = EVALS_DIR / "results"
    results_dir.mkdir(exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = results_dir / f"run_{timestamp}.json"
    out_path.write_text(json.dumps([asdict(r) for r in results], indent=2), encoding="utf-8")
    return out_path


def main() -> None:
    cases = yaml.safe_load((EVALS_DIR / "test_cases.yaml").read_text(encoding="utf-8"))
    results = [run_case(case) for case in cases]
    print_report(results)
    out_path = write_json_report(results)
    print(f"\nFull results written to {out_path}")


if __name__ == "__main__":
    main()
