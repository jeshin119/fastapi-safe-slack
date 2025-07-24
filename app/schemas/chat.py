from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class ChatMessage(BaseModel):
    content: str
    message_type: str = "text"  # text, file, emoji
    reply_to: Optional[int] = None
    mentions: Optional[List[int]] = None

class ChatMessageResponse(BaseModel):
    message_id: int
    content: str
    user_id: int
    user_name: str
    message_type: str
    reply_to: Optional[int] = None
    mentions: Optional[List[int]] = None
    timestamp: datetime
    workspace_id: int
    channel_id: int

class WebSocketMessage(BaseModel):
    type: str  # message, typing, read_receipt
    content: Optional[str] = None
    message_type: str = "text"
    reply_to: Optional[int] = None
    mentions: Optional[List[int]] = None

class WebSocketResponse(BaseModel):
    type: str  # message, user_joined, user_left, typing, connection
    message_id: Optional[int] = None
    content: Optional[str] = None
    user_id: Optional[int] = None
    user_name: Optional[str] = None
    message_type: Optional[str] = None
    reply_to: Optional[int] = None
    mentions: Optional[List[int]] = None
    timestamp: str
    connected_users: Optional[List[dict]] = None 