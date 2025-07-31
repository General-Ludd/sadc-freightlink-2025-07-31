from sqlalchemy.ext.declarative import as_declarative
from sqlalchemy import Column, Integer, String, DateTime, func

@as_declarative()
class Base:
    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())