from abc import ABC, abstractmethod

import structlog

from config import settings
from models.schemas.jd import JDParsed
from services.company_lookup_service import company_lookup_service
from services.json_utils import extract_json as _extract_json
from services.json_utils import extract_json_array as _extract_json_array
from services.llm_service import llm_service

logger = structlog.get_logger()

_PARSE_SYSTEM = (
    "You are a job description parser. Extract structured fields from the given text. "
    "Return ONLY valid JSON with no preamble or explanation."
)

_GEN_SYSTEM = (
    "You are an interview knowledge base builder. Generate targeted technical interview Q&A pairs. "
    "Return ONLY a valid JSON object with a single key 'questions' whose value is an array. "
    "No preamble, no explanation, no markdown."
)


def _build_parse_prompt(jd_text: str) -> str:
    return f"""Extract the following fields from this job description.
Return a single JSON object with exactly these keys:
- role_title: job title (string)
- company_name: company name or null
- seniority: one of "junior", "mid", "senior", "lead", "staff", "principal" or null
- required_skills: required technical and soft skills (array of strings)
- preferred_skills: nice-to-have skills (array of strings)
- tech_stack: specific technologies, languages, frameworks mentioned (array of strings)
- interview_focus: topics likely to be covered in the interview (array of strings)
- domain: primary domain — one of "TECHNICAL", "BEHAVIORAL", "HR"
- estimated_duration_minutes: integer if the JD explicitly states an interview length
  (e.g. "45-minute interview", "1 hour technical screen"), else null — do not guess

Job Description:
{jd_text}"""


def _build_gen_prompt(
    jd_parsed: JDParsed, count: int, company_context: list[str] | None = None
) -> str:
    required = ", ".join(jd_parsed.required_skills[:15]) or "not specified"
    preferred = ", ".join(jd_parsed.preferred_skills[:10]) or "none"
    stack = ", ".join(jd_parsed.tech_stack[:15]) or "not specified"
    focus = ", ".join(jd_parsed.interview_focus[:8]) if jd_parsed.interview_focus else required
    seniority = jd_parsed.seniority or "mid"
    company = jd_parsed.company_name or "the company"

    company_section = ""
    if company_context:
        joined = "\n".join(f"- {c}" for c in company_context)
        company_section = f"""

Real signals about {company}'s actual interview process (from web search):
{joined}
Align question format/style/rounds with these signals where relevant."""

    return f"""Generate {count} interview Q&A pairs for this role.

Role: {jd_parsed.role_title}
Company: {company}
Seniority: {seniority}
Required Skills (must-have — weight these heavier): {required}
Preferred Skills (nice-to-have — lighter weight): {preferred}
Tech Stack: {stack}
Interview Focus: {focus}{company_section}

Skill-gap targeting instructions:
- Prioritize required skills over preferred skills — most questions should probe required skills.
- For each required skill, include at least one question that distinguishes genuine depth from
  surface-level/buzzword familiarity (e.g. asks for tradeoffs, edge cases, or "why" rather than "what").
- If a skill appears in both required_skills and tech_stack, treat it as highest priority.

Return a JSON object with this exact structure:
{{"questions": [
  {{"topic": "...", "question": "...", "ideal_answer": "...", "difficulty": 3}},
  ...
]}}

Each element must have:
- topic: specific topic area (string)
- question: the interview question (string)
- ideal_answer: a comprehensive model answer (string)
- difficulty: integer 1–5 appropriate for {seniority} level

Make questions specific to this role and {company}'s context."""


def _valid_doc(doc: object) -> bool:
    if not isinstance(doc, dict):
        return False
    return all(k in doc for k in ("topic", "question", "ideal_answer", "difficulty"))


class KnowledgeProvider(ABC):
    """Generates interview Q&A documents from parsed JD metadata.

    Implement this to swap in alternative knowledge sources (e.g. web search).
    """

    @abstractmethod
    async def generate(self, jd_parsed: JDParsed) -> list[dict]:
        """Return list of {topic, question, ideal_answer, difficulty} dicts."""


class LLMKnowledgeProvider(KnowledgeProvider):
    def __init__(self, llm_svc) -> None:
        self._llm = llm_svc

    async def generate(self, jd_parsed: JDParsed) -> list[dict]:
        all_skills = jd_parsed.required_skills + jd_parsed.tech_stack
        count = min(max(8, len(all_skills) * 2), 12)

        company_context: list[str] = []
        if jd_parsed.company_name:
            company_context = await company_lookup_service.search_interview_style(
                jd_parsed.company_name
            )

        prompt = _build_gen_prompt(jd_parsed, count, company_context)
        try:
            raw = await self._llm.generate(prompt, system_prompt=_GEN_SYSTEM, json_mode=True)
            obj = _extract_json(raw)
            docs = obj.get("questions", [])
            return [d for d in docs if _valid_doc(d)]
        except Exception as exc:
            logger.warning("jd_knowledge_gen_failed", error=str(exc))
            return []


class JDService:
    def __init__(self, llm_svc) -> None:
        self._llm = llm_svc

    async def parse_jd(self, jd_text: str) -> JDParsed:
        prompt = _build_parse_prompt(jd_text)
        raw = await self._llm.generate(prompt, system_prompt=_PARSE_SYSTEM, json_mode=True)
        data = _extract_json(raw)
        return JDParsed(**data)

    async def resolve_target_minutes(self, jd_parsed: JDParsed | None) -> int:
        """Resolution order: JD-stated duration -> Tavily-researched company/role typical
        duration -> configured default. Never raises — always returns a usable target."""
        if jd_parsed and jd_parsed.estimated_duration_minutes:
            return jd_parsed.estimated_duration_minutes

        if jd_parsed and jd_parsed.company_name:
            researched = await company_lookup_service.search_interview_duration(
                jd_parsed.company_name, jd_parsed.role_title
            )
            if researched:
                return researched

        return settings.default_interview_target_minutes


jd_service = JDService(llm_service)
knowledge_provider: KnowledgeProvider = LLMKnowledgeProvider(llm_service)
