from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from settings.setting import *
from urllib.parse import quote

# DB_URL = "mysql+mysqlconnector://{}:{}@{}:{}/{}".format('root', 'Root@123',
#                                            'localhost', '3306', 'patient_no_show')
DB_URL = f"mysql+mysqlconnector://{db_user}:%s@{db_url}:3306/{db_name}" % quote(db_pass)
engine = create_engine(DB_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autoflush=False, autocommit=False, bind=engine)


def get_db() -> Generator:
    db = None
    try:
        db = SessionLocal()
        # Since SQL Alchemy uses lazy initializing
        #   db connection is never opened here
        yield db
    except Exception as e:
        print(e)
        raise e
    finally:
        db.close()
