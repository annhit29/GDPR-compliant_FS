from flask import Blueprint, jsonify, request
from models import db, Event, CurrentEventState

bp = Blueprint("api", __name__)

@bp.route("/events", methods=["GET"])
def list_events():
    status = request.args.get("status", "pending")
    q = Event.query.filter_by(status=status)
    return jsonify([
        dict(id=e.event_id, kind=e.kind, uid=e.uid, purpose=e.purpose,
             status=e.status, created_at=e.created_at.isoformat() + "Z")
        for e in q.order_by(Event.created_at.asc()).all()
    ])

@bp.route("/events/<int:event_id>/ack", methods=["PATCH", "POST"])
def ack_event(event_id):
    e = Event.query.get(event_id)
    if not e:
        return jsonify({"error": "not found"}), 404
    e.status = "acked"
    db.session.commit()
    return jsonify({"ok": True})

@bp.route("/consents/<uid>/<purpose>", methods=["GET"])
def get_consent(uid, purpose):
    row = CurrentEventState.query.filter_by(uid=uid, purpose=purpose).one_or_none()
    if not row:
        return jsonify({"uid": uid, "purpose": purpose, "status": "unknown"})
    return jsonify(row.as_dict())

@bp.route("/consents", methods=["GET"])
def list_current_states():
    rows = CurrentEventState.query.all()
    return jsonify([r.as_dict() for r in rows])
