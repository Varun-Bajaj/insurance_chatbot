from sqlalchemy import Column, String, Integer, ForeignKey, DateTime
from sqlalchemy import delete
from datetime import datetime, timedelta
from passlib.context import CryptContext
from jose import jwt, JWTError, ExpiredSignatureError
from sqlalchemy.orm import Session
from api.deps import SessionLocal
from logs.logger_setup import setup_logger
from settings.setting import *
from Model.client_model import *
from Model.token_model import *
from Model.user_model import *
from Model.userclient_model import *


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

logger = setup_logger("auth_model_logger")

def get_client_id():
    client_ids = []
    db = SessionLocal()
    try:
        client_data = db.query(Client).all()
        for data in client_data:
            client_ids.append(data.client_id)
        return client_ids
    except:
        logger.exception("Exception to get client ids")
        return client_ids
    finally:
        logger.info("closing database connection")
        db.close()


def revoke_jwt_token(token, db: Session) -> None:
    try:
        # Check if the token exists in the database
        token_query = delete(Token).filter(Token.token == token)
        db.execute(token_query)
        db.commit()
    except:
        logger.exception(f"Exception in revoke token for token:{token}")


def revoke_jwt_token_user(user_id, client_id, db: Session) -> None:
    try:
        # Check if the token exists in the database
        token_query = delete(Token).filter(Token.user_id == user_id and Token.client_id == client_id)
        db.execute(token_query)
        db.commit()
    except:
        logger.exception(f"Exception in revoke token for user_id:{user_id} and client_id:{client_id}")


def save_token(token: str, client_id: int, user_id: int, db: Session) -> bool:
    try:
        token_exist = db.query(Token).filter(Token.user_id == user_id, Token.client_id == client_id).all()
        if token_exist:
            revoke_jwt_token_user(user_id, client_id, db=db)
        db_token = Token(
            token=token,
            client_id=client_id,
            user_id=user_id,
            expires_at=datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
        )
        db.add(db_token)
        db.commit()
        return True
    except:
        logger.exception("Exception to save token")
        return False


def create_user_access(user_id, client_id, db: Session):
    try:
        # Check if the user and client exist
        user = db.query(User).filter(User.user_id == user_id).first()
        client = db.query(Client).filter(Client.client_id == client_id).first()
        if not user or not client:
            logger.error(f"user or client not found for user_id:{user_id} or client_id:{client_id}")
            return False

        # Check if the user already has access to the client
        existing_access = db.query(UserClient).filter(UserClient.user_id == user_id, UserClient.client_id == client_id).all()
        if existing_access:
            logger.info(f"User:{user_id} already have access to client:{client_id}")
            return True
        # Create user access to the client
        user_client = UserClient(user_id=user_id, client_id=client_id)
        db.add(user_client)
        db.commit()
        return True
    except:
        logger.exception("Exception in create user access,")
        return False


def authenticate_user(user_id: str, password: str, client_id: str, db: Session) -> (bool, [int, None]):

    db_user = db.query(User).filter(User.user_id == user_id).first()
    if not db_user:
        logger.error(f"User_id:{user_id} Not Found")
        return False, 105

    if not pwd_context.verify(password, db_user.password):
        logger.error(f"Invalid password for user_id :{user_id}")
        return False, 106

    user_client = db.query(UserClient).filter(UserClient.user_id == db_user.user_id,
                                              UserClient.client_id == client_id).first()
    if not user_client:
        return False, 107
    return True, user_client.client_id


def validate_jwt_token(token: str, db: Session) -> (bool, [tuple, None]):
    try:
        try:
            payload = jwt.decode(token, key=JWT_TOKEN_KEY, algorithms=[ALGORITHM])
            # payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        except ExpiredSignatureError:
            logger.exception("token is expired!!")
            revoke_jwt_token(token, db=db)
            return False, 108
        except JWTError:
            logger.exception(f"Token is invalid")
            return False, None

        decoded_user_id: str = payload.get("user_id", None)
        decoded_client_id: str = payload.get("client_id", None)
        if decoded_user_id is None or decoded_client_id is None:
            logger.error(f"token is invalid token:{token}")
            return False, None

        # Check if the token exists in the database for the given user and client
        data = db.query(Token).filter(Token.user_id == decoded_user_id, Token.client_id == decoded_client_id).all()
        if not data:
            logger.error(f"Not able to find token for given user_id:{decoded_user_id} and client_id:{decoded_client_id}")
            return False, None
        for d in data:
            if d.token == token:
                result = (db.query(UserClient).
                          filter(UserClient.user_id == decoded_user_id, UserClient.client_id == decoded_client_id).
                          update({UserClient.num_api_calls: UserClient.num_api_calls + 1}, synchronize_session=False))
                db.commit()

                return True, (decoded_client_id, decoded_user_id)
        logger.exception(f"token is not validate for client_id:{decoded_client_id} and user_id:{decoded_user_id}")
        return False, None
    except:
        logger.exception("Exception in validate_jwt_token")
        return False, None


def register_client(client_id, client_name, db: Session):
    try:
        db_client = db.query(Client).filter(Client.client_id == client_id).first()
        if not db_client:
            db_client = Client(client_id=client_id, client_name=client_name)
            db.add(db_client)
            db.commit()
        return True
    except:
        logger.exception(f"Exception to add entry for client_id:{client_id}, clinent_name:{client_name}")
        return False


def register_user(user_id, username, password, db: Session):
    try:
        hashed_password = pwd_context.hash(password)
        db_user = db.query(User).filter(User.user_id == user_id).first()
        if not db_user:
            db_user = User(user_id=user_id, username=username, password=hashed_password)
            db.add(db_user)
            db.commit()
        return True
    except:
        logger.exception("Exception in register User")
        return False
