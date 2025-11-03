from flask import Flask, render_template, redirect, request, url_for
from datetime import datetime
from models import db, Event, CurrentEventState
from api import bp as api_bp
from werkzeug.serving import run_simple

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///external_consent_platform.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db.init_app(app)
app.register_blueprint(api_bp, url_prefix="/api")


with app.app_context():
    db.create_all()

@app.route("/")
def index():
    events = Event.query.order_by(Event.created_at.desc()).limit(25).all()
    states = CurrentEventState.query.order_by(CurrentEventState.updated_at.desc()).all()
    return render_template("index.html", events=events, states=states)

@app.route("/submit", methods=["POST"])
def submit():
    uid = request.form["uid"].strip()
    purpose = request.form["purpose"].strip()
    action = request.form["action"]

    e = Event(kind=action, uid=uid, purpose=purpose, status="pending")
    db.session.add(e)
    db.session.commit()

    status = "consented" if action == "consent" else "revoked"
    s = CurrentEventState.query.filter_by(uid=uid, purpose=purpose).one_or_none()
    if s:
        s.status = status
        s.updated_at = datetime.utcnow()
    else:
        db.session.add(CurrentEventState(uid=uid, purpose=purpose, status=status))
    db.session.commit()
    return redirect(url_for("index"))

if __name__ == "__main__":
    run_simple("127.0.0.1", 5000, app, use_reloader=True, use_debugger=True, threaded=True) # to enable running concurrently the poller with the Flask app, so that the DS can see the latest consent/revocation status without restarting the Flask app.
