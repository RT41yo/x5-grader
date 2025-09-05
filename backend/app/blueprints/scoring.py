from flask import Blueprint, request, jsonify
from app.db import db
from app.models import Solution, Session, Evaluation, Case
from app.schemas import SubmitSolutionRequest
from app.services.langflow_client import run_flow_evaluate

scoring_bp = Blueprint("scoring", __name__)


@scoring_bp.route("/submit_solution", methods=["POST"])
def submit_solution():
    """Приём ответа пользователя, вызов Langflow Flow A"""
    data = request.get_json()
    req = SubmitSolutionRequest(**data)

    # Сохраняем решение и сессию
    solution = Solution(case_id=req.case_id, user_id=req.user_id, answer_text=req.answer_text)
    session = Session(case_id=req.case_id, user_id=req.user_id)

    db.session.add(solution)
    db.session.add(session)
    db.session.commit()

    # Получаем кейс
    case = Case.query.get(req.case_id)
    if not case:
        return jsonify({"error": "Case not found"}), 404

    # Вызываем Langflow Flow A
    evaluation_json = run_flow_evaluate(case, req.answer_text)

    # Сохраняем результат
    evaluation = Evaluation(session_id=session.id, overall_score=evaluation_json.get("overall_score"), raw_json=evaluation_json)
    db.session.add(evaluation)
    db.session.commit()

    return jsonify({"session_id": str(session.id), "evaluation": evaluation_json})


@scoring_bp.route("/result/<session_id>", methods=["GET"])
def get_result(session_id):
    """Получение сохранённого результата по session_id"""
    evaluation = Evaluation.query.filter_by(session_id=session_id).first()
    if not evaluation:
        return jsonify({"error": "Evaluation not found"}), 404
    return jsonify(evaluation.raw_json)
