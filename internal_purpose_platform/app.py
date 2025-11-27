import sys, os
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from gdprfs.models import Person

from pathlib import Path
from flask import Flask, render_template, request, redirect, url_for, session, flash
# from gdprfs.merge_alerts import load_merge_alerts
from models import db, InternalUser, CurrentSession
import requests, yaml, os
import json
from sqlalchemy import func

"""
Main Flask app (with signup/login/logout + StartSession/StopSession routes).
"""
# --- Flask Setup ---
app = Flask(__name__)
app.secret_key = os.urandom(24)

app.config["SESSION_COOKIE_NAME"] = "internal_session"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///internal_purpose_platform.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db.init_app(app)

with app.app_context():
    db.create_all()

def merge_person_into(s, dup_person, registered_person):
    """Merge duplicated external user dup_person into registered external user registered_person in the given session `s`."""
    # Move file mappings
    for f in dup_person.files:
        if registered_person not in f.people:
            f.people.append(registered_person)
        if dup_person in f.people:
            f.people.remove(dup_person)

    # Delete duplicate
    s.delete(dup_person)

# --- Load reasons.yaml ---
REASONS_PATH = os.path.join(os.path.dirname(__file__), "purposes_and_reasons.yaml")
with open(REASONS_PATH, "r") as f:
    PURPOSES = yaml.safe_load(f)

MERGE_ALERT_FILE = Path("/home/ann20010929/MA3/Building_a_GDPR-compliant_file_system/instrlib/merge_alerts.json")
def load_merge_alerts():
    if not MERGE_ALERT_FILE.exists():
        return None
    try:
        return json.loads(MERGE_ALERT_FILE.read_text())
    except Exception:
        return None
    
@app.route("/merge_alerts")
def merge_alerts():
    if "uid" not in session:
        return redirect(url_for("login"))

    user = InternalUser.query.filter_by(uid=session["uid"]).first()
    current = CurrentSession.query.filter_by(uid=user.uid, active=True).first()

    alerts_data = load_merge_alerts()
    alerts = alerts_data["alerts"] if alerts_data else None

    return render_template(
        "index.html",
        user=user,
        current=current,
        purposes=PURPOSES,
        merge_alerts=alerts
    )


@app.post("/resolve_merge")
def resolve_merge():
    alias = request.form["alias"].strip().lower()
    person_id = int(request.form["person_id"])
    action = request.form["action"]

    from gdprfs.db_utils import Session
    from gdprfs.models import NameAlias

    if action == "merge":
        with Session() as s:
            registered_person = s.query(Person).get(person_id)

            # 1. Store alias → canonical person_id mapping (see NameAlias model and name_aliases table)
            existing = s.query(NameAlias).filter_by(alias=alias).first()
            if not existing:
                # then store alias → person link
                new_alias = NameAlias(alias=alias, person_id=person_id)
                s.add(new_alias)
                s.commit()
            # else: do nothing → alias already stored

            # 2. Find duplicates to merge
            dup = (
                s.query(Person)
                .filter(Person.id != registered_person.id)
                .filter(
                    (func.lower(Person.first_name) == alias.lower()) |
                    (func.lower(Person.last_name) == alias.lower())
                )
                .first()
            )



            if dup and dup.id != registered_person.id:
                merge_person_into(s, dup, registered_person)
                s.commit()
            #else: no duplicate found → nothing to merge
            
    # Remove this alert from the merge_alerts.json file
    data = load_merge_alerts()
    if data:
        new_alerts = [
            a for a in data["alerts"]
            if a["alias"].lower() != alias 
            # if not (a["alias"].lower() == alias and a["person_id"] == person_id)
        ]

        if new_alerts:
            MERGE_ALERT_FILE.write_text(json.dumps({
                "file": data["file"],
                "alerts": new_alerts
            }, indent=2))
        else:
            MERGE_ALERT_FILE.unlink(missing_ok=True)

    return redirect("/merge_alerts")

