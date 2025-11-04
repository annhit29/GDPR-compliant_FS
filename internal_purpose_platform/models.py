from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class SessionEvent(db.Model):
    __tablename__ = "session_events"
    event_id = db.Column(db.Integer, primary_key=True)
    kind = db.Column(db.String(32), nullable=False)  # Start, Stop, Use, LegalGround
    uid = db.Column(db.String(128), nullable=False)
    purpose = db.Column(db.String(128), nullable=False) # service, analytics, marketing, etc.
    reason = db.Column(db.String(256)) # reason for data processing eg: "for improving user experience"
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class CurrentSession(db.Model):
    __tablename__ = "current_session"
    current_session_id = db.Column(db.Integer, primary_key=True)
    uid = db.Column(db.String(128), nullable=False)
    purpose = db.Column(db.String(128), nullable=False)
    reason = db.Column(db.String(256))
    active = db.Column(db.Boolean, default=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)

    def as_dict(self):
        return {
            "uid": self.uid,
            "purpose": self.purpose,
            "reason": self.reason,
            "active": self.active,
            "updated_at": self.updated_at.isoformat() + "Z",
        }
