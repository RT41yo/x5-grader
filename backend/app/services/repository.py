# backend/app/services/repository.py
from __future__ import annotations

from typing import Any, Dict, Optional, Tuple
from uuid import UUID

from sqlalchemy import select

from app.db import db
from app.models import Case, Solution, Session, Evaluation


# === CASES ===

def get_case(case_id: UUID | str) -> Optional[Case]:
    """
    Быстрый доступ к кейсу по id.
    """
    return db.session.get(Case, case_id)


def create_case(title: str, description: str, best_answer: str, skills_json: Any) -> Case:
    """
    Создание кейса. skills_json — уже разобранный объект (list/dict).
    """
    case = Case(
        title=title.strip(),
        description=description.strip(),
        best_answer=best_answer.strip(),
        skills_json=skills_json or [],
    )
    db.session.add(case)
    db.session.commit()
    return case


# === SOLUTIONS & SESSIONS ===

def create_solution_and_session(case_id: UUID | str, user_id: str, answer_text: str) -> Tuple[Solution, Session]:
    """
    Создаёт Solution и Session одной транзакцией и СВЯЗЫВАЕТ solution.session_id.
    Возвращает пары (solution, session).
    """
    solution = Solution(case_id=case_id, user_id=user_id, answer_text=answer_text)
    session = Session(case_id=case_id, user_id=user_id)
    db.session.add_all([solution, session])
    db.session.flush()  # получаем session.id
    solution.session_id = session.id
    db.session.commit()
    return solution, session


def get_solution_by_session(session_id: UUID | str) -> Optional[Solution]:
    """
    Находит Solution, привязанный к данной сессии.
    """
    stmt = select(Solution).where(Solution.session_id == session_id)
    return db.session.execute(stmt).scalars().first()


def get_last_solution_by_case_and_user(case_id: UUID | str, user_id: str) -> Optional[Solution]:
    """
    Фоллбек на случай старых данных, где session_id у Solution не заполнен.
    Берёт последнюю попытку пользователя по кейсу.
    """
    stmt = (
        select(Solution)
        .where(Solution.case_id == case_id, Solution.user_id == user_id)
        .order_by(Solution.submitted_at.desc())
    )
    return db.session.execute(stmt).scalars().first()


# === EVALUATIONS ===

def save_evaluation(session_id: UUID | str, overall_score: Optional[float], raw_json: Dict[str, Any]) -> Evaluation:
    """
    Сохраняет Evaluation для указанной сессии.
    """
    evaluation = Evaluation(session_id=session_id, overall_score=overall_score, raw_json=raw_json)
    db.session.add(evaluation)
    db.session.commit()
    return evaluation


def get_evaluation_by_session(session_id: UUID | str) -> Optional[Evaluation]:
    """
    Возвращает последнюю Evaluation по session_id (если их несколько).
    """
    stmt = (
        select(Evaluation)
        .where(Evaluation.session_id == session_id)
        .order_by(Evaluation.created_at.desc())
    )
    return db.session.execute(stmt).scalars().first()
