from datetime import datetime
from typing import Optional, Dict, Any, List
from enum import Enum
from pydantic import BaseModel, Field, field_validator


class DomainType(str, Enum):
    lookup = "lookup"
    valueList = "valueList"


class ContentStatus(str, Enum):
    developing = "developing"
    candidate = "candidate"
    production = "production"


class ContentStanding(str, Enum):
    future = "future"
    current = "current"
    legacy = "legacy"


class Link(BaseModel):
    href: str
    method: str
    uri: str
    type: str


class DomainBase(BaseModel):
    name: str = Field(..., max_length=255)
    description: Optional[str] = None
    domainType: DomainType
    createdBy: Optional[str] = None
    modifiedBy: Optional[str] = None
    properties: Optional[Dict[str, Any]] = None


class DomainCreate(DomainBase):
    pass


class DomainUpdate(BaseModel):
    description: Optional[str] = None
    modifiedBy: Optional[str] = None
    properties: Optional[Dict[str, Any]] = None


class Domain(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    domainType: str
    checkOut: bool
    creationTimeStamp: datetime
    modifiedTimeStamp: datetime
    createdBy: Optional[str] = None
    modifiedBy: Optional[str] = None
    version: int
    properties: Optional[Dict[str, Any]] = None
    _links: Optional[Dict[str, Link]] = None

    class Config:
        from_attributes = True


class DomainCollection(BaseModel):
    items: List[Domain]
    start: int
    limit: int
    count: int
    _links: Optional[Dict[str, Link]] = None


class ContentBase(BaseModel):
    label: str = Field(..., max_length=255)
    status: ContentStatus = ContentStatus.developing
    createdBy: Optional[str] = None
    modifiedBy: Optional[str] = None


class ContentCreate(ContentBase):
    pass


class ContentUpdate(BaseModel):
    label: Optional[str] = Field(None, max_length=255)
    status: Optional[ContentStatus] = None
    modifiedBy: Optional[str] = None

    model_config = {"extra": "forbid"}


class Content(BaseModel):
    id: str
    label: str
    status: str
    standing: str
    majorNumber: int
    minorNumber: int
    activationStatus: str
    creationTimeStamp: datetime
    modifiedTimeStamp: datetime
    createdBy: Optional[str] = None
    modifiedBy: Optional[str] = None
    version: int
    domainId: str
    _links: Optional[Dict[str, Link]] = None

    class Config:
        from_attributes = True


class ContentCollection(BaseModel):
    items: List[Content]
    start: int
    limit: int
    count: int
    _links: Optional[Dict[str, Link]] = None
