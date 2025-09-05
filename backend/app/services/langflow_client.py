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

# === ENV / defaults ===
DEFAULT_BASE_URL = os.getenv("LANGFLOW_BASE_URL", "http://langflow:7860")
DEFAULT_API_KEY  = os.getenv("LANGFLOW_API_KEY", "")
FLOW_ID_EVALUATE = os.getenv("FLOW_ID_EVALUATE", "")  # можно оставить пустым → мок
FLOW_ID_EXPLAIN  = os.getenv("FLOW_ID_EXPLAIN", "")

TIMEOUT = httpx.Timeout(connect=5.0, read=35.0, write=10.0, pool=5.0)


def _headers() -> Dict[str, str]:
    h = {"Content-Type": "application/json"}
    if DEFAULT_API_KEY:
        # Langflow ожидает x-api-key
        h["x-api-key"] = DEFAULT_API_KEY
    return h


def _mock_eval(skills: List[Dict[str, Any]]) -> Dict[str, Any]:
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
        "notes": "Mock evaluation (Langflow disabled or request failed).",
    }


def _extract_text(payload: Dict[str, Any]) -> Optional[str]:
    """
    Достаём текст из типичного ответа Langflow (/run, ChatOutput/LLM).
    Структуры отличаются по версиям, поэтому аккуратно перебираем варианты.
    """
    # Вариант: outputs[0].outputs[0].results.text
    try:
        outputs = payload.get("outputs", [])
        if outputs:
            inner = outputs[0].get("outputs", [])
            if inner:
                results = inner[0].get("results", {}) or {}
                for key in ("text", "message", "output_text", "data"):
                    v = results.get(key)
                    if isinstance(v, str):
                        return v
                    # иногда приходит {"text": "..."} внутри data/message
                    if isinstance(v, dict) and "text" in v and isinstance(v["text"], str):
                        return v["text"]
    except Exception:
        pass

    # fallback: если просто строка в корне
    if isinstance(payload, str):
        return payload

    # последний шанс: сериализуем всё как строку
    try:
        return json.dumps(payload, ensure_ascii=False)
    except Exception:
        return None


def _post_run(flow_id: str, body: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    base = get_settings().langflow_url or DEFAULT_BASE_URL
    url = f"{base}/api/v1/run/{flow_id}"
    try:
        with httpx.Client(timeout=TIMEOUT, headers=_headers()) as client:
            resp = client.post(url, json=body)
            if 200 <= resp.status_code < 300:
                # даже если content-type не json — попробуем распарсить
                try:
                    return resp.json()
                except Exception:
                    # иногда приходит текст; завернём в {"raw_text": ...}
                    return {"raw_text": resp.text}
            else:
                log.error("Langflow HTTP %s %s: %s", resp.status_code, url, resp.text[:400])
                return None
    except httpx.HTTPError as e:
        log.exception("Langflow call failed: %s", e)
        return None


def run_flow_evaluate(case, user_answer: str) -> Dict[str, Any]:
    """
    Вызывает flow оценки. Возвращает dict со структурой EvaluationResponse
    (или максимально близко), иначе мок.
    """
    flow_id = getattr(get_settings(), "flow_id_evaluate", FLOW_ID_EVALUATE) or FLOW_ID_EVALUATE
    if not flow_id:
        log.warning("FLOW_ID_EVALUATE is empty → using mock evaluation")
        return _mock_eval(case.skills_json or [])

    # Tweaks: адресуемся к Prompt-нODE по ID "Prompt-EVAL"
    prompt_vars = {
        "case_title": case.title,
        "case_description": case.description,
        "best_answer": case.best_answer,
        # skills многие ноды ждут как строку JSON — дадим и так, и так:
        "skills": json.dumps(case.skills_json or [], ensure_ascii=False),
        "user_answer": user_answer,
    }
    body = {
        "input_value": "",        # не используется, у нас system_message из Prompt
        "input_type": "chat",     # безопасный тип для ChatOutput
        "output_type": "chat",
        "tweaks": {
            "Prompt-EVAL": prompt_vars,
            # на всякий случай плоско (если flow сконфигурят иначе)
            **prompt_vars
        }
    }

    data = _post_run(flow_id, body)
    if not data:
        log.warning("Langflow evaluate: no data, returning mock")
        return _mock_eval(case.skills_json or [])

    text = _extract_text(data)
    if not text:
        log.warning("Langflow evaluate: empty text, returning mock")
        return _mock_eval(case.skills_json or [])

    # LLM должен выдать ЧИСТЫЙ JSON (мы так попросили в промпте).
    # Попробуем распарсить, иначе завернём как raw.
    try:
        parsed = json.loads(text)
        try:
            validated = EvaluationResponse.model_validate(parsed)
            return json.loads(validated.model_dump_json())
        except ValidationError:
            return parsed if isinstance(parsed, dict) else {"raw": parsed}
    except Exception:
        log.error("Langflow evaluate returned non-JSON text: %s", text[:400])
        return {"raw": text}


def run_flow_explain(case, solution, evaluation_json: Dict[str, Any], question: str) -> str:
    """
    Объяснение оценки. Возвращает чистый текст.
    """
    flow_id = getattr(get_settings(), "flow_id_explain", FLOW_ID_EXPLAIN) or FLOW_ID_EXPLAIN
    if not flow_id:
        log.warning("FLOW_ID_EXPLAIN is empty → using fallback text")
        return "Объяснение от AI недоступно. Попробуйте переформулировать вопрос."

    prompt_vars = {
        "case_id": str(case.id),
        "case_title": case.title,
        "case_description": case.description,
        "best_answer": case.best_answer,
        "skills": json.dumps(case.skills_json or [], ensure_ascii=False),
        "user_answer": getattr(solution, "answer", "") or "",
        "evaluation_json": json.dumps(evaluation_json or {}, ensure_ascii=False),
        "question": question or "",
    }
    body = {
        "input_value": "",
        "input_type": "chat",
        "output_type": "chat",
        "tweaks": {
            "Prompt-EXPL": prompt_vars,
            **prompt_vars
        }
    }

    data = _post_run(flow_id, body)
    if not data:
        log.warning("Langflow explain: no data")
        return "Не удалось получить объяснение от AI."

    text = _extract_text(data)
    if not text:
        return "Пустой ответ от AI."
    return text
