# backend/app/blueprints/admin.py
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from flask import Blueprint, jsonify, request

from app.db import db
from app.models import Case

log = logging.getLogger(__name__)

admin_bp = Blueprint("admin", __name__)


def _ensure_json_request() -> Optional[Dict[str, Any]]:
    if not request.is_json:
        return None
    try:
        return request.get_json(force=True, silent=False)
    except Exception:
        return None


def _parse_skills_json(raw: Any) -> List[Dict[str, Any]]:
    """
    Принимает уже-объект или строку JSON, возвращает список навыков.
    На этапе MVP не валидация схемы, а только безопасный разбор.
    """
    if raw is None or raw == "":
        return []
    if isinstance(raw, (list, dict)):
        # допускаем, что пришёл сразу объект
        return raw if isinstance(raw, list) else [raw]
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, list) else [parsed]
        except Exception:
            raise ValueError("Поле 'skills_json' должно быть валидным JSON.")
    raise ValueError("Поле 'skills_json' должно быть массивом или строкой JSON.")


def _qint(name: str, default: int, min_v: int = 0, max_v: int = 1000) -> int:
    try:
        v = int(request.args.get(name, default))
        return max(min_v, min(max_v, v))
    except Exception:
        return default


@admin_bp.route("/cases", methods=["POST"])
def create_case():
    """
    Создание нового кейса.
    Обязательные поля: title, description, best_answer.
    Необязательное: skills_json (list или строка JSON).
    """
    payload = _ensure_json_request()
    if payload is None:
        return jsonify({"error": "Expected application/json"}), 415

    title = (payload.get("title") or "").strip()
    description = (payload.get("description") or "").strip()
    best_answer = (payload.get("best_answer") or "").strip()
    skills_raw = payload.get("skills_json", [])

    if not title or not description or not best_answer:
        return (
            jsonify(
                {
                    "error": "ValidationError",
                    "details": "Поля 'title', 'description', 'best_answer' обязательны.",
                }
            ),
            400,
        )

    try:
        skills_json = _parse_skills_json(skills_raw)
    except ValueError as ve:
        return jsonify({"error": "ValidationError", "details": str(ve)}), 400

    case = Case(
        title=title,
        description=description,
        best_answer=best_answer,
        skills_json=skills_json,
    )
    db.session.add(case)
    db.session.commit()

    return jsonify({"id": str(case.id)}), 201


@admin_bp.route("/cases", methods=["GET"])
def list_cases():
    """
    Список кейсов с простой пагинацией: ?limit=...&offset=...
    По умолчанию: limit=50, offset=0
    """
    limit = _qint("limit", 50, 1, 200)
    offset = _qint("offset", 0, 0, 10000)

    q = Case.query.order_by(Case.title.asc())
    items = q.limit(limit).offset(offset).all()

    # Для демо — без total-count (дорого на больших данных)
    return jsonify(
        [
            {
                "id": str(c.id),
                "title": c.title,
                "description": c.description,
                "best_answer": c.best_answer,
                "skills_json": c.skills_json,
            }
            for c in items
        ]
    )


@admin_bp.route("/cases/<case_id>", methods=["GET"])
def get_case(case_id: str):
    case = Case.query.get(case_id)
    if not case:
        return jsonify({"error": "Case not found"}), 404
    return jsonify(
        {
            "id": str(case.id),
            "title": case.title,
            "description": case.description,
            "best_answer": case.best_answer,
            "skills_json": case.skills_json,
        }
    )


@admin_bp.route("/cases/<case_id>", methods=["PUT"])
def update_case(case_id: str):
    case = Case.query.get(case_id)
    if not case:
        return jsonify({"error": "Case not found"}), 404

    payload = _ensure_json_request()
    if payload is None:
        return jsonify({"error": "Expected application/json"}), 415

    title = payload.get("title")
    description = payload.get("description")
    best_answer = payload.get("best_answer")
    skills_raw = payload.get("skills_json", None)

    if title is not None:
        case.title = title.strip()
    if description is not None:
        case.description = description.strip()
    if best_answer is not None:
        case.best_answer = best_answer.strip()

    if skills_raw is not None:
        try:
            case.skills_json = _parse_skills_json(skills_raw)
        except ValueError as ve:
            return jsonify({"error": "ValidationError", "details": str(ve)}), 400

    db.session.commit()
    return jsonify({"status": "updated"})


@admin_bp.route("/cases/<case_id>", methods=["DELETE"])
def delete_case(case_id: str):
    case = Case.query.get(case_id)
    if not case:
        return jsonify({"error": "Case not found"}), 404
    db.session.delete(case)
    db.session.commit()
    return jsonify({"status": "deleted"})
