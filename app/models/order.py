"""
TrustPoints Order Model
Handles order/delivery operations with GeoJSON support for location-based queries
"""
from datetime import datetime
from bson import ObjectId
import uuid


class OrderStatus:
    """Order status constants"""
    PENDING = 'PENDING'
    CLAIMED = 'CLAIMED'
    IN_TRANSIT = 'IN_TRANSIT'
    DELIVERED = 'DELIVERED'
    CANCELLED = 'CANCELLED'


class ItemCategory:
    """Item category constants"""
    FOOD = 'FOOD'
    DOCUMENT = 'DOCUMENT'
    ELECTRONICS = 'ELECTRONICS'
    FASHION = 'FASHION'
    GROCERY = 'GROCERY'
    MEDICINE = 'MEDICINE'
    OTHER = 'OTHER'
    
    @classmethod
    def all_categories(cls):
        return [cls.FOOD, cls.DOCUMENT, cls.ELECTRONICS, cls.FASHION, 
                cls.GROCERY, cls.MEDICINE, cls.OTHER]


class Order:
    def __init__(self, mongo_db):
        self.collection = mongo_db.orders
        self._ensure_indexes()
    
    def _ensure_indexes(self):
        """Create necessary indexes including geospatial index"""
        # Geospatial index for pickup location
        self.collection.create_index([("location.pickup.coords", "2dsphere")])
        # Geospatial index for destination location
        self.collection.create_index([("location.destination.coords", "2dsphere")])
        # Index for status filtering
        self.collection.create_index("status")
        # Index for sender_id
        self.collection.create_index("sender_id")
        # Index for hunter_id
        self.collection.create_index("hunter_id")
        # Compound index for common queries
        self.collection.create_index([("status", 1), ("created_at", -1)])
    
    @staticmethod
    def generate_order_id():
        """Generate unique order ID"""
        timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
        unique_part = str(uuid.uuid4())[:8].upper()
        return f"TP-{timestamp}-{unique_part}"
    
    @staticmethod
    def create_geojson_point(longitude: float, latitude: float) -> dict:
        """Create GeoJSON Point from coordinates"""
        return {
            "type": "Point",
            "coordinates": [longitude, latitude]  # GeoJSON format: [lng, lat]
        }
    
    @staticmethod
    def calculate_trust_points(distance_km: float, is_fragile: bool = False) -> int:
        """Calculate trust points reward for hunter based on distance and item fragility"""
        base_points = int(distance_km * 10)  # 10 points per km
        if is_fragile:
            base_points = int(base_points * 1.5)  # 50% bonus for fragile items
        return max(base_points, 5)  # Minimum 5 points
    
    @staticmethod
    def calculate_delivery_cost(distance_km: float, weight_kg: float = 0, is_fragile: bool = False) -> int:
        """
        Calculate delivery cost in points for sender
        
        Pricing:
        - Base: 10 points per km
        - Weight surcharge: +5 points per kg over 1kg
        - Fragile surcharge: +20%
        - Minimum cost: 10 points
        """
        # Base cost: 10 points per km
        base_cost = int(distance_km * 10)
        
        # Weight surcharge: +5 points per kg over 1kg
        if weight_kg > 1:
            base_cost += int((weight_kg - 1) * 5)
        
        # Fragile surcharge: +20%
        if is_fragile:
            base_cost = int(base_cost * 1.2)
        
        return max(base_cost, 10)  # Minimum 10 points
    
    def create_order(self, sender_id: str, item_data: dict, location_data: dict, 
                     distance_km: float, notes: str = None) -> dict:
        """
        Create a new order
        
        Args:
            sender_id: ID of the sender user
            item_data: Dict containing item details (name, category, weight, photo_url, description, is_fragile)
            location_data: Dict containing pickup and destination locations
            distance_km: Distance between pickup and destination in kilometers
            notes: Optional delivery notes
        
        Returns:
            Created order document
        """
        now = datetime.utcnow()
        
        # Calculate trust points reward for hunter
        is_fragile = item_data.get('is_fragile', False)
        weight_kg = item_data.get('weight', 0)
        trust_points_reward = self.calculate_trust_points(distance_km, is_fragile)
        
        # Calculate delivery cost for sender
        points_cost = self.calculate_delivery_cost(distance_km, weight_kg, is_fragile)
        
        order_doc = {
            'order_id': self.generate_order_id(),
            'sender_id': sender_id,
            'hunter_id': None,
            'status': OrderStatus.PENDING,
            'item': {
                'name': item_data.get('name'),
                'category': item_data.get('category', ItemCategory.OTHER),
                'weight': weight_kg,  # in kg
                'photo_url': item_data.get('photo_url'),
                'description': item_data.get('description', ''),
                'is_fragile': is_fragile
            },
            'location': {
                'pickup': {
                    'address': location_data['pickup']['address'],
                    'coords': self.create_geojson_point(
                        location_data['pickup']['longitude'],
                        location_data['pickup']['latitude']
                    )
                },
                'destination': {
                    'address': location_data['destination']['address'],
                    'coords': self.create_geojson_point(
                        location_data['destination']['longitude'],
                        location_data['destination']['latitude']
                    )
                }
            },
            'distance_km': round(distance_km, 2),
            'points_cost': points_cost,  # Cost for sender
            'trust_points_reward': trust_points_reward,  # Reward for hunter
            'notes': notes,
            'claimed_at': None,
            'picked_up_at': None,
            'delivered_at': None,
            'created_at': now,
            'updated_at': now
        }
        
        result = self.collection.insert_one(order_doc)
        order_doc['_id'] = result.inserted_id
        
        return self._format_order(order_doc)
    
    def find_by_id(self, order_id: str) -> dict:
        """Find order by order_id"""
        order = self.collection.find_one({'order_id': order_id})
        return self._format_order(order) if order else None
    
    def find_by_object_id(self, object_id: str) -> dict:
        """Find order by MongoDB ObjectId"""
        try:
            order = self.collection.find_one({'_id': ObjectId(object_id)})
            return self._format_order(order) if order else None
        except Exception:
            return None
    
    def get_available_orders(self, limit: int = 50, skip: int = 0) -> list:
        """
        Get all orders with PENDING status (available for hunters)
        Sorted by newest first
        """
        cursor = self.collection.find(
            {'status': OrderStatus.PENDING}
        ).sort('created_at', -1).skip(skip).limit(limit)
        
        return [self._format_order(order) for order in cursor]
    
    def get_nearby_orders(self, latitude: float, longitude: float, 
                          radius_km: float = 10, limit: int = 50) -> list:
        """
        Get PENDING orders near a specific location using geospatial query
        
        Args:
            latitude: User's latitude
            longitude: User's longitude
            radius_km: Search radius in kilometers (default 10km)
            limit: Maximum number of results
        
        Returns:
            List of nearby orders sorted by distance
        """
        # Convert radius from km to meters
        radius_meters = radius_km * 1000
        
        cursor = self.collection.find({
            'status': OrderStatus.PENDING,
            'location.pickup.coords': {
                '$near': {
                    '$geometry': {
                        'type': 'Point',
                        'coordinates': [longitude, latitude]
                    },
                    '$maxDistance': radius_meters
                }
            }
        }).limit(limit)
        
        return [self._format_order(order) for order in cursor]
    
    def claim_order(self, order_id: str, hunter_id: str) -> dict:
        """
        Hunter claims an order
        Changes status from PENDING to CLAIMED
        """
        now = datetime.utcnow()
        
        result = self.collection.find_one_and_update(
            {
                'order_id': order_id,
                'status': OrderStatus.PENDING,  # Can only claim pending orders
                'sender_id': {'$ne': hunter_id}  # Hunter cannot claim own order
            },
            {
                '$set': {
                    'hunter_id': hunter_id,
                    'status': OrderStatus.CLAIMED,
                    'claimed_at': now,
                    'updated_at': now
                }
            },
            return_document=True
        )
        
        return self._format_order(result) if result else None
    
    def start_delivery(self, order_id: str, hunter_id: str) -> dict:
        """
        Hunter starts delivery (picked up the item)
        Changes status from CLAIMED to IN_TRANSIT
        """
        now = datetime.utcnow()
        
        result = self.collection.find_one_and_update(
            {
                'order_id': order_id,
                'hunter_id': hunter_id,
                'status': OrderStatus.CLAIMED
            },
            {
                '$set': {
                    'status': OrderStatus.IN_TRANSIT,
                    'picked_up_at': now,
                    'updated_at': now
                }
            },
            return_document=True
        )
        
        return self._format_order(result) if result else None
    
    def complete_delivery(self, order_id: str, hunter_id: str) -> dict:
        """
        Hunter completes delivery
        Changes status from IN_TRANSIT to DELIVERED
        """
        now = datetime.utcnow()
        
        result = self.collection.find_one_and_update(
            {
                'order_id': order_id,
                'hunter_id': hunter_id,
                'status': OrderStatus.IN_TRANSIT
            },
            {
                '$set': {
                    'status': OrderStatus.DELIVERED,
                    'delivered_at': now,
                    'updated_at': now
                }
            },
            return_document=True
        )
        
        return self._format_order(result) if result else None
    
    def cancel_order(self, order_id: str, user_id: str) -> dict:
        """
        Cancel an order (only sender can cancel, and only if not yet in transit)
        """
        now = datetime.utcnow()
        
        result = self.collection.find_one_and_update(
            {
                'order_id': order_id,
                'sender_id': user_id,
                'status': {'$in': [OrderStatus.PENDING, OrderStatus.CLAIMED]}
            },
            {
                '$set': {
                    'status': OrderStatus.CANCELLED,
                    'updated_at': now
                }
            },
            return_document=True
        )
        
        return self._format_order(result) if result else None
    
    def get_sender_orders(self, sender_id: str, status: str = None, 
                          limit: int = 50, skip: int = 0) -> list:
        """Get orders created by a sender"""
        query = {'sender_id': sender_id}
        if status:
            query['status'] = status
        
        cursor = self.collection.find(query).sort('created_at', -1).skip(skip).limit(limit)
        return [self._format_order(order) for order in cursor]
    
    def get_hunter_orders(self, hunter_id: str, status: str = None,
                          limit: int = 50, skip: int = 0) -> list:
        """Get orders claimed by a hunter"""
        query = {'hunter_id': hunter_id}
        if status:
            query['status'] = status
        
        cursor = self.collection.find(query).sort('created_at', -1).skip(skip).limit(limit)
        return [self._format_order(order) for order in cursor]
    
    def count_available_orders(self) -> int:
        """Count total available (PENDING) orders"""
        return self.collection.count_documents({'status': OrderStatus.PENDING})
    
    @staticmethod
    def _format_order(order: dict) -> dict:
        """Format order document for API response"""
        if not order:
            return None
        
        formatted = order.copy()
        
        # Convert ObjectId to string
        if '_id' in formatted:
            formatted['id'] = str(formatted.pop('_id'))
        
        # Format datetime fields
        datetime_fields = ['created_at', 'updated_at', 'claimed_at', 'picked_up_at', 'delivered_at']
        for field in datetime_fields:
            if formatted.get(field):
                formatted[field] = formatted[field].isoformat() + 'Z'
        
        # Extract coordinates for easier frontend access
        if 'location' in formatted:
            pickup_coords = formatted['location']['pickup']['coords']['coordinates']
            dest_coords = formatted['location']['destination']['coords']['coordinates']
            
            formatted['pickup_coordinates'] = {
                'longitude': pickup_coords[0],
                'latitude': pickup_coords[1]
            }
            formatted['destination_coordinates'] = {
                'longitude': dest_coords[0],
                'latitude': dest_coords[1]
            }
        
        return formatted
