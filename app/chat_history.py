import json
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from datetime import datetime
from .database import ChatMessage, User

class ChatHistoryManager:
    """Manage user chat history with database persistence"""
    
    def save_message(self, db: Session, user_id: int, message: str, response: str, sources: List[Dict] = None):
        """Save a chat message to the database"""
        try:
            # Convert sources to JSON string
            sources_json = json.dumps(sources) if sources else None
            
            # Create chat message record
            chat_message = ChatMessage(
                user_id=user_id,
                message=message,
                response=response,
                sources=sources_json,
                created_at=datetime.utcnow()
            )
            
            db.add(chat_message)
            db.commit()
            db.refresh(chat_message)
            
            return chat_message.id
            
        except Exception as e:
            db.rollback()
            raise Exception(f"Error saving chat message: {str(e)}")
    
    def get_user_history(self, db: Session, user_id: int, limit: int = 50) -> List[Dict]:
        """Get user's chat history"""
        try:
            messages = db.query(ChatMessage).filter(
                ChatMessage.user_id == user_id
            ).order_by(
                ChatMessage.created_at.desc()
            ).limit(limit).all()
            
            history = []
            for msg in reversed(messages):  # Reverse to show chronological order
                sources = json.loads(msg.sources) if msg.sources else []
                history.append({
                    'id': msg.id,
                    'message': msg.message,
                    'response': msg.response,
                    'sources': sources,
                    'created_at': msg.created_at.isoformat(),
                })
            
            return history
            
        except Exception as e:
            raise Exception(f"Error retrieving chat history: {str(e)}")
    
    def clear_user_history(self, db: Session, user_id: int):
        """Clear all chat history for a user"""
        try:
            db.query(ChatMessage).filter(
                ChatMessage.user_id == user_id
            ).delete()
            
            db.commit()
            
        except Exception as e:
            db.rollback()
            raise Exception(f"Error clearing chat history: {str(e)}")
