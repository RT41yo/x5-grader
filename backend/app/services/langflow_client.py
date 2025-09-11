# backend/app/services/langflow_client.py
from __future__ import annotations

import json
import logging
import os
import random
import time
from typing import Any, Dict, List, Optional

import httpx
from pydantic import ValidationError

from app.config import get_settings
from app.schemas import EvaluationResponse

log = logging.getLogger(__name__)

# === ENV / defaults ===
DEFAULT_BASE_URL = os.getenv("LANGFLOW_BASE_URL", "http://langflow:7860")
DEFAULT_API_KEY = os.getenv("LANGFLOW_API_KEY", "")
FLOW_ID_EVALUATE = os.getenv("FLOW_ID_EVALUATE", "")
FLOW_ID_EXPLAIN = os.getenv("FLOW_ID_EXPLAIN", "")

# Жёсткие таймауты под SLA ~3с end-to-end
TIMEOUT = httpx.Timeout(connect=5.0, read=90.0, write=20.0, pool=10.0)
MAX_RETRIES = 1           # 1 повтор на случай сетевого глитча
RETRY_BACKOFF = 0.2       # базовый бэкофф (с джиттером)

# Ограничим длину текстов, чтобы не улететь по токенам
CLIP_DEFAULT = 6000
CLIP_DESC = 4000


def _headers() -> Dict[str, str]:
    h = {"Content-Type": "application/json"}
    api_key = DEFAULT_API_KEY or os.getenv("LANGFLOW_API_KEY") or ""
    if api_key:
        # Langflow обычно ожидает x-api-key; при необходимости замените на Authorization: Bearer
        h["x-api-key"] = api_key
    return h


def _clip(text: Optional[str], limit: int = CLIP_DEFAULT) -> str:
    if not text:
        return ""
    if len(text) <= limit:
        return text
    return text[:limit] + "\n...[truncated]..."


def _strip_code_fences(s: str) -> str:
    """
    Убираем обёртки ```json ... ```/``` ... ```
    """
    if not isinstance(s, str):
        return s
    s = s.strip()
    if s.startswith("```"):
        # удалим первую строку (``` или ```json)
        s = s.lstrip("`")
        if "\n" in s:
            _, rest = s.split("\n", 1)
            s = rest
        s = s.rstrip("`").strip()
    return s


def _extract_text(payload: Dict[str, Any]) -> Optional[str]:
    """
    Аккуратно достаём текст из типичного ответа Langflow (/run, ChatOutput/LLM).
    Структуры отличаются по версиям → переберём варианты.
    """
    try:
        # Вариант: outputs[0].outputs[0].results.{text|message|output_text|data}
        outputs = payload.get("outputs", [])
        if outputs:
            inner = outputs[0].get("outputs", [])
            if inner:
                results = inner[0].get("results", {}) or {}
                for key in ("text", "message", "output_text", "data"):
                    v = results.get(key)
                    if isinstance(v, str) and v.strip():
                        return v
                    if isinstance(v, dict):
                        # иногда в data/message лежит {"text": "..."}
                        t = v.get("text")
                        if isinstance(t, str) and t.strip():
                            return t
    except Exception:
        pass

    # fallback: если просто строка в корне
    if isinstance(payload, str) and payload.strip():
        return payload

    # последний шанс: сериализуем всё как строку
    try:
        return json.dumps(payload, ensure_ascii=False)
    except Exception:
        return None


