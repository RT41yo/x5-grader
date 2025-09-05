import uuid
from datetime import datetime
from .db import db


class Case(db.Model):
    __tablename__ = "cases"

    id = db.Column(db.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = db.Column(db.String, nullable=False)
    description = db.Column(db.Text, nullable=False)  # текст кейса
    best_answer = db.Column(db.Text, nullable=False)
    skills_json = db.Column(db.JSON, nullable=False)  # структура навыков/критериев


class Solution(db.Model):
    __tablename__ = "solutions"

    id = db.Column(db.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    case_id = db.Column(db.UUID(as_uuid=True), db.ForeignKey("cases.id"), nullable=False)
    user_id = db.Column(db.String, nullable=False)  # для MVP хватит строки
    answer_text = db.Column(db.Text, nullable=False)
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)


class Session(db.Model):
    __tablename__ = "sessions"

    id = db.Column(db.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    case_id = db.Column(db.UUID(as_uuid=True), db.ForeignKey("cases.id"), nullable=False)
    user_id = db.Column(db.String, nullable=False)
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    duration_sec = db.Column(db.Integer, nullable=True)


class Evaluation(db.Model):
    __tablename__ = "evaluations"

    id = db.Column(db.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = db.Column(db.UUID(as_uuid=True), db.ForeignKey("sessions.id"), nullable=False)
    overall_score = db.Column(db.Float, nullable=True)
    raw_json = db.Column(db.JSON, nullable=False)  # полный ответ от Langflow
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
