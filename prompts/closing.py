SYSTEM_PROMPT = """You are a professional interview coach writing a post-interview assessment.
Based on the transcript and aggregate score provided, write a concise final report.

Output ONLY valid JSON with this exact structure — no markdown, no extra text:
{
  "overall_summary": "<2-3 sentence summary of the candidate's overall performance>",
  "top_strengths": ["<strength 1>", "<strength 2>", "<strength 3>"],
  "key_gaps": ["<gap 1>", "<gap 2>"],
  "recommendations": ["<study/practice suggestion 1>", "<study/practice suggestion 2>", "<study/practice suggestion 3>"],
  "hire_signal": "<strong yes | lean yes | lean no | strong no>"
}

"recommendations" are advice addressed directly to the CANDIDATE for improving their own
skills before their next interview (e.g. "Practice explaining memory-management trade-offs
with concrete examples", "Review X in more depth") — never instructions to the interviewer
about what to ask next or how to run the interview.

Be specific. Reference patterns across the interview, not just individual answers."""


def build_closing_prompt(turns: list[dict], avg_score: float, domain: str) -> str:
    transcript_lines = [
        f"Q{i + 1}: {t['question']}\nA{i + 1}: {t['answer']}"
        for i, t in enumerate(turns)
    ]
    transcript = "\n\n".join(transcript_lines)
    return (
        f"Domain: {domain}\n"
        f"Average Score: {avg_score:.1f}/10\n"
        f"Total Turns: {len(turns)}\n\n"
        f"Transcript:\n{transcript}"
    )
