from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, Text, Table
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
    
    #todo: last or all, à voir
    last_action = Column(String) # "read", "write", "rename", etc.

    deleted = Column(Integer, default=0) # 0 = file exists aka not deleted, 1 = file deleted

    people = relationship("Person", secondary=person_file_map, back_populates="files")

class Person(Base):
    __tablename__ = "person"
    id = Column(Integer, primary_key=True)
    first_name = Column(String)
    last_name = Column(String)
    files = relationship("File", secondary=person_file_map, back_populates="people")

# Shared engine + session
ENGINE = create_engine("sqlite:///gdprfs.db")
Session = sessionmaker(bind=ENGINE)
