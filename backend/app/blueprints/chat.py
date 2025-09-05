# backend/app/blueprints/chat.py
from __future__ import annotations

import logging
import uuid
from typing import Optional

from flask import Blueprint, jsonify, request
from pydantic import ValidationError

from app.models import Evaluation, Case, Solution, Session
from app.schemas import AskRequest
from app.services.langflow_client import run_flow_explain

log = logging.getLogger(__name__)

chat_bp = Blueprint("chat", __name__)


def _parse_uuid(maybe_uuid: str) -> Optional[uuid.UUID]:
    try:
        return uuid.UUID(str(maybe_uuid))
    except Exception:
        return None


@chat_bp.route("/ask", methods=["POST"])
def ask_question():
    """
    Уточняющий вопрос по уже выполненной оценке (Flow B).
    Требует существующую session_id.
    """
    if not request.is_json:
        return jsonify({"error": "Expected application/json"}), 415

    try:
        data = request.get_json(force=True, silent=False)
        req = AskRequest(**data)
    except ValidationError as ve:
        return jsonify({"error": "ValidationError", "details": ve.errors()}), 400
    except Exception:
        return jsonify({"error": "Invalid JSON"}), 400

    sid = _parse_uuid(str(req.session_id)) or str(req.session_id)

    # 1) Оценка
    evaluation = (
        Evaluation.query.filter_by(session_id=sid)
        .order_by(Evaluation.created_at.desc())
        .first()
    )
    if not evaluation:
        return jsonify({"error": "Evaluation not found"}), 404

    # 2) Сессия и кейс
    session = Session.query.get(sid)
    if not session:
        return jsonify({"error": "Session not found"}), 404

    case = Case.query.get(session.case_id)
    if not case:
        return jsonify({"error": "Case not found"}), 404

    # 3) Ищем solution ТОЧНО этой попытки: берём solution_id из evaluation.raw_json.context
    solution = None
    try:
        ctx = evaluation.raw_json.get("context") if isinstance(evaluation.raw_json, dict) else None
        sol_id = (ctx or {}).get("solution_id")
        if sol_id:
            solution = Solution.query.get(sol_id)
    except Exception:
        solution = None

    # 4) Фоллбек на случай старых записей без контекста: последняя попытка по case+user
    if not solution:
        solution = (
            Solution.query
            .filter_by(case_id=session.case_id, user_id=session.user_id)
            .order_by(Solution.submitted_at.desc())
            .first()
        )
    if not solution:
        return jsonify({"error": "Solution not found"}), 404

    # 5) Вызываем Flow B (или даём заглушку, если FLOW_ID_EXPLAIN пуст)
    try:
        answer = run_flow_explain(
            case=case,
            solution=solution,
            evaluation_json=evaluation.raw_json,
            question=req.question.strip(),
        )
        if not isinstance(answer, str) or not answer.strip():
            answer = "Пустой ответ от AI."
        return jsonify({"answer": answer})
    except Exception as e:
        log.exception("ask_question failed for session=%s: %s", sid, e)
        return jsonify({"error": "Explain flow failed", "details": str(e)}), 502
