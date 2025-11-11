from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

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

class User(db.Model):
    """
    The attributes first_name, last_name are the DS' personal data that are evaluated by the Enforcer.
    """
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True) # identifier for the internal "external consent platform" database
    uid = db.Column(db.String(64), unique=True, nullable=False) # user identifier  # nullable=False means this field must be provided
    first_name = db.Column(db.String(64))
    last_name = db.Column(db.String(64))
    password_hash = db.Column(db.String(128), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
