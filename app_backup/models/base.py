from sqlalchemy import Column, Integer, DateTime, String
from sqlalchemy.sql import func
from sqlalchemy.ext.declarative import declared_attr
from ..db.database import Base
import uuid


class BaseModel(Base):
    """Base model with common fields"""
    __abstract__ = True
    
    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    @declared_attr
    def __tablename__(cls):
        return cls.__name__.lower()


class UUIDBaseModel(Base):
    """Base model with UUID primary key"""
    __abstract__ = True
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    @declared_attr
    def __tablename__(cls):
        return cls.__name__.lower()
