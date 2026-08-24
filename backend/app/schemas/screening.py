from pydantic import BaseModel, Field


class ScreeningRequest(BaseModel):
    resume_id: int
    job_id: int


class ScreeningResult(BaseModel):
    overall_score: int = Field(ge=0, le=100)
    recommendation: str
    summary: str

    matched_skills: list[str]
    missing_skills: list[str]

    relevant_experience: list[str]
    strengths: list[str]
    gaps: list[str]