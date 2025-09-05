from typing import Any, Dict
from pydantic import ValidationError

from app.schemas import EvaluationResponse


def validate_evaluation_json(data: Dict[str, Any]) -> tuple[bool, str]:
    """
    Проверка JSON, полученного от Langflow (Flow A).
    Возвращает (ok, message).
    """
    try:
        EvaluationResponse.model_validate(data)
        return True, "valid"
    except ValidationError as e:
        return False, str(e)
