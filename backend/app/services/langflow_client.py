import json
from typing import Any, Dict, Optional

import httpx
from pydantic import ValidationError

from app.config import get_settings
from app.schemas import EvaluationResponse


# Имена/ID flow — можно переопределить через .env при желании
EVALUATE_FLOW_ID = "EvaluateCase"
EXPLAIN_FLOW_ID = "ExplainEvaluation"


def _extract_output(payload: Dict[str, Any]) -> Any:
    """
    Универсальный парсер ответа Langflow /run.
    Пытается вытащить либо JSON (для Evaluate), либо текст (для Explain).
    Формат у Langflow может отличаться в зависимости от нод, поэтому парсим мягко.
    """
    # 1) Популярный вариант: payload["outputs"][0]["outputs"][0]["results"]["json"/"text"]
    try:
        outputs = payload.get("outputs", [])
        if outputs:
            inner_outputs = outputs[0].get("outputs", [])
            if inner_outputs:
                results = inner_outputs[0].get("results", {})
                # json-ответ
                if "json" in results:
                    return results["json"]
                # текстовый ответ
                if "text" in results:
                    return results["text"]
                # Иногда кладут в "data"
                if "data" in results:
                    return results["data"]
    except Exception:
        pass

    # 2) Бывает, что нода напрямую возвращает "data" на верхнем уровне
    if "data" in payload:
        return payload["data"]

    # 3) В крайнем случае — возвращаем исходный payload, пусть вызывающий код решает
    return payload


def _run_flow(flow_id: str, tweaks: Dict[str, Any], output_type: str) -> Any:
    settings = get_settings()
    url = f"{settings.langflow_url}/api/v1/run/{flow_id}?stream=false"

    body = {
        "input_value": "",
        "input_type": "input",
        "output_type": output_type,  # "json" или "text"
        "tweaks": tweaks,
    }

    # Таймауты и пара ретраев на случай сетевых глюков
    timeout = httpx.Timeout(connect=5.0, read=30.0, write=10.0, pool=5.0)
    for attempt in range(2):
        try:
            with httpx.Client(timeout=timeout) as client:
                resp = client.post(url, json=body)
                resp.raise_for_status()
                data = resp.json()
                return _extract_output(data)
        except httpx.HTTPError as e:
            if attempt == 1:
                raise RuntimeError(f"Langflow call failed [{flow_id}]: {e}") from e
    # Невозможный путь (из-за raise), но для типов:
    return None


def run_flow_evaluate(case, user_answer: str) -> Dict[str, Any]:
    """
    Вызов Flow A (оценка решения).
    Ожидаем JSON-ответ, валидируем через EvaluationResponse (мягко).
    """
    tweaks = {
        # Всё, что нужно flow, передаём явным образом
        "case_id": str(case.id),
        "case_description": case.description,
        "best_answer": case.best_answer,
        "skills": case.skills_json or [],
        "user_answer": user_answer,
    }

    result = _run_flow(EVALUATE_FLOW_ID, tweaks, output_type="json")

    # Попробуем провалидировать структуру для надёжности (не падаем, если невалидно)
    try:
        validated = EvaluationResponse.model_validate(result)
        return json.loads(validated.model_dump_json())
    except ValidationError:
        # Если JSON не соответствует схеме — всё равно вернём как есть, чтобы не ломать пайплайн
        return result if isinstance(result, dict) else {"raw": result}


def run_flow_explain(case, solution, evaluation_json: Dict[str, Any], question: str) -> str:
    """
    Вызов Flow B (объяснение оценки).
    Ожидаем текстовый ответ.
    """
    tweaks = {
        "case_id": str(case.id),
        "question": question,
        "case_description": case.description,
        "best_answer": case.best_answer,
        "skills": case.skills_json or [],
        "user_answer": solution.answer_text if solution else "",
        "evaluation_json": evaluation_json,
    }

    result = _run_flow(EXPLAIN_FLOW_ID, tweaks, output_type="text")

    # Приведём к строке на всякий случай
    if isinstance(result, (dict, list)):
        return json.dumps(result, ensure_ascii=False)
    return str(result)
