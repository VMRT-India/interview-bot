"""One-shot fetch of external public interview-question datasets into
data/knowledge_base_seed.json's schema. Run manually, not part of the app.

Sources:
- Hugging Face K-areem/AI-Interview-Questions (technical, no auth required)
- Kaggle syedmharis/software-engineering-interview-questions-dataset (technical, needs
  KAGGLE_USERNAME/KAGGLE_KEY in .env)

Merges results directly into data/knowledge_base_seed.json (append, dedup by question text).
Run scripts/ingest_knowledge_base.py afterwards to index into Qdrant.
"""
import csv
import json
import re
import sys
import tempfile
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv

SEED_PATH = Path(__file__).parent.parent / "data" / "knowledge_base_seed.json"
HF_ROWS_URL = "https://datasets-server.huggingface.co/rows"

_DIFFICULTY_MAP = {"easy": 1, "medium": 2, "hard": 3}

_INST_RE = re.compile(r"<s>\s*\[INST\](.*?)\[/INST\](.*?)</s>", re.DOTALL)

_TOPIC_KEYWORDS = {
    "uml": "Software Design & Modeling",
    "design pattern": "Software Design & Modeling",
    "agile": "Development Methodology",
    "waterfall": "Development Methodology",
    "hbase": "Big Data",
    "pig": "Big Data",
    "hadoop": "Big Data",
    "sql injection": "Security",
    "hash": "Security",
    "encrypt": "Security",
    "database": "Database Systems",
    "java": "Programming Languages",
    "thread": "Concurrency",
    "concurren": "Concurrency",
}


def _infer_topic(question: str) -> str:
    q_lower = question.lower()
    for kw, topic in _TOPIC_KEYWORDS.items():
        if kw in q_lower:
            return topic
    return "Software Engineering"


def fetch_hf_technical(dataset: str, split: str) -> list[dict]:
    docs = []
    offset = 0
    length = 100
    total = None
    consecutive_failures = 0
    while total is None or offset < total:
        data = None
        for attempt in range(6):
            try:
                resp = httpx.get(
                    HF_ROWS_URL,
                    params={
                        "dataset": dataset,
                        "config": "default",
                        "split": split,
                        "offset": offset,
                        "length": length,
                    },
                    timeout=30,
                )
                if resp.status_code in (429, 500, 502, 503):
                    time.sleep(3 * (attempt + 1))
                    continue
                resp.raise_for_status()
                data = resp.json()
                break
            except httpx.HTTPError:
                time.sleep(3 * (attempt + 1))

        if data is None:
            consecutive_failures += 1
            print(f"  WARN: giving up on offset {offset} after retries, skipping page")
            if consecutive_failures >= 5:
                print("  ABORT: too many consecutive page failures, stopping this split")
                break
            offset += length
            continue
        consecutive_failures = 0
        rows = data.get("rows", [])
        if not rows:
            break

        for row in rows:
            text = row.get("row", {}).get("text", "")
            match = _INST_RE.search(text)
            if not match:
                continue
            question = match.group(1).strip()
            answer = match.group(2).strip()
            if not question or not answer:
                continue
            docs.append(
                {
                    "domain": "TECHNICAL",
                    "topic": _infer_topic(question),
                    "question": question,
                    "ideal_answer": answer,
                    "difficulty": 2,
                    "tags": ["hf_import"],
                }
            )

        total = data.get("num_rows_total", total)
        offset += length
        time.sleep(1.0)

    return docs


def fetch_kaggle_technical(dataset: str) -> list[dict]:
    load_dotenv(Path(__file__).parent.parent / ".env")
    from kaggle.api.kaggle_api_extended import KaggleApi

    api = KaggleApi()
    api.authenticate()

    with tempfile.TemporaryDirectory() as tmp_dir:
        api.dataset_download_files(dataset, path=tmp_dir, unzip=True)
        csv_path = next(Path(tmp_dir).glob("*.csv"))

        docs = []
        with open(csv_path, newline="", encoding="utf-8", errors="replace") as f:
            for row in csv.DictReader(f):
                question = (row.get("Question") or "").strip()
                answer = (row.get("Answer") or "").strip()
                if not question or not answer:
                    continue
                docs.append(
                    {
                        "domain": "TECHNICAL",
                        "topic": (row.get("Category") or "Software Engineering").strip(),
                        "question": question,
                        "ideal_answer": answer,
                        "difficulty": _DIFFICULTY_MAP.get(
                            (row.get("Difficulty") or "").strip().lower(), 2
                        ),
                        "tags": ["kaggle_import"],
                    }
                )
        return docs


def main() -> None:
    with open(SEED_PATH) as f:
        existing = json.load(f)

    seen_questions = {d["question"].strip().lower() for d in existing}
    print(f"Existing seed docs: {len(existing)}")

    new_docs = []
    for split in ("train", "eval"):
        print(f"Fetching K-areem/AI-Interview-Questions [{split}]...")
        docs = fetch_hf_technical("K-areem/AI-Interview-Questions", split)
        print(f"  -> {len(docs)} parsed rows")
        for doc in docs:
            key = doc["question"].strip().lower()
            if key not in seen_questions:
                seen_questions.add(key)
                new_docs.append(doc)

    print("Fetching Kaggle syedmharis/software-engineering-interview-questions-dataset...")
    kaggle_docs = fetch_kaggle_technical(
        "syedmharis/software-engineering-interview-questions-dataset"
    )
    print(f"  -> {len(kaggle_docs)} parsed rows")
    for doc in kaggle_docs:
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
    sys.exit(main())
