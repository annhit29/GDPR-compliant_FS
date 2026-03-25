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

app.config["SESSION_COOKIE_NAME"] = "external_session"
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
    # Fetch current logged-in user info
    uid = session["uid"]
    user = User.query.filter_by(uid=uid).first()

    # events = Event.query.order_by(Event.created_at.desc()).limit(25).all()
    events = (
        Event.query
        .filter_by(uid=uid) # only show events of the logged-in user
        .order_by(Event.created_at.desc())
        .limit(25)
        .all()
    )
    # states = CurrentEventState.query.order_by(CurrentEventState.updated_at.desc()).all()
    states = (
        CurrentEventState.query
        .filter_by(uid=uid)
        .order_by(CurrentEventState.updated_at.desc())
        .all()
    )
    # return render_template("index.html", events=events, states=states)
    return render_template("index.html", events=events, states=states, event_config=EVENT_CONFIG, user=user)

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
    
    # Extract spCat for SpecialConsent / RevokeSpecialConsent (Art 9)
    spCat = request.form.get("spCat", "").strip().lower() if action in ("SpecialConsent", "RevokeSpecialConsent") else None

    # Extract fid for RequestErasure (Art 17); fid_old for RequestRectification (Art 16)
    fid = request.form.get("fid", "").strip() if action == "RequestErasure" else (
          request.form.get("fid_old", "").strip() if action == "RequestRectification" else None)

    # Extract fid_new for RequestRectification (Art 16)
    fid_new = request.form.get("fid_new", "").strip() if action == "RequestRectification" else None

    # Save the event locally in external_consent_platform.db
    e = Event(kind=action, uid=uid, purpose=purpose, spCat=spCat, fid=fid, fid_new=fid_new, status="pending")
    db.session.add(e)
    db.session.commit()

    # Update state only if configured
    state_change = evt_def.get("state_change")
    category = evt_def.get("category", "general")
    if state_change:
        # For SpecialConsent, include spCat in lookup to track per-category consent
        if spCat:
            s = CurrentEventState.query.filter_by(uid=uid, purpose=purpose, category=category, spCat=spCat).one_or_none()
        else:
            s = CurrentEventState.query.filter_by(uid=uid, purpose=purpose, category=category).one_or_none()

        if s:
            s.status = state_change
            s.updated_at = datetime.utcnow()
        else:
            db.session.add(CurrentEventState(uid=uid, purpose=purpose, category=category, spCat=spCat, status=state_change))
        db.session.commit()
    return redirect(url_for("index"))

@app.route("/withdraw_and_erase", methods=["POST"])
def withdraw_and_erase():
    """
    Art 17(1)(b): Withdraw all active consents (regular + special) then request erasure.
    Creates Revoke / RevokeSpecialConsent events followed by a RequestErasure event,
    with timestamps ordered so the poller processes withdrawals before the erasure request.
    """
    if "uid" not in session:
        flash("You must log in first.")
        return redirect(url_for("login"))

    uid = session["uid"]
    fid = request.form.get("fid", "").strip()
    if not fid:
        flash("File ID (fid) is required for erasure.")
        return redirect(url_for("index"))

    from datetime import timedelta
    base_time = datetime.utcnow()
    idx = 0

    # 1. Revoke all active regular consents
    active_consents = CurrentEventState.query.filter_by(
        uid=uid, category="consent", status="consented"
    ).all()
    for row in active_consents:
        e = Event(kind="Revoke", uid=uid, purpose=row.purpose, status="pending")
        e.created_at = base_time + timedelta(microseconds=idx)
        db.session.add(e)
        row.status = "revoked"
        row.updated_at = base_time + timedelta(microseconds=idx)
        idx += 1

    # 2. Revoke all active special consents (Art 9)
    active_special = CurrentEventState.query.filter_by(
        uid=uid, category="special_consent", status="special_consented"
    ).all()
    for row in active_special:
        e = Event(kind="RevokeSpecialConsent", uid=uid, purpose=row.purpose,
                  spCat=row.spCat, status="pending")
        e.created_at = base_time + timedelta(microseconds=idx)
        db.session.add(e)
        row.status = "special_revoked"
        row.updated_at = base_time + timedelta(microseconds=idx)
        idx += 1

    # 3. Request erasure (last, so all withdrawals are processed first)
    erasure = Event(kind="RequestErasure", uid=uid, fid=fid, purpose="", status="pending")
    erasure.created_at = base_time + timedelta(microseconds=idx)
    db.session.add(erasure)

    db.session.commit()

    flash(f"Withdrew {len(active_consents)} consent(s) and {len(active_special)} special consent(s). "
          f"Erasure requested for file {fid}.")
    return redirect(url_for("index"))

# --- Data request and download routes ---
@app.route("/my_data")
def my_data():
    if "uid" not in session:
        return redirect(url_for("login"))
    uid = session["uid"]
    try:
        resp = requests.get(f"http://127.0.0.1:7000/access_status/{uid}", timeout=3)
        info = resp.json()
    except Exception:
        info = {"ready": False}
    return render_template("my_data.html", info=info, uid=uid)

@app.route("/download_my_data")
def download_my_data():
    if "uid" not in session:
        return redirect(url_for("login"))
    uid = session["uid"]
    try:
        status = requests.get(f"http://127.0.0.1:7000/access_status/{uid}", timeout=3).json()
        if status.get("ready"):
            resp = requests.get(
                f"http://127.0.0.1:7000/access_download/{status['response_id']}", timeout=30)
            from flask import Response
            return Response(
                resp.content,
                mimetype="application/zip",
                headers={"Content-Disposition": f"attachment; filename=my_data_{uid}.zip"})
    except Exception as e:
        flash(f"Download failed: {e}")
    return redirect(url_for("my_data"))

@app.route("/upload_rectification", methods=["POST"])
def upload_rectification():
    """DS uploads corrected file here (port 5000); we proxy it to GDPRFS (port 7000)."""
    if "uid" not in session:
        return jsonify({"error": "not logged in"}), 401
    f = request.files.get("file")
    if not f:
        return jsonify({"error": "no file provided"}), 400
    import base64
    content_b64 = base64.b64encode(f.read()).decode()
    try:
        resp = requests.post(
            "http://127.0.0.1:7000/upload_rectification",
            json={"filename": f.filename, "content_b64": content_b64},
            timeout=10)
        return jsonify(resp.json()), resp.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    run_simple("127.0.0.1", 5000, app, use_reloader=True, use_debugger=True, threaded=True) # to enable running concurrently the poller with the Flask app, so that the DS can see the latest consent/revocation status without restarting the Flask app.
