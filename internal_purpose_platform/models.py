from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class CurrentSession(db.Model):
    """
    Tracks the currently active session for each internal user.
    A session := same user + same purpose + same sub-purpose (reason)
    """
    __tablename__ = "current_sessions"
    current_state_id = db.Column(db.Integer, primary_key=True)
    uid = db.Column(db.String, db.ForeignKey("internal_users.uid"), nullable=False)
    purpose = db.Column(db.String, nullable=False)
    reason = db.Column(db.String, nullable=False)
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    active = db.Column(db.Boolean, default=True) # 0 = inactive, 1 = active

    def as_dict(self):
        return {
            "uid": self.uid,
            "purpose": self.purpose,
            "reason": self.reason,
            "active": self.active,
            "started_at": self.started_at.isoformat() + "Z",
        }
    
class InternalUser(db.Model): # same structure as User in external_consent_platform/models.py
    __tablename__ = "internal_users"
    id = db.Column(db.Integer, primary_key=True)
    uid = db.Column(db.String, unique=True, nullable=False)
    first_name = db.Column(db.String)
    last_name = db.Column(db.String)
    password_hash = db.Column(db.String)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
