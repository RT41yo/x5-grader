# backend/services/langflow_client.py
import os
import json
import logging
from typing import Any, Dict, Optional, List

import httpx
from pydantic import ValidationError

from app.config import get_settings
from app.schemas import EvaluationResponse

log = logging.getLogger(__name__)

# ===== Настройки / дефолты =====
DEFAULT_EVALUATE_FLOW_ID = os.getenv("FLOW_ID_EVALUATE", "");  # пусто = отключено → мок
DEFAULT_EXPLAIN_FLOW_ID  = os.getenv("FLOW_ID_EXPLAIN",  "");  # пусто = отключено → мок
DEFAULT_BASE_URL         = os.getenv("LANGFLOW_BASE_URL", "http://langflow:7860")
DEFAULT_TIMEOUTS         = httpx.Timeout(connect=5.0, read=30.0, write=10.0, pool=5.0)

# Если когда-то понадобится токен:
DEFAULT_API_KEY          = os.getenv("LANGFLOW_API_KEY", "")


# ===== Вспомогательные =====
def _mock_eval(skills: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Простейший мок-ответ для демо, когда Langflow не подключён."""
    return {
        "overall_score": 3,
        "skills": [
            {
                "name": (s.get("skill") or "Навык"),
                "skill_score": 3,
                "improvement_plan": ["Почитать методичку", "Попрактиковаться"],
            }
            for s in (skills or [])
        ],
        "notes": "Mock evaluation (Langflow disabled or error)",
    }


def _extract_output(payload: Dict[str, Any]) -> Any:
    """
    Универсальный парсер ответа Langflow.
    Пытаемся вытащить полезный контент из популярных структур.
    """
    # вариант 1: outputs[0].outputs[0].results.{json|text|data}
    try:
        outputs = payload.get("outputs", [])
        if outputs:
            inner_outputs = outputs[0].get("outputs", [])
            if inner_outputs:
                results = inner_outputs[0].get("results", {}) or {}
                for key in ("json", "text", "data"):
                    if key in results:
                        return results[key]
    except Exception:
        pass

    # вариант 2: верхний уровень {"result": {...}} или {"data": ...}
    for key in ("result", "data"):
        if key in payload:
            return payload[key]

    # крайний случай: возвращаем как есть
    return payload


def _headers() -> Dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if DEFAULT_API_KEY:
        headers["Authorization"] = f"Bearer {DEFAULT_API_KEY}"
    return headers


def _try_parse_json(resp: httpx.Response) -> Optional[Dict[str, Any]]:
    ctype = resp.headers.get("content-type", "")
    text = resp.text
    if "application/json" in ctype.lower():
        try:
            return resp.json()
        except Exception as e:
            log.error("Langflow returned invalid JSON: %s ... (%s)", text[:300], e)
            return None
    # Иногда сервис отдаёт JSON без заголовка
    try:
        return json.loads(text)
    except Exception:
        log.error("Langflow returned non-JSON response (status %s): %s", resp.status_code, text[:300])
        return None


def _run_flow_http(
    base_url: str,
    flow_id: str,
    payload: Dict[str, Any],
    timeout: httpx.Timeout,
) -> Optional[Dict[str, Any]]:
    """
    Пробуем разные URL-формы запуска flow. Вернём распарсенный JSON или None.
    """
    # На разных версиях Langflow встречаются оба варианта
    candidates = [
        f"{base_url}/api/v1/run/{flow_id}?stream=false",
        f"{base_url}/api/v1/process/{flow_id}?stream=false",
    ]

    with httpx.Client(timeout=timeout, headers=_headers()) as client:
        for url in candidates:
            try:
                log.info("Calling Langflow: %s", url)
                resp = client.post(url, json=payload)
                if 200 <= resp.status_code < 300:
                    data = _try_parse_json(resp)
                    if data is not None:
                        return data
                    # если 2xx, но не JSON — пробуем следующий endpoint
                    continue
                else:
                    log.error("Langflow HTTP %s %s: %s", resp.status_code, url, resp.text[:300])
            except httpx.HTTPError as e:
                log.exception("Langflow call failed on %s: %s", url, e)
    return None


# ===== Публичные функции =====
def run_flow_evaluate(case, user_answer: str) -> Dict[str, Any]:
    """
    Вызов Flow «оценить кейс».
    Если flow выключен (нет FLOW_ID_EVALUATE) — возвращаем мок-оценку.
    """
    settings = get_settings()
    base_url = getattr(settings, "langflow_url", DEFAULT_BASE_URL) or DEFAULT_BASE_URL
    flow_id  = getattr(settings, "flow_id_evaluate", DEFAULT_EVALUATE_FLOW_ID) or DEFAULT_EVALUATE_FLOW_ID
    timeout  = DEFAULT_TIMEOUTS

    # Если Flow ID пустой — работаем в режиме демо
    if not flow_id:
        log.warning("FLOW_ID_EVALUATE is empty → using mock evaluation")
        return _mock_eval(case.skills_json or [])

    # Собираем payload под ноды flow-а
    tweaks = {
        "case_id": str(case.id),
        "case_title": case.title,
        "case_description": case.description,
        "best_answer": case.best_answer,
        "skills": case.skills_json or [],
        "user_answer": user_answer,
    }
    body = {
        "input_value": "",
        "input_type": "input",
        "output_type": "json",
        "tweaks": tweaks,
    }

    # 2 попытки на случай сетевых глюков
    for attempt in range(2):
        data = _run_flow_http(base_url, flow_id, body, timeout)
        if data is not None:
            result = _extract_output(data)
            # Попробуем провалидировать (мягко)
            try:
                validated = EvaluationResponse.model_validate(result)
                return json.loads(validated.model_dump_json())
            except ValidationError:
                # Если структура свободная — возвращаем как есть
                return result if isinstance(result, dict) else {"raw": result}
        log.warning("Langflow evaluate attempt %s failed, retrying...", attempt + 1)

    # Все попытки не удались — вернём мок, но логируем причину
    log.warning("Langflow evaluate failed, returning mock.")
    return _mock_eval(case.skills_json or [])


def run_flow_explain(case, solution, evaluation_json: Dict[str, Any], question: str) -> str:
    """
    Вызов Flow «объяснить оценку».
    Если flow выключен (нет FLOW_ID_EXPLAIN) — возвращаем шаблонный текст.
    """
    settings = get_settings()
    base_url = getattr(settings, "langflow_url", DEFAULT_BASE_URL) or DEFAULT_BASE_URL
    flow_id  = getattr(settings, "flow_id_explain", DEFAULT_EXPLAIN_FLOW_ID) or DEFAULT_EXPLAIN_FLOW_ID
    timeout  = DEFAULT_TIMEOUTS

    if not flow_id:
        log.warning("FLOW_ID_EXPLAIN is empty → using mock explanation")
        return "Автоматический разбор недоступен. Задайте более конкретный вопрос или сверьтесь с лучшим ответом."

    tweaks = {
        "case_id": str(case.id),
        "case_title": case.title,
        "case_description": case.description,
        "best_answer": case.best_answer,
        "skills": case.skills_json or [],
        "user_answer": (solution.answer if hasattr(solution, "answer") else "") or "",
        "evaluation_json": evaluation_json,
        "question": question or "",
    }
    body = {
        "input_value": "",
        "input_type": "input",
        "output_type": "text",
        "tweaks": tweaks,
    }

    for attempt in range(2):
        data = _run_flow_http(base_url, flow_id, body, timeout)
        if data is not None:
            out = _extract_output(data)
            if isinstance(out, (dict, list)):
                return json.dumps(out, ensure_ascii=False)
            return str(out)
        log.warning("Langflow explain attempt %s failed, retrying...", attempt + 1)

    log.warning("Langflow explain failed, returning fallback text.")
    return "Не удалось получить объяснение от AI. Попробуйте переформулировать вопрос."
