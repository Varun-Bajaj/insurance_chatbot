from sqlalchemy import Column, String, Integer, ForeignKey, DateTime
from .base_model import *
from datetime import datetime, timedelta


class Token(Base):
    __tablename__ = "Token"
    id = Column(Integer, primary_key=True, index=True)
    token = Column(String(3000), index=True)
    client_id = Column(String(128), ForeignKey("Client.client_id"))
    user_id = Column(String(128), ForeignKey("User.user_id"))
    expires_at = Column(DateTime)
    created_date = Column(DateTime, default=datetime.utcnow)

