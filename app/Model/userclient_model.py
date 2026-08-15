from sqlalchemy import Column, String, Integer, ForeignKey, DateTime
from .base_model import Base
from .user_model import *
from .client_model import *


class UserClient(Base):
    __tablename__ = "User_Client"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(128), ForeignKey("User.user_id"))
    client_id = Column(String(128), ForeignKey("Client.client_id"))
    num_api_calls = Column(Integer, default=0)
