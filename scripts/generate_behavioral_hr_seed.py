"""One-shot LLM synthesis of BEHAVIORAL and HR seed docs.

No adequate public dataset exists for these domains (see Kaggle HR dataset
rejection — 2.5M rows collapsed to 40 real templates with a text bug). This
generates original STAR-format behavioral and professional HR Q&A pairs via
the same LLM used for JD-specific knowledge synthesis (services/jd_service.py),
covering a fixed set of curated topics per domain.

Merges results directly into data/knowledge_base_seed.json (append, dedup by
question text). Run scripts/ingest_knowledge_base.py afterwards to index into Qdrant.
"""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import structlog

from services.json_utils import extract_json
from services.llm_service import llm_service

logger = structlog.get_logger()

SEED_PATH = Path(__file__).parent.parent / "data" / "knowledge_base_seed.json"

_QUESTIONS_PER_TOPIC = 5

_BEHAVIORAL_TOPICS = [
    "Teamwork & Collaboration",
    "Conflict Resolution",
    "Leadership & Ownership",
    "Handling Failure & Mistakes",
    "Time Management & Prioritization",
    "Communication Under Pressure",
    "Adaptability & Change",
    "Initiative & Problem Solving",
]

_HR_TOPICS = [
    "Motivation & Career Goals",
    "Culture Fit & Values",
    "Compensation & Expectations",
    "Work Style & Preferences",
    "Availability & Logistics",
    "Strengths & Weaknesses",
    "Company Knowledge & Interest",
    "Handling Feedback & Growth",
]

_BEHAVIORAL_SYSTEM = (
    "You are an expert behavioral interview coach. Generate realistic behavioral interview "
    "questions with STAR-format (Situation, Task, Action, Result) ideal answer exemplars. "
    "Return ONLY a valid JSON object with a single key 'questions' whose value is an array. "
    "No preamble, no explanation, no markdown."
)

_HR_SYSTEM = (
    "You are an expert HR interviewer. Generate realistic HR-round interview questions with "
    "strong, professional ideal answer exemplars. "
    "Return ONLY a valid JSON object with a single key 'questions' whose value is an array. "
    "No preamble, no explanation, no markdown."
)


def _build_prompt(domain: str, topic: str, count: int) -> str:
    style = (
        "Each ideal_answer must be a STAR-structured exemplar (explicitly cover Situation, "
        "Task, Action, Result in flowing prose, not labeled sections)."
        if domain == "BEHAVIORAL"
        else "Each ideal_answer must be a concise, professional exemplar answer."
    )
    return f"""Generate {count} {domain.lower()} interview Q&A pairs for the topic: "{topic}".

{style}

Return a JSON object with this exact structure:
{{"questions": [
  {{"question": "...", "ideal_answer": "...", "difficulty": 2}},
  ...
]}}

Each element must have:
- question: the interview question (string)
- ideal_answer: the exemplar answer (string)
- difficulty: integer 1-5 (most behavioral/HR questions are 1-3)

Vary phrasing and scenario across the {count} questions — do not repeat the same wording."""


def _valid_doc(doc: object) -> bool:
    return isinstance(doc, dict) and all(k in doc for k in ("question", "ideal_answer"))


async def _generate_topic(domain: str, topic: str) -> list[dict]:
    system = _BEHAVIORAL_SYSTEM if domain == "BEHAVIORAL" else _HR_SYSTEM
    prompt = _build_prompt(domain, topic, _QUESTIONS_PER_TOPIC)
    try:
        raw = await llm_service.generate(prompt, system_prompt=system, json_mode=True)
        obj = extract_json(raw)
        docs = obj.get("questions", [])
        return [
            {
                "domain": domain,
                "topic": topic,
                "question": d["question"],
                "ideal_answer": d["ideal_answer"],
                "difficulty": d.get("difficulty", 2),
                "tags": ["llm_synthesized"],
            }
            for d in docs
            if _valid_doc(d)
        ]
    except Exception as exc:
        logger.warning("behavioral_hr_gen_failed", domain=domain, topic=topic, error=str(exc))
        return []


async def main() -> None:
    with open(SEED_PATH) as f:
        existing = json.load(f)

    seen_questions = {d["question"].strip().lower() for d in existing}
    print(f"Existing seed docs: {len(existing)}")

    new_docs: list[dict] = []
    for domain, topics in (("BEHAVIORAL", _BEHAVIORAL_TOPICS), ("HR", _HR_TOPICS)):
        for topic in topics:
            print(f"Generating {domain} / {topic}...")
            docs = await _generate_topic(domain, topic)
            print(f"  -> {len(docs)} docs")
            for doc in docs:
                key = doc["question"].strip().lower()
                if key not in seen_questions:
                    seen_questions.add(key)
                    new_docs.append(doc)

    print(f"New unique docs to add: {len(new_docs)}")
    merged = existing + new_docs

    with open(SEED_PATH, "w") as f:
        json.dump(merged, f, indent=2)

    print(f"Wrote {len(merged)} total docs to {SEED_PATH}")


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
