import sqlalchemy
from sqlalchemy import Column, String
from .base_model import Base


class Client(Base):
    __tablename__ = "Client"
    client_id = Column(String(128), primary_key=True, index=True)
    client_name = Column(String(256))