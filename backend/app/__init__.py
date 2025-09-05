# backend/app/__init__.py
from __future__ import annotations

import logging
from flask import Flask
from flask_cors import CORS

from .config import get_settings
from .db import init_db
from .web.routes import web_bp
from .blueprints.admin import admin_bp
from .blueprints.scoring import scoring_bp
from .blueprints.chat import chat_bp


def create_app() -> Flask:
    """Фабрика Flask-приложения."""
    app = Flask(__name__, static_folder=None)

    # === CORS ===
    # Для демо-развёртывания — разрешим всех.
    # Если будет фронт на отдельном домене → заменить на CORS(app, origins=[...])
    CORS(app)

    # === Конфиги ===
    settings = get_settings()
    app.config["SECRET_KEY"] = settings.secret_key
    app.config["SQLALCHEMY_DATABASE_URI"] = settings.database_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "pool_pre_ping": True,
        "pool_recycle": 1800,
    }

    # === Инициализация БД ===
    init_db(app)

    # === Регистрация blueprints ===
    app.register_blueprint(admin_bp, url_prefix="/api/admin")
    app.register_blueprint(scoring_bp, url_prefix="/api")
    app.register_blueprint(chat_bp, url_prefix="/api")
    app.register_blueprint(web_bp)

    # === Healthcheck ===
    @app.route("/api/health", methods=["GET"])
    def health():
        return {"status": "ok"}

    # === Логирование (для gunicorn) ===
    if not app.logger.handlers:
        handler = logging.StreamHandler()
        fmt = logging.Formatter("[%(asctime)s] %(levelname)s in %(module)s: %(message)s")
        handler.setFormatter(fmt)
        app.logger.addHandler(handler)
        app.logger.setLevel(logging.INFO)

    return app
