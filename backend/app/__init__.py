from flask import Flask
from flask_cors import CORS
from .config import get_settings
from .db import init_db
from .web.routes import web_bp

# Blueprints подключим позже
from .blueprints.admin import admin_bp
from .blueprints.scoring import scoring_bp
from .blueprints.chat import chat_bp


def create_app():
    """Flask app factory."""
    app = Flask(__name__, static_folder=None)
    CORS(app)

    # Загружаем конфиги
    settings = get_settings()
    app.config["SQLALCHEMY_DATABASE_URI"] = settings.database_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # Инициализация БД
    init_db(app)

    # Регистрируем blueprints
    app.register_blueprint(admin_bp, url_prefix="/api/admin")
    app.register_blueprint(scoring_bp, url_prefix="/api")
    app.register_blueprint(chat_bp, url_prefix="/api")
    app.register_blueprint(web_bp)

    @app.route("/api/health", methods=["GET"])
    def health():
        return {"status": "ok"}

    return app
