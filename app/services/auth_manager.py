from jose import jwt
from datetime import timedelta, datetime
from utilities.encryption import password_encrypt, password_decrypt
from sqlalchemy.orm import Session
from dao.chatbot_dao import *
from dao.auth_dao import *
from settings.setting import *
from logs.logger_setup import setup_logger



class Manager:
    def __init__(self):
        self.logger = setup_logger("manager_logger")

    @staticmethod
    def create_jwt_token(userid: str, client_id: str) -> str:
        expires_delta = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES * 60)
        return jwt.encode({"client_id": client_id, "user_id": userid, "exp": datetime.utcnow() + expires_delta},
                          SECRET_KEY, algorithm=ALGORITHM)

    def get_token(self, user_id, password, client_id, db: Session):
        try:
            decrypt_pass = password_decrypt(password.encode(), PASSWORD_SECRET, self.logger)
            status, code_or_client_id = authenticate_user(user_id, decrypt_pass, client_id, db=db)
            if not status:
                self.logger.error(f"Error occurred in authenticate user:{user_id}, code:{code_or_client_id}")
                return False, code_or_client_id
            # update_user_login_info(db, db_user)
            token = Manager.create_jwt_token(user_id, code_or_client_id)
            status = save_token(token, code_or_client_id, user_id, db=db)
            if not status:
                self.logger.exception(f"Not able to create token for given userid:{user_id}")
                return False, 103
            return True, token
        except:
            self.logger.exception("Exception in get_token")
            return False, 103

    def validate_token(self, token, db: Session):
        status, data = validate_jwt_token(token, db=db)
        if status:
            return True, data
        self.logger.warning(f"Token:{token} is invalid")
        return status, None

    def register_client_(self, client_id, client_name, db: Session):
        status = register_client(client_id, client_name, db=db)
        if not status:
            self.logger.error(f"Error in registering client {client_name}, {client_id}")
            return False, 103
        self.logger.info(f"client {client_name}, {client_id} successfully registered.")
        return True, 200

    def register_user_(self, user_id, username, password, db: Session):
        encrypt_pass = password_encrypt(password, PASSWORD_SECRET)
        status = register_user(user_id, username, password, db=db)
        if not status:
            self.logger.error(f"Error in registering User {username}, {user_id}")
            return False, 103
        self.logger.info(f"User {user_id}, {username} successfully registered.")
        return True, {"user_id": user_id, "username": username, "password": encrypt_pass}

    def give_user_access(self, user_id, client_id, db: Session):
        status = create_user_access(user_id, client_id, db=db)
        if not status:
            self.logger.error(f"Error in giving access to  User {user_id} for client {client_id}")
            return False, 103
        self.logger.info(f"Gave access to User {user_id} for client {client_id}")
        return True, 200
