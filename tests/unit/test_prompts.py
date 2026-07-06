from prompts.closing import build_closing_prompt
from prompts.evaluator import build_eval_prompt
from prompts.interviewer import (
    build_closing_turn_prompt,
    build_conclude_check_prompt,
    build_system_prompt,
    build_user_prompt,
)


# ---------------------------------------------------------------------------
# interviewer.py
# ---------------------------------------------------------------------------

def test_system_prompt_contains_domain_and_difficulty():
    prompt = build_system_prompt("TECHNICAL", 3)
    assert "TECHNICAL" in prompt
    assert "3/5" in prompt


def test_system_prompt_no_extras_by_default():
    prompt = build_system_prompt("BEHAVIORAL", 2)
    assert "Knowledge Base" not in prompt
    assert "Job Description" not in prompt


def test_system_prompt_injects_context():
    chunks = ["Q: What is a hash?\nA: A key-value mapping.", "Q: Explain O(n).\nA: Linear time."]
    prompt = build_system_prompt("TECHNICAL", 2, context=chunks)
    assert "Knowledge Base Context" in prompt
    assert "What is a hash?" in prompt
    assert "Explain O(n)." in prompt


def test_system_prompt_empty_context_list_omits_section():
    prompt = build_system_prompt("TECHNICAL", 2, context=[])
    assert "Knowledge Base" not in prompt


def test_system_prompt_injects_jd():
    prompt = build_system_prompt("HR", 1, jd_text="Requires 5 years of Python experience.")
    assert "Role Context" in prompt
    assert "5 years of Python" in prompt
    assert "Align every question" in prompt


def test_system_prompt_no_resume_section_by_default():
    prompt = build_system_prompt("TECHNICAL", 2)
    assert "Candidate Resume" not in prompt


def test_system_prompt_injects_resume():
    prompt = build_system_prompt(
        "TECHNICAL", 2, resume_text="Built a distributed cache in Go at Acme Corp."
    )
    assert "Candidate Resume" in prompt
    assert "distributed cache in Go" in prompt
    assert "cross-reference against the role's" in prompt


def test_conclude_check_prompt_contains_transcript():
    history = [{"question": "Explain hashing.", "answer": "It maps keys to buckets."}]
    prompt = build_conclude_check_prompt(history)
    assert "Explain hashing." in prompt
    assert "maps keys to buckets." in prompt


def test_closing_turn_prompt_has_no_further_questions_instruction():
    history = [{"question": "Q1", "answer": "A1"}]
    system_prompt, user_prompt = build_closing_turn_prompt("TECHNICAL", history)
    assert "Do not ask any further questions" in system_prompt
    assert "TECHNICAL" in system_prompt
    assert "Q1" in user_prompt
    assert "A1" in user_prompt
    assert user_prompt.strip().endswith("Interviewer (closing statement):")


def test_user_prompt_turn_zero():
    prompt = build_user_prompt([], 0)
    assert "introduction" in prompt.lower()
    assert "first question" in prompt.lower()


def test_user_prompt_formats_history():
    history = [
        {"question": "What is Python?", "answer": "A high-level language."},
        {"question": "What is a list?", "answer": "An ordered mutable sequence."},
    ]
    prompt = build_user_prompt(history, 2)
    assert "What is Python?" in prompt
    assert "A high-level language." in prompt
    assert "What is a list?" in prompt
    assert prompt.strip().endswith("Interviewer:")


# ---------------------------------------------------------------------------
# evaluator.py
# ---------------------------------------------------------------------------

def test_eval_prompt_contains_question_and_answer():
    prompt = build_eval_prompt("What is a linked list?", "A node-based linear structure.")
    assert "What is a linked list?" in prompt
    assert "A node-based linear structure." in prompt


# ---------------------------------------------------------------------------
# closing.py
# ---------------------------------------------------------------------------

def test_closing_prompt_contains_full_transcript():
    turns = [
        {"question": "Q1?", "answer": "A1."},
        {"question": "Q2?", "answer": "A2."},
    ]
    prompt = build_closing_prompt(turns, 7.5, "TECHNICAL")
    assert "Q1?" in prompt
    assert "A1." in prompt
    assert "Q2?" in prompt
    assert "7.5" in prompt
    assert "TECHNICAL" in prompt
    assert "Total Turns: 2" in prompt


def test_closing_prompt_avg_score_formatting():
    turns = [{"question": "Q?", "answer": "A."}]
    prompt = build_closing_prompt(turns, 8.333, "HR")
    assert "8.3" in prompt
