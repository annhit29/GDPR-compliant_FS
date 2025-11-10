from datetime import datetime
from pathlib import Path
from models import Base, ENGINE, Session, File, Person

# --- Setup the database ---
Base.metadata.create_all(ENGINE) #create empty tables of gdprfs/models.py
print("[DB] gdprfs.db's tables (empty) initialized successfully.")

session = Session() # open a session to create initial data

if not session.query(Person).count():  # only initialize once
    potential_users = [
        {"first_name": "François", "last_name": "Hublet"},
        {"first_name": "Wei-En", "last_name": "Hsieh"},
        {"first_name": "John", "last_name": "Doe"},
        {"first_name": "David", "last_name": "Basin"},
        {"first_name": "Alan", "last_name": "Turing"},
    ]

    for user in potential_users:
        p = Person(
            uid=None,               # they haven’t registered yet
            first_name=user["first_name"],
            last_name=user["last_name"],
            registered=False,       # mark them as potential users
        )
        session.add(p)

    session.commit()
    print(f"[DB] Added {len(potential_users)} potential users.")
else:
    print("[DB] Database already initialized")

session.close()