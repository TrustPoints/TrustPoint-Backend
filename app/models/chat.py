"""
TrustPoints Chat Model
Handles chat/messaging between sender and hunter for orders
"""
from datetime import datetime
from bson import ObjectId


class Chat:
    def __init__(self, mongo_db):
        self.collection = mongo_db.chats
        self._ensure_indexes()
    
    def _ensure_indexes(self):
        """Create necessary indexes for chat queries"""
        # Index for order_id to quickly fetch all messages for an order
        self.collection.create_index("order_id")
        # Compound index for order messages sorted by time
        self.collection.create_index([("order_id", 1), ("created_at", 1)])
        # Index for sender queries
        self.collection.create_index("sender_id")
    
    def send_message(self, order_id: str, sender_id: str, sender_name: str, 
                     message: str, message_type: str = 'text') -> dict:
        """
        Send a chat message
        
        Args:
            order_id: ID of the order this message belongs to
            sender_id: ID of the user sending the message
            sender_name: Name of the sender for display
            message: The message content
            message_type: Type of message ('text', 'system', 'location')
        
        Returns:
            Created message document
        """
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
    
    def get_messages(self, order_id: str, limit: int = 100, skip: int = 0) -> list:
        """
        Get all messages for an order
        
        Args:
            order_id: The order ID to fetch messages for
            limit: Maximum number of messages to return
            skip: Number of messages to skip (for pagination)
        
        Returns:
            List of message documents sorted by creation time (oldest first)
        """
        cursor = self.collection.find(
            {'order_id': order_id}
        ).sort('created_at', 1).skip(skip).limit(limit)
        
        return [self._sanitize_message(msg) for msg in cursor]
    
    def get_messages_after(self, order_id: str, after_timestamp: datetime) -> list:
        """
        Get messages after a specific timestamp (for real-time updates)
        
        Args:
            order_id: The order ID
            after_timestamp: Get messages created after this time
        
        Returns:
            List of new messages
        """
        cursor = self.collection.find({
            'order_id': order_id,
            'created_at': {'$gt': after_timestamp}
        }).sort('created_at', 1)
        
        return [self._sanitize_message(msg) for msg in cursor]
    
    def mark_as_read(self, order_id: str, reader_id: str) -> int:
        """
        Mark all messages as read for a user
        
        Args:
            order_id: The order ID
            reader_id: ID of the user reading the messages
        
        Returns:
            Number of messages marked as read
        """
        result = self.collection.update_many(
            {
                'order_id': order_id,
                'sender_id': {'$ne': reader_id},
                'is_read': False
            },
            {'$set': {'is_read': True}}
        )
        return result.modified_count
    
    def get_unread_count(self, order_id: str, user_id: str) -> int:
        """
        Get count of unread messages for a user in an order
        
        Args:
            order_id: The order ID
            user_id: The user to check unread count for
        
        Returns:
            Number of unread messages
        """
        return self.collection.count_documents({
            'order_id': order_id,
            'sender_id': {'$ne': user_id},
            'is_read': False
        })
    
    def send_system_message(self, order_id: str, message: str) -> dict:
        """
        Send a system notification message
        
        Args:
            order_id: The order ID
            message: System message content
        
        Returns:
            Created system message document
        """
        return self.send_message(
            order_id=order_id,
            sender_id='system',
            sender_name='System',
            message=message,
            message_type='system'
        )
    
    def delete_order_messages(self, order_id: str) -> int:
        """
        Delete all messages for an order (cleanup)
        
        Args:
            order_id: The order ID
        
        Returns:
            Number of messages deleted
        """
        result = self.collection.delete_many({'order_id': order_id})
        return result.deleted_count
    
    @staticmethod
    def _sanitize_message(message: dict) -> dict:
        """Convert ObjectId to string for JSON serialization"""
        if message:
            sanitized = message.copy()
            if '_id' in sanitized:
                sanitized['id'] = str(sanitized.pop('_id'))
            if 'created_at' in sanitized:
                sanitized['created_at'] = sanitized['created_at'].isoformat()
            return sanitized
        return message
