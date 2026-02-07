"""
TrustPoints Activity Model
Handles user activity logging for tracking all user actions
"""
from datetime import datetime
from bson import ObjectId


class ActivityType:
    """Activity type constants"""
    ORDER_CREATED = 'ORDER_CREATED'
    ORDER_CLAIMED = 'ORDER_CLAIMED'
    ORDER_PICKED_UP = 'ORDER_PICKED_UP'
    ORDER_DELIVERED = 'ORDER_DELIVERED'
    ORDER_CANCELLED = 'ORDER_CANCELLED'
    POINTS_EARNED = 'POINTS_EARNED'
    POINTS_SPENT = 'POINTS_SPENT'
    POINTS_TRANSFERRED = 'POINTS_TRANSFERRED'
    POINTS_RECEIVED = 'POINTS_RECEIVED'
    ACCOUNT_CREATED = 'ACCOUNT_CREATED'
    PROFILE_UPDATED = 'PROFILE_UPDATED'


class Activity:
    def __init__(self, mongo_db):
        self.collection = mongo_db.activities
        self._ensure_indexes()
    
    def _ensure_indexes(self):
        """Create necessary indexes for efficient querying"""
        # Index for user_id queries
        self.collection.create_index("user_id")
        # Index for created_at for sorting
        self.collection.create_index([("created_at", -1)])
        # Compound index for user activities sorted by date
        self.collection.create_index([("user_id", 1), ("created_at", -1)])
        # Index for activity type
        self.collection.create_index("type")
    
    def create_activity(self, user_id: str, activity_type: str, title: str, 
                        description: str = None, points: int = None, 
                        order_id: str = None, metadata: dict = None) -> dict:
        """
        Create a new activity record
        
        Args:
            user_id: ID of the user who performed the activity
            activity_type: Type of activity (from ActivityType constants)
            title: Short title of the activity
            description: Detailed description
            points: Points earned or spent (positive for earned, negative for spent)
            order_id: Related order ID if applicable
            metadata: Additional data related to the activity
        
        Returns:
            Created activity document
        """
        now = datetime.utcnow()
        
        activity_doc = {
            'user_id': user_id,
            'type': activity_type,
            'title': title,
            'description': description,
            'points': points,
            'order_id': order_id,
            'metadata': metadata or {},
            'created_at': now
        }
        
        result = self.collection.insert_one(activity_doc)
        activity_doc['_id'] = result.inserted_id
        
        return self._format_activity(activity_doc)
    
    def get_user_activities(self, user_id: str, limit: int = 10, skip: int = 0) -> list:
        """
        Get activities for a specific user
        
        Args:
            user_id: ID of the user
            limit: Maximum number of activities to return
            skip: Number of activities to skip (for pagination)
        
        Returns:
            List of activity documents
        """
        cursor = self.collection.find(
            {'user_id': user_id}
        ).sort('created_at', -1).skip(skip).limit(limit)
        
        return [self._format_activity(activity) for activity in cursor]
    
    def get_recent_activities(self, user_id: str, limit: int = 5) -> list:
        """
        Get most recent activities for a user (for dashboard display)
        
        Args:
            user_id: ID of the user
            limit: Maximum number of activities to return
        
        Returns:
            List of activity documents
        """
        return self.get_user_activities(user_id, limit=limit, skip=0)
    
    def count_user_activities(self, user_id: str) -> int:
        """Count total activities for a user"""
        return self.collection.count_documents({'user_id': user_id})
    
    def log_order_created(self, user_id: str, order_id: str, points_cost: int = 0) -> dict:
        """Log when user creates a new order"""
        return self.create_activity(
            user_id=user_id,
            activity_type=ActivityType.ORDER_CREATED,
            title='Pesanan Dibuat',
            description=f'Order #{order_id}',
            points=-points_cost if points_cost > 0 else None,
            order_id=order_id
        )
    
    def log_order_claimed(self, user_id: str, order_id: str) -> dict:
        """Log when hunter claims an order"""
        return self.create_activity(
            user_id=user_id,
            activity_type=ActivityType.ORDER_CLAIMED,
            title='Mengambil Pesanan',
            description=f'Order #{order_id}',
            order_id=order_id
        )
    
    def log_order_picked_up(self, user_id: str, order_id: str) -> dict:
        """Log when hunter picks up an order"""
        return self.create_activity(
            user_id=user_id,
            activity_type=ActivityType.ORDER_PICKED_UP,
            title='Paket Diambil',
            description=f'Order #{order_id}',
            order_id=order_id
        )
    
    def log_order_delivered(self, user_id: str, order_id: str, points_earned: int = 0) -> dict:
        """Log when hunter delivers an order"""
        return self.create_activity(
            user_id=user_id,
            activity_type=ActivityType.ORDER_DELIVERED,
            title='Pengiriman Selesai',
            description=f'Order #{order_id}',
            points=points_earned if points_earned > 0 else None,
            order_id=order_id
        )
    
    def log_order_cancelled(self, user_id: str, order_id: str, refund_points: int = 0) -> dict:
        """Log when order is cancelled"""
        return self.create_activity(
            user_id=user_id,
            activity_type=ActivityType.ORDER_CANCELLED,
            title='Pesanan Dibatalkan',
            description=f'Order #{order_id}',
            points=refund_points if refund_points > 0 else None,
            order_id=order_id
        )
    
    def log_points_earned(self, user_id: str, points: int, reason: str = None) -> dict:
        """Log when user earns points"""
        return self.create_activity(
            user_id=user_id,
            activity_type=ActivityType.POINTS_EARNED,
            title='Points Diterima',
            description=reason or 'Points earned',
            points=points
        )
    
    def log_points_spent(self, user_id: str, points: int, reason: str = None) -> dict:
        """Log when user spends points"""
        return self.create_activity(
            user_id=user_id,
            activity_type=ActivityType.POINTS_SPENT,
            title='Points Digunakan',
            description=reason or 'Points spent',
            points=-points
        )
    
    def log_points_transferred(self, user_id: str, points: int, recipient_email: str) -> dict:
        """Log when user transfers points to another user"""
        return self.create_activity(
            user_id=user_id,
            activity_type=ActivityType.POINTS_TRANSFERRED,
            title='Transfer Points',
            description=f'Transfer ke {recipient_email}',
            points=-points,
            metadata={'recipient_email': recipient_email}
        )
    
    def log_points_received(self, user_id: str, points: int, sender_email: str = None) -> dict:
        """Log when user receives points from transfer"""
        return self.create_activity(
            user_id=user_id,
            activity_type=ActivityType.POINTS_RECEIVED,
            title='Points Diterima',
            description=f'Transfer dari pengguna lain' if not sender_email else f'Transfer dari {sender_email}',
            points=points,
            metadata={'sender_email': sender_email} if sender_email else {}
        )
    
    @staticmethod
    def _format_activity(activity: dict) -> dict:
        """Format activity document for API response"""
        if activity:
            formatted = activity.copy()
            if '_id' in formatted:
                formatted['activity_id'] = str(formatted.pop('_id'))
            if 'created_at' in formatted and isinstance(formatted['created_at'], datetime):
                formatted['created_at'] = formatted['created_at'].isoformat()
            return formatted
        return None
