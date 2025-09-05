from typing import Optional, Dict, Any
from sqlalchemy import select

from app.db import db
from app.models import Case, Solution, Session, Evaluation


# --- CASES ---

def get_case(case_id: str) -> Optional[Case]:
    return db.session.get(Case, case_id)


def create_case(title: str, description: str, best_answer: str, skills_json: Any) -> Case:
    case = Case(title=title, description=description, best_answer=best_answer, skills_json=skills_json or [])
    db.session.add(case)
    db.session.commit()
    return case


# --- SOLUTIONS & SESSIONS ---

def create_solution_and_session(case_id: str, user_id: str, answer_text: str) -> tuple[Solution, Session]:
    solution = Solution(case_id=case_id, user_id=user_id, answer_text=answer_text)
    session = Session(case_id=case_id, user_id=user_id)
    db.session.add(solution)
    db.session.add(session)
    db.session.commit()
    return solution, session


def get_solution_by_case_and_user(case_id: str, user_id: str) -> Optional[Solution]:
    stmt = select(Solution).where(Solution.case_id == case_id, Solution.user_id == user_id).order_by(Solution.submitted_at.desc())
    return db.session.execute(stmt).scalars().first()


# --- EVALUATIONS ---

def save_evaluation(session_id: str, overall_score: float | None, raw_json: Dict[str, Any]) -> Evaluation:
    evaluation = Evaluation(session_id=session_id, overall_score=overall_score, raw_json=raw_json)
    db.session.add(evaluation)
    db.session.commit()
    return evaluation


def get_evaluation_by_session(session_id: str) -> Optional[Evaluation]:
    stmt = select(Evaluation).where(Evaluation.session_id == session_id).order_by(Evaluation.created_at.desc())
    return db.session.execute(stmt).scalars().first()
