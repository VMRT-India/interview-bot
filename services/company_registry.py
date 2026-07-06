"""Fixed registry of pre-generatable company archetypes (Phase 7).

Used by scripts/generate_company_kb.py to synthesize a role archetype per company
(instead of waiting on a real user-submitted JD), and by services/rag_service.py to
match a live session's parsed company_name against a pre-generated knowledge base.

Quant/finance content is intentionally kept under domain="TECHNICAL" with topic tags
rather than a new interview_type — see TODO.md for why.
"""
import re

from models.schemas.jd import JDParsed

COMPANY_ARCHETYPES: dict[str, JDParsed] = {
    "meta": JDParsed(
        role_title="Software Engineer",
        company_name="Meta",
        seniority="mid",
        required_skills=["data structures & algorithms", "system design", "distributed systems"],
        tech_stack=["React", "GraphQL", "PyTorch"],
        interview_focus=["coding", "system design", "behavioral"],
        domain="TECHNICAL",
    ),
    "amazon": JDParsed(
        role_title="Software Development Engineer",
        company_name="Amazon",
        seniority="mid",
        required_skills=["data structures & algorithms", "distributed systems", "object-oriented design"],
        tech_stack=["AWS", "Java", "DynamoDB"],
        interview_focus=["coding", "system design", "leadership principles behavioral"],
        domain="TECHNICAL",
    ),
    "apple": JDParsed(
        role_title="Software Engineer",
        company_name="Apple",
        seniority="mid",
        required_skills=["data structures & algorithms", "systems programming", "concurrency"],
        tech_stack=["Swift", "C++", "iOS"],
        interview_focus=["coding", "system design", "product sense"],
        domain="TECHNICAL",
    ),
    "netflix": JDParsed(
        role_title="Senior Software Engineer",
        company_name="Netflix",
        seniority="senior",
        required_skills=["distributed systems", "microservices", "JVM internals"],
        tech_stack=["Java", "Kafka", "AWS"],
        interview_focus=["system design", "coding", "culture fit"],
        domain="TECHNICAL",
    ),
    "google": JDParsed(
        role_title="Software Engineer",
        company_name="Google",
        seniority="mid",
        required_skills=["data structures & algorithms", "system design", "googleyness"],
        tech_stack=["C++", "Java", "Go"],
        interview_focus=["coding", "system design", "googleyness & leadership"],
        domain="TECHNICAL",
    ),
    "janestreet": JDParsed(
        role_title="Quantitative Trader",
        company_name="Jane Street",
        seniority="mid",
        required_skills=["probability", "mental math", "market intuition"],
        tech_stack=["OCaml"],
        interview_focus=["probability puzzles", "mental math", "trading games", "market making"],
        domain="TECHNICAL",
    ),
    "hrt": JDParsed(
        role_title="Quantitative Researcher",
        company_name="Hudson River Trading",
        seniority="mid",
        required_skills=["statistics", "algorithms", "probability"],
        tech_stack=["C++", "Python"],
        interview_focus=["probability", "statistics", "algorithms", "market microstructure"],
        domain="TECHNICAL",
    ),
    "citadel": JDParsed(
        role_title="Quantitative Researcher",
        company_name="Citadel",
        seniority="mid",
        required_skills=["statistics", "machine learning", "probability", "linear algebra"],
        tech_stack=["Python", "C++"],
        interview_focus=["probability", "statistics", "brainteasers", "coding"],
        domain="TECHNICAL",
    ),
    "jpmorganchase": JDParsed(
        role_title="Software Engineer",
        company_name="JPMorgan Chase",
        seniority="mid",
        required_skills=["Java", "distributed systems", "data structures & algorithms"],
        tech_stack=["Java", "Spring", "Kafka"],
        interview_focus=["coding", "system design", "behavioral"],
        domain="TECHNICAL",
    ),
    "barclays": JDParsed(
        role_title="Technology Analyst",
        company_name="Barclays",
        seniority="junior",
        required_skills=["Java", "SQL", "object-oriented programming"],
        tech_stack=["Java", "SQL"],
        interview_focus=["coding", "OOP fundamentals", "behavioral"],
        domain="TECHNICAL",
    ),
    "hsbc": JDParsed(
        role_title="Software Engineer",
        company_name="HSBC",
        seniority="mid",
        required_skills=["Java", "distributed systems", "SQL"],
        tech_stack=["Java", "SQL", "Kafka"],
        interview_focus=["coding", "system design", "behavioral"],
        domain="TECHNICAL",
    ),
}

# Aliases that normalize to a registry key, for common alternate spellings/names
_ALIASES: dict[str, str] = {
    "hudsonrivertrading": "hrt",
    "jpmorgan": "jpmorganchase",
    "jpmorganchaseco": "jpmorganchase",
    "chase": "jpmorganchase",
    "janestreetcapital": "janestreet",
}


def _normalize(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def resolve_company_slug(company_name: str | None) -> str | None:
    """Returns the registry key for company_name if it matches a known pre-generated
    company (via direct match or alias), else None."""
    if not company_name:
        return None
    key = _normalize(company_name)
    if key in COMPANY_ARCHETYPES:
        return key
    return _ALIASES.get(key)
