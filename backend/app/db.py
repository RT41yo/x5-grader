# backend/app/db.py
from __future__ import annotations

from flask_sqlalchemy import SQLAlchemy

# expire_on_commit=False — чтобы объекты не протухали сразу после commit()
db = SQLAlchemy(session_options={"expire_on_commit": False})


def init_db(app) -> None:
    """
    Инициализация подключения к БД.
    Опции пула и др. задаются в app.config в фабрике приложения (__init__.py).
    """
    db.init_app(app)
