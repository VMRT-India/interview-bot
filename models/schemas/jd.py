from pydantic import BaseModel


class JDParsed(BaseModel):
    role_title: str
    company_name: str | None = None
    seniority: str | None = None
    required_skills: list[str] = []
    preferred_skills: list[str] = []
    tech_stack: list[str] = []
    interview_focus: list[str] = []
    domain: str = "TECHNICAL"
    estimated_duration_minutes: int | None = None
