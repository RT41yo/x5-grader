# app/web/routes.py
from flask import Blueprint, render_template, redirect, url_for, request, send_from_directory

# Blueprint для веб-страниц (шаблонов)
# Папки templates/ и static/ находятся рядом с этим файлом:
# app/web/templates, app/web/static
web_bp = Blueprint(
    "web",
    __name__,
    template_folder="templates",
    static_folder="static",
    static_url_path="/static",  # явно фиксируем путь для статики
)


@web_bp.route("/")
def index():
    """Главная: переадресуем на страницу сдачи решения."""
    return redirect(url_for("web.submit_page"))


@web_bp.route("/admin")
def admin_page():
    """
    Админ-панель:
    - форма создания кейса (title, description, best_answer, skills_json)
    - список уже созданных кейсов

    Данные подгружаются через fetch из /api/admin/cases на стороне клиента (main.js),
    чтобы не тащить логику в серверный рендер.
    """
    return render_template(
        "admin.html",
        page_title="Админ-панель — X5 AI Checker",
    )


@web_bp.route("/submit", methods=["GET"])
def submit_page():
    """
    Страница сдачи решения:
    - выпадающий список кейсов (подтягивается через /api/admin/cases)
    - textarea для ответа
    - отправка POST на /api/submit_solution из main.js
    """
    return render_template(
        "submit.html",
        page_title="Сдать решение — X5 AI Checker",
    )


@web_bp.route("/result/<session_id>", methods=["GET"])
def result_page(session_id: str):
    """
    Страница просмотра результата:
    - подгружает JSON из /api/result/<session_id> на клиенте (main.js)
    - показывает общую/точечные оценки, рекомендации
    - блок для вопросов (POST /api/ask)
    """
    return render_template(
        "result.html",
        page_title="Результат проверки — X5 AI Checker",
        session_id=session_id,
    )


@web_bp.route("/favicon.ico")
def favicon():
    """Уберём 404 по фавиконке."""
    return send_from_directory(web_bp.static_folder, "favicon.ico", mimetype="image/x-icon")
