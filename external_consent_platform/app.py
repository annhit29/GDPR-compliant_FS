from flask import Flask, jsonify, render_template, redirect, request, url_for
from datetime import datetime
from models import db, Event, CurrentEventState
from api import bp as api_bp
from werkzeug.serving import run_simple

import yaml, os

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "event_config.yaml")
with open(CONFIG_PATH, "r") as f:
    EVENT_CONFIG = yaml.safe_load(f)["events"]

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
    # return render_template("index.html", events=events, states=states)
    return render_template("index.html", events=events, states=states, event_config=EVENT_CONFIG)

@app.route("/submit", methods=["POST"])
def submit():
    uid = request.form["uid"].strip()
    # purpose = request.form["purpose"].strip()
    purpose = request.form.get("purpose", "").strip()
    action = request.form["action"]

    # find the event definition
    evt_def = next((e for e in EVENT_CONFIG if e["name"] == action), None)
    if not evt_def:
        return jsonify({"error": f"Unknown event type: {action}"}), 400
    
    e = Event(kind=action, uid=uid, purpose=purpose, status="pending")
    db.session.add(e)
    db.session.commit()

    state_change = evt_def.get("state_change")
    if state_change:
        # use both uid and purpose for lookup (purpose may be empty)
        s = CurrentEventState.query.filter_by(uid=uid, purpose=purpose).one_or_none()
        if s:
            s.status = state_change
            s.updated_at = datetime.utcnow()
        else:
            db.session.add(CurrentEventState(uid=uid, purpose=purpose, status=state_change))
        db.session.commit()

    # status = "consented" if action == "Consent" else "revoked" 
    # s = CurrentEventState.query.filter_by(uid=uid, purpose=purpose).one_or_none()
    # if s:
        # s.status = status
        # s.updated_at = datetime.utcnow()
    # else:
        # db.session.add(CurrentEventState(uid=uid, purpose=purpose, status=status))
    # db.session.commit()
    return redirect(url_for("index"))

if __name__ == "__main__":
    run_simple("127.0.0.1", 5000, app, use_reloader=True, use_debugger=True, threaded=True) # to enable running concurrently the poller with the Flask app, so that the DS can see the latest consent/revocation status without restarting the Flask app.
