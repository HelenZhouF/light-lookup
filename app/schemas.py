from datetime import datetime
from typing import Optional, Dict, Any, List
from enum import Enum
from pydantic import BaseModel, Field, field_validator


class DomainType(str, Enum):
    lookup = "lookup"
    valueList = "valueList"


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
