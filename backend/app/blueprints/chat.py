from flask import Blueprint, request, jsonify
from app.models import Evaluation, Case, Solution, Session
from app.schemas import AskRequest
from app.services.langflow_client import run_flow_explain

chat_bp = Blueprint("chat", __name__)


@chat_bp.route("/ask", methods=["POST"])
def ask_question():
    """Задаём уточняющий вопрос (Flow B)"""
    data = request.get_json()
    req = AskRequest(**data)

    evaluation = Evaluation.query.filter_by(session_id=req.session_id).first()
    session = Session.query.get(req.session_id)
    if not evaluation or not session:
        return jsonify({"error": "Session or evaluation not found"}), 404

    case = Case.query.get(session.case_id)
    solution = Solution.query.filter_by(case_id=case.id, user_id=session.user_id).first()

    # Вызов Langflow Flow B
    answer = run_flow_explain(case, solution, evaluation.raw_json, req.question)

    return jsonify({"answer": answer})
