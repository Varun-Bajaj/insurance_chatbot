from sqlalchemy import Column, String, Integer, ForeignKey, DateTime
from .base_model import *
from datetime import datetime, timezone


class User(Base):
    __tablename__ = "User"
    user_id = Column(String(128), primary_key=True, index=True)
    username = Column(String(128))
    password = Column(String(128))
    created_date = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)