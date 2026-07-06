def build_system_prompt(
    domain: str,
    difficulty: int,
    jd_text: str | None = None,
    context: list[str] | None = None,
    resume_text: str | None = None,
) -> str:
    jd_section = (
        f"\n\nRole Context:\n{jd_text}\n\n"
        "Align every question to this specific role, company, and required skills. "
        "Prioritize topics listed under Interview Focus and Required Skills."
    ) if jd_text else ""
    resume_section = (
        f"\n\nCandidate Resume:\n{resume_text}\n\n"
        "Probe the candidate's actual listed projects and experience above — ask about specific "
        "things they claim to have built or done, and cross-reference against the role's "
        "requirements to identify real skill gaps, not just generic questions."
    ) if resume_text else ""
    context_section = (
        "\n\nRelevant Knowledge Base Context (use to ground your questions — do not quote verbatim):\n"
        + "\n---\n".join(context)
        if context
        else ""
    )
    return f"""You are a senior {domain} interviewer conducting a structured one-on-one interview.
Difficulty level: {difficulty}/5.{jd_section}{resume_section}{context_section}

Rules:
- Ask exactly ONE question per turn. Never ask multiple questions at once.
- Adapt difficulty based on the candidate's prior answers.
- Use follow-up questions to probe deeper when an answer is shallow or vague.
- Occasionally apply realistic pressure: challenge an answer, ask "are you sure?", or push for specifics.
- Never repeat a question already asked in this session.
- Do not provide hints, answers, or explanations.
- Keep questions concise and specific.
- Output ONLY the question text. No preamble, no labels, no explanation."""


def build_user_prompt(history: list[dict], turn: int) -> str:
    if turn == 0:
        return (
            "Begin with a brief professional introduction (1-2 sentences), "
            "then ask your first question."
        )
    lines = []
    for h in history:
        lines.append(f"Interviewer: {h['question']}")
        lines.append(f"Candidate: {h['answer']}")
    lines.append("Interviewer:")
    return "\n".join(lines)


CONCLUDE_CHECK_SYSTEM = (
    "You are assessing whether an ongoing interview has gathered enough signal to conclude. "
    'Return ONLY JSON: {"conclude": true or false}. '
    "Conclude only if you have a confident read on the candidate's ability across the areas "
    "covered so far — depth of knowledge, problem-solving, and communication. If answers have "
    "been shallow, inconsistent, or key areas are unexplored, continue."
)


def build_conclude_check_prompt(history: list[dict]) -> str:
    lines = [
        f"Q{i + 1}: {h['question']}\nA{i + 1}: {h['answer']}" for i, h in enumerate(history)
    ]
    transcript = "\n\n".join(lines)
    return (
        "The interview has reached its target time. Based on the transcript so far, should it "
        f"conclude now?\n\nTranscript:\n{transcript}"
    )


def build_closing_turn_prompt(domain: str, history: list[dict]) -> tuple[str, str]:
    """Returns (system_prompt, user_prompt) for the final, unscored sign-off turn — a real
    in-character message, not a raw system notice, per the requirement that the interview
    never end abruptly."""
    system_prompt = f"""You are a senior {domain} interviewer wrapping up a one-on-one interview.
Deliver ONE short, warm, professional closing statement to the candidate:
- Thank them for their time.
- Briefly and genuinely acknowledge the conversation (no scores or verdicts — those come later).
- Mention they'll receive detailed feedback shortly.
Do not ask any further questions. Output ONLY the closing statement text — no labels, no preamble."""

    lines = [f"Interviewer: {h['question']}\nCandidate: {h['answer']}" for h in history]
    user_prompt = "\n\n".join(lines) + "\n\nInterviewer (closing statement):"
    return system_prompt, user_prompt
