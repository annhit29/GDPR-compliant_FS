from datetime import datetime
from pathlib import Path
from gdprfs.models import Base, ENGINE, Session, File, Person

# --- Setup the database ---
Base.metadata.create_all(ENGINE)
session = Session()

if not session.query(Person).count():  # only initialize once
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # absolute paths (these files might exist or will be created later)
    # Note: theese are just metadata placeholders.
    file_a_path = Path("/var/lib/gdprfs/upper/enrollment_2025.csv").resolve()
    file_b_path = Path("/var/lib/gdprfs/upper/course_feedback_report.pdf").resolve()
    file_c_path = Path("/var/lib/gdprfs/upper/student_activity_log.json").resolve()
    
    # files with metadata
    file_a = File(
        file_id="enrollment_2025.csv",
        abs_path=str(file_a_path),
        created_at=now,
        modified_at=now,
        accessed_at=now,
        last_action="write",
    )

    file_b = File(
        file_id="course_feedback_report.pdf",
        abs_path=str(file_b_path),
        created_at=now,
        modified_at=now,
        accessed_at=now,
        last_action="write",
    )

    file_c = File(
        file_id="student_activity_log.json",
        abs_path=str(file_c_path),
        created_at=now,
        modified_at=now,
        accessed_at=now,
        last_action="write",
    )

    p1 = Person(first_name="François", last_name="Hublet", files=[file_a])
    p2 = Person(first_name="Wei-En", last_name="Hsieh", files=[file_b])
    p3 = Person(first_name="John", last_name="Doe", files=[file_c])

    session.add_all([file_a, file_b, file_c, p1, p2, p3])
    session.commit()
    print("[DB] Initial data inserted")
else:
    print("[DB] Database already initialized")

session.close()