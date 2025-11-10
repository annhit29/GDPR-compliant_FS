from models import Base, ENGINE

if __name__ == "__main__":
    Base.metadata.create_all(ENGINE)
    print("[DB] gdprfs.db's tables initialized successfully.")
