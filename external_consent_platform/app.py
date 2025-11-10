from flask import Flask, jsonify, render_template, redirect, request, url_for, session
from datetime import datetime
from models import db, Event, CurrentEventState, User
from api import bp as api_bp
from werkzeug.serving import run_simple
import requests
import yaml, os
from flask import flash

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "event_config.yaml")
with open(CONFIG_PATH, "r") as f:
    EVENT_CONFIG = yaml.safe_load(f)["events"]

app = Flask(__name__)
app.secret_key = os.urandom(24) # a SECRET_KEY to securely sign the session cookies # todo: this can be improved by using a fixed secret key from env variable or config file, by storing it in a .env or config file

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///external_consent_platform.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db.init_app(app)
app.register_blueprint(api_bp, url_prefix="/api")


with app.app_context():
    db.create_all() # create all the relational tables if not exist

# ---- User Authentication Routes ---
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        uid = request.form["uid"].strip()
        first = request.form["first_name"].strip()
        last = request.form["last_name"].strip()
        pwd = request.form["password"]

        if User.query.filter_by(uid=uid).first():
            return "UID already exists", 400

        u = User(uid=uid, first_name=first, last_name=last)
        u.set_password(pwd)
        db.session.add(u)
        db.session.commit()
        
        # Notify FUSE daemon to sync users
        try:
            requests.post("http://127.0.0.1:7000/sync_users", timeout=2)
            print(f"[SYNC] Notified FUSE daemon to sync users (after {uid} signup).")
        except Exception as e:
            print(f"[WARN] Failed to notify FUSE daemon: {e}")
        
        return redirect(url_for("login"))
    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        uid = request.form["uid"].strip()
        pwd = request.form["password"]
        u = User.query.filter_by(uid=uid).first()
        if not u or not u.check_password(pwd):
            return "Invalid credentials", 401
        session["uid"] = uid
        return redirect(url_for("index"))
    return render_template("login.html")


@app.route("/logout", methods=["GET", "POST"])
def logout():
    session.clear()
    return redirect(url_for("login"))

# ---- Main Application Routes ---
@app.route("/") # main page
def index():
    if "uid" not in session: # if user is not logged in
        return redirect(url_for("login")) # then redirect to the login page
    # else:
    events = Event.query.order_by(Event.created_at.desc()).limit(25).all()
    states = CurrentEventState.query.order_by(CurrentEventState.updated_at.desc()).all()
    # return render_template("index.html", events=events, states=states)
    return render_template("index.html", events=events, states=states, event_config=EVENT_CONFIG)

@app.route("/submit", methods=["POST"])
def submit():
    """
    Handle event submissions from the external consent platform.
    """
    if "uid" not in session:
        flash("You must log in first.")
        return redirect(url_for("login"))
    uid = session["uid"] # get uid from session, in order to prevent DS from triggering events for another DS
    # uid = request.form["uid"].strip()
    purpose = request.form.get("purpose", "").strip().lower()
    action = request.form["action"]

    if not action:
        flash("No action specified.")
        return redirect(url_for("index"))
    
    # find the event definition
    evt_def = next((e for e in EVENT_CONFIG if e["name"] == action), None)
    if not evt_def:
        flash(f"Unknown event type: {action}")
        return redirect(url_for("index"))
        # return jsonify({"error": f"Unknown event type: {action}"}), 400
    
    # Save the event locally in external_consent_platform.db
    e = Event(kind=action, uid=uid, purpose=purpose, status="pending")
    db.session.add(e)
    db.session.commit()

    # Update state only if configured
    state_change = evt_def.get("state_change")
    category = evt_def.get("category", "general")
    if state_change:
        # use both uid and purpose for lookup (purpose may be empty)
        s = CurrentEventState.query.filter_by(uid=uid, purpose=purpose, category=category).one_or_none()

        if s:
            s.status = state_change
            s.updated_at = datetime.utcnow()
        else:
            db.session.add(CurrentEventState(uid=uid, purpose=purpose, category=category, status=state_change))
        db.session.commit()
    return redirect(url_for("index"))

if __name__ == "__main__":
    run_simple("127.0.0.1", 5000, app, use_reloader=True, use_debugger=True, threaded=True) # to enable running concurrently the poller with the Flask app, so that the DS can see the latest consent/revocation status without restarting the Flask app.