def _post_run(flow_id: str, body: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    base = get_settings().langflow_url or DEFAULT_BASE_URL
    url = f"{base}/api/v1/run/{flow_id}"

    for attempt in range(MAX_RETRIES + 1):
        try:
            with httpx.Client(timeout=TIMEOUT, headers=_headers()) as client:
                resp = client.post(url, json=body)
                if 200 <= resp.status_code < 300:
                    try:
                        return resp.json()
                    except Exception:
                        # иногда приходит текст; завернём в {"raw_text": ...}
                        return {"raw_text": resp.text}
                else:
                    log.error("Langflow HTTP %s %s: %s", resp.status_code, url, resp.text[:400])
        except httpx.HTTPError as e:
            log.warning("Langflow call failed (attempt %s/%s): %s", attempt + 1, MAX_RETRIES + 1, e)

        if attempt < MAX_RETRIES:
            time.sleep(RETRY_BACKOFF * (1 + random.random()))

    return None


def _mock_eval(skills: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Валидный под EvaluationResponse мок — на случай пустого FLOW_ID или сетевой ошибки.
    """
    def _criteria(sobj: Dict[str, Any]) -> List[Dict[str, Any]]:
        lst = []
        src = (sobj or {}).get("criteria") if isinstance(sobj, dict) else None
        if isinstance(src, list) and src:
            for c in src:
                name = (c.get("name") if isinstance(c, dict) else None) or "Критерий"
                lst.append({"name": name, "score": 3.0, "evidence": "—", "suggestion": "Повторить материал"})
        else:
            lst.append({"name": "Критерий", "score": 3.0, "evidence": "—", "suggestion": "Повторить материал"})
        return lst

    return {
        "overall_score": 60.0,
        "overall_explanation": "Mock evaluation: Langflow недоступен.",
        "skills": [
            {
                "name": (s.get("skill") if isinstance(s, dict) else None) or "Навык",
                "skill_score": 3.0,
                "criteria": _criteria(s if isinstance(s, dict) else {}),
                "improvement_plan": ["Прочитать методичку", "Отработать на кейсе"],
            }
            for s in (skills or [])
        ] or [
            {
                "name": "Навык",
                "skill_score": 3.0,
                "criteria": [{"name": "Критерий", "score": 3.0, "evidence": "—", "suggestion": "Повторить материал"}],
                "improvement_plan": ["Прочитать методичку", "Отработать на кейсе"],
            }
        ],
        "keyword_coverage": 50.0,
        "highlights": {},
    }


def run_flow_evaluate(case, user_answer: str) -> Dict[str, Any]:
    """
    Вызывает flow оценки (Flow A). Возвращает dict, соответствующий EvaluationResponse,
    либо максимально близко, либо мок при ошибке.
    """
    flow_id_env = getattr(get_settings(), "flow_id_evaluate", "") or FLOW_ID_EVALUATE
    if not flow_id_env:
        log.warning("FLOW_ID_EVALUATE is empty → using mock evaluation")
        return _mock_eval(case.skills_json or [])

    prompt_vars = {
        "case_title": case.title,
        "case_description": _clip(case.description, CLIP_DESC),
        "best_answer": _clip(case.best_answer, CLIP_DEFAULT),
        # skills многие ноды ждут как строку JSON — дадим и объект, и строку:
        "skills": json.dumps(case.skills_json or [], ensure_ascii=False),
        "user_answer": _clip(user_answer, CLIP_DEFAULT),
    }
    body = {
        "input_value": "",        # не используется, у нас system_message из Prompt
        "input_type": "chat",
        "output_type": "chat",
        "tweaks": {
            "Prompt-EVAL": prompt_vars,
            **prompt_vars  # на случай если flow сконфигурят иначе
        }
    }

    start = time.perf_counter()
    data = _post_run(flow_id_env, body)
    latency_ms = int((time.perf_counter() - start) * 1000)

    if not data:
        log.warning("Langflow evaluate: no data, returning mock")
        out = _mock_eval(case.skills_json or [])
        out.setdefault("meta", {})["latency_ms"] = latency_ms
        return out

    text = _extract_text(data)
    if not text:
        log.warning("Langflow evaluate: empty text, returning mock")
        out = _mock_eval(case.skills_json or [])
        out.setdefault("meta", {})["latency_ms"] = latency_ms
        return out

    clean = _strip_code_fences(text)

    # LLM должен вернуть ЧИСТЫЙ JSON. Валидируем через Pydantic.
    try:
        parsed = json.loads(clean)
    except Exception:
        log.error("Langflow evaluate returned non-JSON text: %s", text[:400])
        out = {"raw": text, "meta": {"latency_ms": latency_ms}}
        return out

    # Попробуем привести к EvaluationResponse → вернём уже "чистый" dict
    try:
        validated = EvaluationResponse.model_validate(parsed)
        out = json.loads(validated.model_dump_json())
        out.setdefault("meta", {})["latency_ms"] = latency_ms
        return out
    except ValidationError as ve:
        log.warning("EvaluationResponse validation failed: %s", ve.errors())
        # Вернём как есть (если это словарь), чтобы фронт хоть что-то показал.
        if isinstance(parsed, dict):
            parsed.setdefault("meta", {})["latency_ms"] = latency_ms
            return parsed
        return {"raw": parsed, "meta": {"latency_ms": latency_ms}}


def run_flow_explain(case, solution, evaluation_json: Dict[str, Any], question: str) -> str:
    """
    Объяснение оценки (Flow B). Возвращает чистый текст.
    """
    flow_id_env = getattr(get_settings(), "flow_id_explain", "") or FLOW_ID_EXPLAIN
    if not flow_id_env:
        log.warning("FLOW_ID_EXPLAIN is empty → using fallback text")
        return "Объяснение от AI недоступно. Попробуйте переформулировать вопрос."

    prompt_vars = {
        "case_id": str(case.id),
        "case_title": case.title,
        "case_description": _clip(case.description, CLIP_DESC),
        "best_answer": _clip(case.best_answer, CLIP_DEFAULT),
        "skills": json.dumps(case.skills_json or [], ensure_ascii=False),
        "user_answer": _clip(getattr(solution, "answer_text", "") or "", CLIP_DEFAULT),
        "evaluation_json": json.dumps(evaluation_json or {}, ensure_ascii=False),
        "question": (question or "").strip(),
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

    data = _post_run(flow_id_env, body)
    if not data:
        log.warning("Langflow explain: no data")
        return "Не удалось получить объяснение от AI."

    text = _extract_text(data)
    if not text or not text.strip():
        return "Пустой ответ от AI."
    return text.strip()
