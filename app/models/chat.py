from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional
from bson import ObjectId


# =============================================================================
# Enums & Constants
# =============================================================================

class MessageType(str, Enum):
    TEXT = 'text'
    SYSTEM = 'system'
    LOCATION = 'location'


# =============================================================================
# Chat Model
# =============================================================================

class Chat:
    SYSTEM_SENDER_ID = 'system'
    SYSTEM_SENDER_NAME = 'System'
    
    def __init__(self, mongo_db):
        self.collection = mongo_db.chats
        self._ensure_indexes()
    
    def _ensure_indexes(self) -> None:
        indexes = [
            ("order_id", {}),
            ([("order_id", 1), ("created_at", 1)], {}),
            ("sender_id", {}),
        ]
        for index_spec, options in indexes:
            self.collection.create_index(index_spec, **options)
    
    # =========================================================================
    # Message Operations
    # =========================================================================
    
    def send_message(self, order_id: str, sender_id: str, sender_name: str, 
                     message: str, message_type: str = MessageType.TEXT.value) -> Dict:
        now = datetime.utcnow()
        
        message_doc = {
            'order_id': order_id,
            'sender_id': sender_id,
            'sender_name': sender_name,
            'message': message,
            'message_type': message_type,
            'is_read': False,
            'created_at': now
        }
        
        result = self.collection.insert_one(message_doc)
        message_doc['_id'] = result.inserted_id
        
        return self._sanitize_message(message_doc)
    
    def send_system_message(self, order_id: str, message: str) -> Dict:
        return self.send_message(
            order_id=order_id,
            sender_id=self.SYSTEM_SENDER_ID,
            sender_name=self.SYSTEM_SENDER_NAME,
            message=message,
            message_type=MessageType.SYSTEM.value
        )
    
    # =========================================================================
    # Query Operations
    # =========================================================================
    
    def get_messages(self, order_id: str, limit: int = 100, skip: int = 0) -> List[Dict]:
        cursor = self.collection.find(
            {'order_id': order_id}
        ).sort('created_at', 1).skip(skip).limit(limit)
        
        return [self._sanitize_message(msg) for msg in cursor]
    
    def get_messages_after(self, order_id: str, after_timestamp: datetime) -> List[Dict]:
        cursor = self.collection.find({
            'order_id': order_id,
            'created_at': {'$gt': after_timestamp}
        }).sort('created_at', 1)
        
        return [self._sanitize_message(msg) for msg in cursor]
    
    def get_unread_count(self, order_id: str, user_id: str) -> int:
        return self.collection.count_documents({
            'order_id': order_id,
            'sender_id': {'$ne': user_id},
            'is_read': False
        })
    
    # =========================================================================
    # Update Operations
    # =========================================================================
    
    def mark_as_read(self, order_id: str, reader_id: str) -> int:
        result = self.collection.update_many(
            {
                'order_id': order_id,
                'sender_id': {'$ne': reader_id},
                'is_read': False
            },
            {'$set': {'is_read': True}}
        )
        return result.modified_count
    
    def delete_order_messages(self, order_id: str) -> int:
        result = self.collection.delete_many({'order_id': order_id})
        return result.deleted_count
    
    # =========================================================================
    # Formatting
    # =========================================================================
    
    @staticmethod
    def _sanitize_message(message: Optional[Dict]) -> Optional[Dict]:
        if not message:
            return message
        
        sanitized = message.copy()
        if '_id' in sanitized:
            sanitized['id'] = str(sanitized.pop('_id'))
        if 'created_at' in sanitized:
            sanitized['created_at'] = sanitized['created_at'].isoformat()
        return sanitized
