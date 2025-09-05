# backend/app/blueprints/scoring.py
from __future__ import annotations

import json
import logging
import time
import uuid
from typing import Any, Dict, Optional

from flask import Blueprint, jsonify, request
from pydantic import ValidationError

from app.db import db
from app.models import Case, Evaluation, Session, Solution
from app.schemas import SubmitSolutionRequest
from app.services.langflow_client import run_flow_evaluate

log = logging.getLogger(__name__)

scoring_bp = Blueprint("scoring", __name__)


def _parse_uuid(maybe_uuid: str) -> Optional[uuid.UUID]:
    try:
        return uuid.UUID(str(maybe_uuid))
    except Exception:
        return None


@scoring_bp.route("/submit_solution", methods=["POST"])
def submit_solution():
    """
    Приём ответа пользователя:
      1) валидируем вход (Pydantic),
      2) создаём Solution и Session,
      3) вызываем Langflow (Flow A),
      4) сохраняем Evaluation,
      5) возвращаем session_id и нормализованный evaluation JSON.
    """
    if not request.is_json:
        return jsonify({"error": "Expected application/json"}), 415

    try:
        data = request.get_json(force=True, silent=False)
        req = SubmitSolutionRequest(**data)
    except ValidationError as ve:
        return jsonify({"error": "ValidationError", "details": ve.errors()}), 400
    except Exception:
        return jsonify({"error": "Invalid JSON"}), 400

    # Проверяем существование кейса заранее
    case = Case.query.get(req.case_id)
    if not case:
        return jsonify({"error": "Case not found"}), 404

    try:
        start_total = time.perf_counter()

        # 1) создаём solution + session
        solution = Solution(case_id=req.case_id, user_id=req.user_id, answer_text=req.answer_text)
        session = Session(case_id=req.case_id, user_id=req.user_id)
        db.session.add_all([solution, session])
        db.session.flush()  # получаем UUID-ы

        # 2) оцениваем через Langflow
        start_eval = time.perf_counter()
        evaluation_json = run_flow_evaluate(case, req.answer_text)
        latency_ms = int((time.perf_counter() - start_eval) * 1000)

        if not isinstance(evaluation_json, dict):
            evaluation_json = {"raw": str(evaluation_json)}

        # 3) ВШИВАЕМ КОНТЕКСТ В EVALUATION: гарантируем последующие обращения к ТОЧНОМУ solution
        ctx = evaluation_json.get("context")
        if not isinstance(ctx, dict):
            ctx = {}
            evaluation_json["context"] = ctx
        ctx.update({
            "session_id": str(session.id),
            "solution_id": str(solution.id),
            "case_id": str(req.case_id),
            "user_id": req.user_id,
        })
        evaluation_json.setdefault("meta", {})["latency_ms"] = latency_ms

        # 4) сохраняем Evaluation
        overall_score = None
        try:
            oscore = evaluation_json.get("overall_score")
            if isinstance(oscore, (int, float)):
                overall_score = float(oscore)
        except Exception:
            overall_score = None

        evaluation = Evaluation(
            session_id=session.id,
            overall_score=overall_score,
            raw_json=evaluation_json,
        )
        db.session.add(evaluation)
        db.session.commit()

        total_ms = int((time.perf_counter() - start_total) * 1000)
        log.info(
            "submit_solution: session=%s case=%s user=%s latency_ms(flow=%s,total=%s)",
            session.id, req.case_id, req.user_id, latency_ms, total_ms,
        )

        return jsonify({
            "session_id": str(session.id),
            "evaluation": evaluation_json,
            "meta": {"latency_ms": latency_ms},
        }), 201

    except Exception as e:
        log.exception("submit_solution failed: %s", e)
        db.session.rollback()
        return jsonify({"error": "Evaluation failed", "details": str(e)}), 502


@scoring_bp.route("/result/<session_id>", methods=["GET"])
def get_result(session_id: str):
    """Возвращает сохранённый JSON результата по session_id."""
    sid = _parse_uuid(session_id) or session_id
    evaluation = Evaluation.query.filter_by(session_id=sid).order_by(Evaluation.created_at.desc()).first()
    if not evaluation:
        return jsonify({"error": "Evaluation not found"}), 404

    try:
        if isinstance(evaluation.raw_json, str):
            return jsonify({"raw": evaluation.raw_json})
        return jsonify(evaluation.raw_json)
    except Exception as e:
        log.exception("get_result: failed to serialize JSON for session=%s: %s", session_id, e)
        try:
            return jsonify({"raw": json.dumps(evaluation.raw_json, ensure_ascii=False)})
        except Exception:
            return jsonify({"error": "Corrupted evaluation payload"}), 500
