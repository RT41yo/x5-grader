from pydantic import BaseModel, Field
from typing import List, Optional


class CriterionScore(BaseModel):
    name: str
    score: float
    evidence: Optional[str] = None


class SkillScore(BaseModel):
    name: str
    skill_score: float
    criteria: List[CriterionScore]
    rationale: Optional[str] = None
    improvement_plan: List[str] = []


class EvaluationResponse(BaseModel):
    overall_score: float
    skills: List[SkillScore]
    keyword_coverage: Optional[float] = None
    highlights: Optional[dict] = None


# Для API
class SubmitSolutionRequest(BaseModel):
    user_id: str
    case_id: str
    answer_text: str


class AskRequest(BaseModel):
    session_id: str
    question: str
