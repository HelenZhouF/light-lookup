import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Integer, Boolean, Text
from sqlalchemy.dialects.sqlite import JSON

from .database import Base


class Domain(Base):
    __tablename__ = "domains"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), unique=True, index=True, nullable=False)
    description = Column(Text, nullable=True)
    domainType = Column(String(50), nullable=False)
    checkOut = Column(Boolean, default=False, nullable=False)
    creationTimeStamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    modifiedTimeStamp = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    createdBy = Column(String(255), nullable=True)
    modifiedBy = Column(String(255), nullable=True)
    version = Column(Integer, default=1, nullable=False)
    properties = Column(JSON, nullable=True)
