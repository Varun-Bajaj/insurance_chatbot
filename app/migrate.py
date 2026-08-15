import os
import sys
import traceback
from sqlalchemy import create_engine
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
from urllib.parse import quote
from settings.setting import *
from Model.userclient_model import *
from Model.token_model import *
from Model.user_model import *
from Model.client_model import *
from Model.base_model import *
from Model.modeldetails_model import *


DB_URL = f"mysql+mysqlconnector://{db_user}:%s@{db_url}:3306/{db_name}" % quote(
    db_pass)
engine = create_engine(DB_URL, pool_pre_ping=True, echo=True)
SessionLocal = sessionmaker(autoflush=False, autocommit=False, bind=engine)


sys.path.append(os.getcwd())


def migrate_sa_model(target_db, source_db, sa_model):
    """
    Migrates given sqlalchemy model to new db
    :param sa_model: sqlalchemy model which needs to be migrated new db
    :param target_db: where data will be inserted
    :param source_db: from where data will be retrieved
    :return:
    """
    print(f"migrating model: {sa_model.__name__}, table name: {sa_model.__tablename__}")
    query = sa.select(sa_model)
    for row in source_db.execute(query).all():
        print(f"migrating: {row[0]} to new db")
        dict_obj = {key: value for key, value in row[0].__dict__.items() if not key.startswith("_")}
        print(f"dict object: {dict_obj}")
        source_obj = sa_model(**dict_obj)
        target_db.add(source_obj)
        target_db.flush([source_obj])


if __name__ == "__main__":

    _target_db = SessionLocal()
   # _source_db = source_session()

    try:
        # set of models which needs to be migrated, make sure models follow hierarchy else
        # MySQL will raise Foreign Key Integrity Constrain Error
        model_set = [
            User, Client, UserClient, Token, Details
        ]
        Base.metadata.bind = engine
        Base.metadata.create_all(engine, checkfirst=True)
        # for model in model_set:
        #     migrate_sa_model(_target_db, _source_db, model)
        print(f"all models migrated, issuing session commit")
        _target_db.commit()
    except Exception as er:
        _target_db.rollback()
        print(f"failed to migrate table data: {er}, rollback issued")
        traceback.print_exc()
        raise er
    finally:
        _target_db.close()
