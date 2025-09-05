# backend/wsgi.py
import os
import logging
from typing import List

from app import create_app
from app.db import db
from sqlalchemy import text

app = create_app()

def _drop_orphan_composite_types(table_names: List[str], schema: str = "public"):
    """
    В Postgres при создании таблицы автоматически создаётся композитный тип с тем же именем.
    Если по какой-то причине тип остался, а таблица не создана, повторный CREATE TABLE падает
    с ошибкой уникальности (pg_type_typname_nsp_index). Здесь мы:
      - проверяем, существует ли таблица в schema;
      - если таблицы нет, но есть тип с тем же именем — удаляем этот тип.
    """
    conn = db.engine.connect()
    try:
        for tbl in table_names:
            # есть ли таблица?
            table_exists = conn.execute(
                text("""
                    SELECT EXISTS (
                      SELECT 1
                      FROM   pg_catalog.pg_class c
                      JOIN   pg_catalog.pg_namespace n ON n.oid = c.relnamespace
                      WHERE  c.relkind = 'r'          -- обычная таблица
                      AND    n.nspname = :schema
                      AND    c.relname = :tbl
                    )
                """),
                {"schema": schema, "tbl": tbl},
            ).scalar()

            if table_exists:
                continue

            # есть ли тип с таким именем?
            type_exists = conn.execute(
                text("""
                    SELECT EXISTS (
                      SELECT 1
                      FROM   pg_catalog.pg_type t
                      JOIN   pg_catalog.pg_namespace n ON n.oid = t.typnamespace
                      WHERE  n.nspname = :schema
                      AND    t.typname = :tbl
                    )
                """),
                {"schema": schema, "tbl": tbl},
            ).scalar()

            if type_exists:
                app.logger.warning(
                    "Found orphan composite type '%s' in schema '%s' — dropping it...", tbl, schema
                )
                # Экранируем идентификаторы кавычками
                conn.execute(text(f'DROP TYPE "{schema}"."{tbl}" CASCADE;'))
        conn.commit()
    finally:
        conn.close()


# ===== Автосоздание таблиц (для демо вместо Alembic) =====
if os.getenv("AUTO_CREATE_TABLES") == "1":
    with app.app_context():
        try:
            # 1) Чистим осиротевшие типы под наши таблицы
            table_names = list(db.metadata.tables.keys())  # имена таблиц из моделей
            _drop_orphan_composite_types(table_names, schema="public")

            # 2) Создаём недостающие таблицы
            db.create_all()
            app.logger.info("AUTO_CREATE_TABLES: created all tables (if missing).")
        except Exception as exc:
            app.logger.exception("AUTO_CREATE_TABLES: failed to create tables: %s", exc)

# Настройка логгера под gunicorn
if not app.logger.handlers:
    handler = logging.StreamHandler()
    fmt = logging.Formatter("[%(asctime)s] %(levelname)s in %(module)s: %(message)s")
    handler.setFormatter(fmt)
    app.logger.addHandler(handler)
    app.logger.setLevel(logging.INFO)

# Gunicorn ищет переменную "app"
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
