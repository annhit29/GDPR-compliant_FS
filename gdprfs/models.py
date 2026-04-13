from sqlalchemy import create_engine, Column, Integer, String, Boolean, ForeignKey, Text, Table
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

Base = declarative_base()

person_file_map = Table(
    "person_file_map", Base.metadata,
    Column("person_id", ForeignKey("person.id"), primary_key=True),
    Column("file_id", ForeignKey("file.id"), primary_key=True)
)

class File(Base):
    __tablename__ = "file"
    id = Column(Integer, primary_key=True)
    file_id = Column(String, unique=True, nullable=False)
    abs_path = Column(Text) # absolute path
    #timestamps:
    created_at = Column(String)
    modified_at = Column(String)
    accessed_at = Column(String)
    
    sha256 = Column(String(64), nullable=True) # for LLM
    special_categories = Column(Text, default="") # comma-separated GDPR Art 9 special data categories (e.g. "health,religious")

    last_action = Column(String) # "read", "write", "rename", etc.

    people = relationship("Person", secondary=person_file_map, back_populates="files")

class Person(Base):
    __tablename__ = "person"
    id = Column(Integer, primary_key=True)
    uid = Column(String, unique=True) # the user identifier field  # this field can be NULL for potential users
    first_name = Column(String)
    last_name = Column(String)
    registered = Column(Boolean, default=False)  # 0 = False  = potential user or not-yet-registered user, 1 = True = registered user
    files = relationship("File", secondary=person_file_map, back_populates="people")
    aliases = relationship("NameAlias", backref="person", cascade="all, delete") # list of NameAlias objects to allow the LLM auto-detects aliases

class PersonFileSpecialCategory(Base):
    """Per-person-per-file Art 9 special data categories.
    Tracks which special categories apply to which person in which file."""
    __tablename__ = "person_file_special_category"
    id = Column(Integer, primary_key=True)
    person_id = Column(Integer, ForeignKey("person.id"), nullable=False)
    file_id = Column(Integer, ForeignKey("file.id"), nullable=False)
    special_category = Column(String(32), nullable=False)  # e.g. "health", "genetic"

    person = relationship("Person")
    file = relationship("File")

class ProcessingRecord(Base):
    """Art 30: Records of processing activities.
    Each row is one Record(pr, c, a, p, v) event caused by the enforcer."""
    __tablename__ = "processing_record"
    id = Column(Integer, primary_key=True, autoincrement=True)
    processor = Column(String, nullable=False)
    controller = Column(String, nullable=False)
    activity = Column(String, nullable=False)
    property = Column(String, nullable=False)
    value = Column(String, nullable=False)
    timestamp = Column(String, nullable=False)

class NameAlias(Base):
    __tablename__ = "alias_person_map"

    id = Column(Integer, primary_key=True)
    alias = Column(String, unique=True, nullable=False) # all in lowercase, for easy matching
    person_id = Column(Integer, ForeignKey("person.id"), nullable=False)

# Shared engine + session
# ENGINE = create_engine("sqlite:///gdprfs.db")
ENGINE = create_engine("sqlite:////home/ann20010929/MA3/Building_a_GDPR-compliant_file_system/instrlib/gdprfs.db")
Session = sessionmaker(bind=ENGINE)
# print("[GDPRFS] Using DB at:", ENGINE.url)

# Ensure all tables exist (safe to call repeatedly — only creates missing tables)
Base.metadata.create_all(ENGINE)

# Always print the DB path on import (once per process)
print(f"[GDPRFS] Using GDPRFS database at: {ENGINE.url}")