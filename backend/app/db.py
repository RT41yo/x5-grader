from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


def init_db(app):
    """Инициализация подключения к БД."""
    db.init_app(app)
