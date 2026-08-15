# Import necessary modules and classes
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime
import sqlalchemy
from .user_model import *
from .base_model import Base
from sqlalchemy import Index
from .modeldetails_model import *


class Analysis(Base):
    __tablename__ = "AnalysisModel"
    id = Column(Integer, primary_key=True, index=True)

    question = Column(Text, index=True)
    answer = Column(Text)
    rating = Column(Integer)
    comment = Column(Text)
    created_date = Column(DateTime, default=datetime.utcnow)
    user_id = Column(String(128), ForeignKey('User.user_id', ondelete='CASCADE'))
    model_id = Column(Integer, ForeignKey('ModelDetails.id', ondelete='CASCADE'))
    ## Relationships
    details = relationship('Details', back_populates='analysis')
    user = relationship('User', back_populates='analysis')
    # Explicit index creation with prefix length
    __table_args__ = (
        Index('ix_AnalysisModel_question', question, mysql_length=255),  # 255 is the prefix length
    )


## Relationships
User.analysis = relationship('Analysis', back_populates='user', cascade="all, delete-orphan")

