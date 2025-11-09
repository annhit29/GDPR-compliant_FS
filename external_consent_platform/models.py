from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class Event(db.Model):
    __tablename__ = "events"
    event_id = db.Column(db.Integer, primary_key=True)
    kind = db.Column(db.String(16), nullable=False)  # Consent or Revoke
    uid = db.Column(db.String(128), nullable=False)
    purpose = db.Column(db.String(128), nullable=False) # service, analytics, marketing, etc.
    status = db.Column(db.String(16), default="pending")  # pending or acked
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class CurrentEventState(db.Model):
    __tablename__ = "current_event_state"
    current_state_id = db.Column(db.Integer, primary_key=True)
    uid = db.Column(db.String(128), nullable=False)
    purpose = db.Column(db.String(128), nullable=False)
    category = db.Column(db.String(32), nullable=False, default="general") # consent category, request category, etc.
    status = db.Column(db.String(16), nullable=False)  # consented or revoked
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)

    def as_dict(self):
        return {
            "uid": self.uid,
            "purpose": self.purpose,
            "status": self.status,
            "updated_at": self.updated_at.isoformat() + "Z",
        }
