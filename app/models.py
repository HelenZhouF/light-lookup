import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Integer, Boolean, Text, ForeignKey
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import relationship

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

    contents = relationship("Content", back_populates="domain", cascade="all, delete-orphan")


class ContentStatus(str):
    DEVELOPING = "developing"
    CANDIDATE = "candidate"
    PRODUCTION = "production"


class ContentStanding(str):
    FUTURE = "future"
    CURRENT = "current"
    LEGACY = "legacy"


class Content(Base):
    __tablename__ = "contents"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    label = Column(String(255), nullable=False)
    status = Column(String(50), nullable=False, default="developing")
    standing = Column(String(50), nullable=False, default="future")
    majorNumber = Column(Integer, nullable=False, default=1)
    minorNumber = Column(Integer, nullable=False, default=0)
    activationStatus = Column(String(50), nullable=False, default="active")
    productionStartTime = Column(DateTime, nullable=True)
    productionEndTime = Column(DateTime, nullable=True)
    creationTimeStamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    modifiedTimeStamp = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    createdBy = Column(String(255), nullable=True)
    modifiedBy = Column(String(255), nullable=True)
    version = Column(Integer, default=1, nullable=False)

    domainId = Column(String, ForeignKey("domains.id"), nullable=False)
    domain = relationship("Domain", back_populates="contents")

    entries = relationship("Entry", back_populates="content", cascade="all, delete-orphan")


class Entry(Base):
    __tablename__ = "entries"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    key = Column(String(255), nullable=True)
    value = Column(Text, nullable=False)
    disabled = Column(Boolean, default=False, nullable=False)
    sequence = Column(Integer, default=0, nullable=False)
    folderPath = Column(String(1024), nullable=True)
    creationTimeStamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    modifiedTimeStamp = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    createdBy = Column(String(255), nullable=True)
    modifiedBy = Column(String(255), nullable=True)
    version = Column(Integer, default=1, nullable=False)

    contentId = Column(String, ForeignKey("contents.id"), nullable=False)
    content = relationship("Content", back_populates="entries")
