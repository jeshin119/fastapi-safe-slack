from sqlalchemy import Column, Integer, Text, DateTime, ForeignKey, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base

class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True, index=True)
    channel_id = Column(Integer, ForeignKey("channels.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    content = Column(Text)
    message_type = Column(String, default="text")
    reply_to = Column(Integer, ForeignKey("messages.id"), nullable=True)
    mentions = Column(Text, nullable=True)  # JSON 형태로 저장
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    # 관계
    channel = relationship("Channel", back_populates="messages")
    user = relationship("User", back_populates="messages")
    reply_message = relationship("Message", remote_side=[id]) 