# --- Authentication Routes ---
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        uid = request.form["uid"].strip()
        first = request.form["first_name"].strip()
        last = request.form["last_name"].strip()
        pwd = request.form["password"]

        if InternalUser.query.filter_by(uid=uid).first():
            return "User already exists", 400

        u = InternalUser(uid=uid, first_name=first, last_name=last)
        u.set_password(pwd)
        db.session.add(u)
        db.session.commit()
        return redirect(url_for("login"))
    return render_template("signup.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        uid = request.form["uid"].strip()
        pwd = request.form["password"]
        u = InternalUser.query.filter_by(uid=uid).first()
        if not u or not u.check_password(pwd):
            return "Invalid credentials", 401
        session["uid"] = uid
        return redirect(url_for("index"))
    return render_template("login.html")

@app.route("/logout", methods=["POST"])
def logout():
    uid = session.get("uid")
    if uid:
        # Stop any active session for this user
        current = CurrentSession.query.filter_by(uid=uid, active=True).first()
        if current: # if there's an active session
            current.active = False # then stop it
            db.session.commit()
            print(f"[Internal] Auto-stopped active session for {uid} on logout")

            # Notify FUSE as well
            try:
                payload = {"kind": "StopSession", "uid": uid}
                requests.post("http://127.0.0.1:7000/ingest", json=payload, timeout=2) # timeout after 2s if FUSE is down
                print(f"[Internal] Sent StopSession({uid}) → FUSE on logout")
            except Exception as e:
                print(f"[WARN] Failed to notify FUSE on logout: {e}")

    # Clear the web session
    session.clear()
    return redirect(url_for("login"))

# --- Main Page Routes ---
@app.route("/")
def index():
    if "uid" not in session:
        return redirect(url_for("login"))
    user = InternalUser.query.filter_by(uid=session["uid"]).first()
    current = CurrentSession.query.filter_by(uid=user.uid, active=True).first()
    # return render_template("index.html", user=user, purposes=PURPOSES, current=current)
    alerts = load_merge_alerts()
    return render_template(
        "index.html",
        user=user,
        purposes=PURPOSES,
        current=current,
        merge_alerts=alerts["alerts"] if alerts else None
    )
# --- Start/Stop session endpoints ---
@app.route("/start_session", methods=["POST"])
def start_session():
    uid = session.get("uid")
    purpose = request.form["purpose"]
    reason = request.form["reason"]

    # Stop old session if exists
    old = CurrentSession.query.filter_by(uid=uid, active=True).first()
    if old:
        old.active = False
        db.session.commit()

        # Notify FUSE that old session has ended/stopped:
        payload = {"kind": "StopSession", "uid": uid}
        try:
            requests.post("http://127.0.0.1:7000/ingest", json=payload, timeout=2)
            print(f"[Internal] Sent StopSession({uid}) before new StartSession.")
        except Exception as e:
            print(f"[WARN] StopSession notify failed: {e}")

    # Start a new session
    s = CurrentSession(uid=uid, purpose=purpose, reason=reason, active=True)
    db.session.add(s)
    db.session.commit()

    # Notify FUSE
    payload = {"kind": "StartSession", "uid": uid, "purpose": purpose, "reason": reason}
    try:
        res = requests.post("http://127.0.0.1:7000/ingest", json=payload, timeout=2)
        res.raise_for_status()
        print(f"[Internal] Sent StartSession({uid}, {purpose}, {reason}) → FUSE")
    except Exception as e:
        print(f"[WARN] Failed to send StartSession: {e}")

    return redirect(url_for("index"))

@app.route("/stop_session", methods=["POST"])
def stop_session():
    uid = session.get("uid")

    # Mark current session inactive
    current = CurrentSession.query.filter_by(uid=uid, active=True).first()
    if not current: # if the session is already inactive
        print(f"[Internal] No active session to stop for {uid}. Skipping.") #print to FUSE terminal
        flash("No active session to stop.") #print to internal interface

        return redirect(url_for("index"))  # this means: no FUSE notify, no DB update

    # else: Mark inactive
    current.active = False
    db.session.commit()

    # if current:
    #     current.active = False
    #     db.session.commit()
    
    # Notify FUSE
    payload = {"kind": "StopSession", "uid": uid}
    try:
        res = requests.post("http://127.0.0.1:7000/ingest", json=payload, timeout=2)
        res.raise_for_status()
        print(f"[Internal] Sent StopSession({uid}) → FUSE")
    except Exception as e:
        print(f"[WARN] Failed to send StopSession: {e}")

    return redirect(url_for("index"))

if __name__ == "__main__":
    app.run("127.0.0.1", 8000, debug=True)
