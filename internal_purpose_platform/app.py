from flask import Flask, render_template, request, redirect, url_for
from datetime import datetime
from models import db, SessionEvent, CurrentSession
from api import bp as api_bp
from werkzeug.serving import run_simple

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///internal_purpose_platform.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)
app.register_blueprint(api_bp, url_prefix="/api")

with app.app_context():
    db.create_all()

@app.route("/")
def index():
    sessions = CurrentSession.query.order_by(CurrentSession.updated_at.desc()).all()
    events = SessionEvent.query.order_by(SessionEvent.created_at.desc()).limit(25).all()
    return render_template("index.html", sessions=sessions, events=events)

@app.route("/start", methods=["POST"])
def start():
    uid = request.form["uid"].strip()
    purpose = request.form["purpose"].strip()
    reason = request.form["reason"].strip()

    # create the SessionStart event (i.e. `Use` event begins)
    ev = SessionEvent(uid=uid, purpose=purpose, reason=reason, kind="Start")
    db.session.add(ev)

    cur = CurrentSession.query.filter_by(uid=uid).first() # if the currentSession already exists, update it
    if cur:
        cur.purpose = purpose
        cur.reason = reason
        cur.active = True
        cur.updated_at = datetime.utcnow()
    else: # else, create a new currentSession
        db.session.add(CurrentSession(uid=uid, purpose=purpose, reason=reason, active=True))

    db.session.commit()
    return redirect(url_for("index"))

@app.route("/stop", methods=["POST"])
def stop():
    uid = request.form["uid"].strip()
    ev = SessionEvent(uid=uid, purpose="", reason="", kind="Stop")
    db.session.add(ev)

    cur = CurrentSession.query.filter_by(uid=uid).first()
    if cur:
        cur.active = False
        cur.updated_at = datetime.utcnow()

    db.session.commit()
    return redirect(url_for("index"))

if __name__ == "__main__":
    run_simple("127.0.0.1", 8000, app, use_reloader=True, use_debugger=True, threaded=True)
