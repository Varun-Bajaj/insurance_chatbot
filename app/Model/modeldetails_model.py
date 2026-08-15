# Import necessary modules and classes
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from .base_model import Base

from .analysis_model import *

# Database model
class Details(Base):
    __tablename__ = "ModelDetails"
    id = Column(Integer, primary_key=True, index=True)
    vid = Column(Integer, index=True)
    name = Column(String(128))
    datasets = Column(String(128))
    approach = Column(String(255))
    inuse = Column(Boolean)
    created_date = Column(DateTime, default=datetime.utcnow)
    ## Relationships
    analysis = relationship('Analysis', back_populates='details')
