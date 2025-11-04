from flask import Blueprint, jsonify, request
from models import db, CurrentSession, SessionEvent
from datetime import datetime

bp = Blueprint("api", __name__)

@bp.route("/sessions", methods=["GET"])
def list_sessions():
    sessions = CurrentSession.query.all()
    return jsonify([s.as_dict() for s in sessions])

@bp.route("/sessions/<uid>", methods=["GET"])
def get_session(uid):
    s = CurrentSession.query.filter_by(uid=uid).first()
    if not s:
        return jsonify({"uid": uid, "active": False})
    return jsonify(s.as_dict())

@bp.route("/events", methods=["POST"])
def record_event():
    payload = request.get_json(force=True)
    e = SessionEvent(
        uid=payload.get("uid"),
        purpose=payload.get("purpose", ""),
        reason=payload.get("reason", ""),
        kind=payload.get("kind", "Use"),
        created_at=datetime.utcnow()
    )
    db.session.add(e)
    db.session.commit()
    return jsonify({"ok": True})
