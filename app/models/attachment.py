from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.core.base import Base
from datetime import datetime


class Attachment(Base):
    __tablename__ = "attachments"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    entity_type = Column(String(50), nullable=False)   # "user", "workout", "progress"
    entity_id = Column(Integer, nullable=False, index=True)
    filename = Column(String(255), nullable=False)
    s3_key = Column(String(512), nullable=False, unique=True)
    content_type = Column(String(100), nullable=False)
    size = Column(Integer, nullable=False)             # bytes
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="attachments")
