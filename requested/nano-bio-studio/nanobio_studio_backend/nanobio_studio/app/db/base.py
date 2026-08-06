"""
SQLAlchemy declarative base for all ORM models.
"""
from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, DateTime, func
from datetime import datetime

Base = declarative_base()


class TimestampMixin:
    """Mixin to add created_at and updated_at timestamps to models."""
    
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
