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

    #todo: last or all, à voir
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

class NameAlias(Base):
    __tablename__ = "name_alias"

    id = Column(Integer, primary_key=True)
    alias = Column(String, unique=True, nullable=False)
    person_id = Column(Integer, ForeignKey("person.id"), nullable=False)

# Shared engine + session
# ENGINE = create_engine("sqlite:///gdprfs.db")
ENGINE = create_engine("sqlite:////home/ann20010929/MA3/Building_a_GDPR-compliant_file_system/instrlib/gdprfs.db")
Session = sessionmaker(bind=ENGINE)
print("[GDPRFS] Using DB at:", ENGINE.url)
