from flask import Blueprint, request, jsonify
from app.db import db
from app.models import Case

admin_bp = Blueprint("admin", __name__)


@admin_bp.route("/cases", methods=["POST"])
def create_case():
    """Создание нового кейса"""
    data = request.get_json()
    case = Case(
        title=data["title"],
        description=data["description"],
        best_answer=data["best_answer"],
        skills_json=data.get("skills_json", []),
    )
    db.session.add(case)
    db.session.commit()
    return jsonify({"id": str(case.id)}), 201


@admin_bp.route("/cases", methods=["GET"])
def list_cases():
    """Список всех кейсов"""
    cases = Case.query.all()
    return jsonify(
        [
            {
                "id": str(c.id),
                "title": c.title,
                "description": c.description,
                "best_answer": c.best_answer,
                "skills_json": c.skills_json,
            }
            for c in cases
        ]
    )


@admin_bp.route("/cases/<case_id>", methods=["GET"])
def get_case(case_id):
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
def update_case(case_id):
    case = Case.query.get(case_id)
    if not case:
        return jsonify({"error": "Case not found"}), 404
    data = request.get_json()
    case.title = data.get("title", case.title)
    case.description = data.get("description", case.description)
    case.best_answer = data.get("best_answer", case.best_answer)
    case.skills_json = data.get("skills_json", case.skills_json)
    db.session.commit()
    return jsonify({"status": "updated"})


@admin_bp.route("/cases/<case_id>", methods=["DELETE"])
def delete_case(case_id):
    case = Case.query.get(case_id)
    if not case:
        return jsonify({"error": "Case not found"}), 404
    db.session.delete(case)
    db.session.commit()
    return jsonify({"status": "deleted"})
