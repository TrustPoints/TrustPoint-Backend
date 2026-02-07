from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional
from bson import ObjectId
import uuid


# =============================================================================
# Enums & Constants
# =============================================================================

class OrderStatus(str, Enum):
    PENDING = 'PENDING'
    CLAIMED = 'CLAIMED'
    IN_TRANSIT = 'IN_TRANSIT'
    DELIVERED = 'DELIVERED'
    CANCELLED = 'CANCELLED'


class ItemCategory(str, Enum):
    FOOD = 'FOOD'
    DOCUMENT = 'DOCUMENT'
    ELECTRONICS = 'ELECTRONICS'
    FASHION = 'FASHION'
    GROCERY = 'GROCERY'
    MEDICINE = 'MEDICINE'
    OTHER = 'OTHER'
    
    @classmethod
    def all_categories(cls) -> List[str]:
        return [cat.value for cat in cls]


# =============================================================================
# Order Model
# =============================================================================

class Order:
    # Pricing constants
    POINTS_PER_KM: int = 10
    MIN_POINTS: int = 5
    MIN_COST: int = 10
    WEIGHT_SURCHARGE_PER_KG: int = 5
    FRAGILE_COST_MULTIPLIER: float = 1.2
    FRAGILE_REWARD_MULTIPLIER: float = 1.5
    
    def __init__(self, mongo_db):
        self.collection = mongo_db.orders
        self._ensure_indexes()
    
    def _ensure_indexes(self) -> None:
        indexes = [
            ([("location.pickup.coords", "2dsphere")], {}),
            ([("location.destination.coords", "2dsphere")], {}),
            ("status", {}),
            ("sender_id", {}),
            ("hunter_id", {}),
            ([("status", 1), ("created_at", -1)], {}),
        ]
        for index_spec, options in indexes:
            self.collection.create_index(index_spec, **options)
    
    # =========================================================================
    # Static Methods - ID Generation & Calculations
    # =========================================================================
    
    @staticmethod
    def generate_order_id() -> str:
        timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
        unique_part = str(uuid.uuid4())[:8].upper()
        return f"TP-{timestamp}-{unique_part}"
    
    @staticmethod
    def create_geojson_point(longitude: float, latitude: float) -> Dict:
        return {
            "type": "Point",
            "coordinates": [longitude, latitude]
        }
    
    @classmethod
    def calculate_trust_points(cls, distance_km: float, is_fragile: bool = False) -> int:
        base_points = int(distance_km * cls.POINTS_PER_KM)
        if is_fragile:
            base_points = int(base_points * cls.FRAGILE_REWARD_MULTIPLIER)
        return max(base_points, cls.MIN_POINTS)
    
    @classmethod
    def calculate_delivery_cost(cls, distance_km: float, weight_kg: float = 0, 
                                is_fragile: bool = False) -> int:
        base_cost = int(distance_km * cls.POINTS_PER_KM)
        
        if weight_kg > 1:
            base_cost += int((weight_kg - 1) * cls.WEIGHT_SURCHARGE_PER_KG)
        
        if is_fragile:
            base_cost = int(base_cost * cls.FRAGILE_COST_MULTIPLIER)
        
        return max(base_cost, cls.MIN_COST)
    
    # =========================================================================
    # CRUD Operations
    # =========================================================================
    
    def create_order(self, sender_id: str, item_data: Dict, location_data: Dict, 
                     distance_km: float, notes: Optional[str] = None) -> Dict:
        now = datetime.utcnow()
        
        is_fragile = item_data.get('is_fragile', False)
        weight_kg = item_data.get('weight', 0)
        
        order_doc = {
            'order_id': self.generate_order_id(),
            'sender_id': sender_id,
            'hunter_id': None,
            'status': OrderStatus.PENDING.value,
            'item': {
                'name': item_data.get('name'),
                'category': item_data.get('category', ItemCategory.OTHER.value),
                'weight': weight_kg,
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
            'points_cost': self.calculate_delivery_cost(distance_km, weight_kg, is_fragile),
            'trust_points_reward': self.calculate_trust_points(distance_km, is_fragile),
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
    
    def find_by_id(self, order_id: str) -> Optional[Dict]:
        order = self.collection.find_one({'order_id': order_id})
        return self._format_order(order) if order else None
    
    def find_by_object_id(self, object_id: str) -> Optional[Dict]:
        try:
            order = self.collection.find_one({'_id': ObjectId(object_id)})
            return self._format_order(order) if order else None
        except Exception:
            return None
    
    # =========================================================================
    # Query Operations
    # =========================================================================
    
    def get_available_orders(self, limit: int = 50, skip: int = 0) -> List[Dict]:
        cursor = self.collection.find(
            {'status': OrderStatus.PENDING.value}
        ).sort('created_at', -1).skip(skip).limit(limit)
        
        return [self._format_order(order) for order in cursor]
    
    def get_nearby_orders(self, latitude: float, longitude: float, 
                          radius_km: float = 10, limit: int = 50) -> List[Dict]:
        radius_meters = radius_km * 1000
        
        cursor = self.collection.find({
            'status': OrderStatus.PENDING.value,
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
    
    def get_sender_orders(self, sender_id: str, status: Optional[str] = None, 
                          limit: int = 50, skip: int = 0) -> List[Dict]:
        query = {'sender_id': sender_id}
        if status:
            query['status'] = status
        
        cursor = self.collection.find(query).sort('created_at', -1).skip(skip).limit(limit)
        return [self._format_order(order) for order in cursor]
    
    def get_hunter_orders(self, hunter_id: str, status: Optional[str] = None,
                          limit: int = 50, skip: int = 0) -> List[Dict]:
        query = {'hunter_id': hunter_id}
        if status:
            query['status'] = status
        
        cursor = self.collection.find(query).sort('created_at', -1).skip(skip).limit(limit)
        return [self._format_order(order) for order in cursor]
    
    def count_available_orders(self) -> int:
        return self.collection.count_documents({'status': OrderStatus.PENDING.value})
    
    # =========================================================================
    # Status Transitions
    # =========================================================================
    
    def claim_order(self, order_id: str, hunter_id: str) -> Optional[Dict]:
        now = datetime.utcnow()
        
        result = self.collection.find_one_and_update(
            {
                'order_id': order_id,
                'status': OrderStatus.PENDING.value,
                'sender_id': {'$ne': hunter_id}
            },
            {
                '$set': {
                    'hunter_id': hunter_id,
                    'status': OrderStatus.CLAIMED.value,
                    'claimed_at': now,
                    'updated_at': now
                }
            },
            return_document=True
        )
        
        return self._format_order(result) if result else None
    
    def start_delivery(self, order_id: str, hunter_id: str) -> Optional[Dict]:
        now = datetime.utcnow()
        
        result = self.collection.find_one_and_update(
            {
                'order_id': order_id,
                'hunter_id': hunter_id,
                'status': OrderStatus.CLAIMED.value
            },
            {
                '$set': {
                    'status': OrderStatus.IN_TRANSIT.value,
                    'picked_up_at': now,
                    'updated_at': now
                }
            },
            return_document=True
        )
        
        return self._format_order(result) if result else None
    
    def complete_delivery(self, order_id: str, hunter_id: str) -> Optional[Dict]:
        now = datetime.utcnow()
        
        result = self.collection.find_one_and_update(
            {
                'order_id': order_id,
                'hunter_id': hunter_id,
                'status': OrderStatus.IN_TRANSIT.value
            },
            {
                '$set': {
                    'status': OrderStatus.DELIVERED.value,
                    'delivered_at': now,
                    'updated_at': now
                }
            },
            return_document=True
        )
        
        return self._format_order(result) if result else None
    
    def cancel_order(self, order_id: str, user_id: str) -> Optional[Dict]:
        now = datetime.utcnow()
        
        result = self.collection.find_one_and_update(
            {
                'order_id': order_id,
                'sender_id': user_id,
                'status': {'$in': [OrderStatus.PENDING.value, OrderStatus.CLAIMED.value]}
            },
            {
                '$set': {
                    'status': OrderStatus.CANCELLED.value,
                    'updated_at': now
                }
            },
            return_document=True
        )
        
        return self._format_order(result) if result else None
    
    # =========================================================================
    # Formatting
    # =========================================================================
    
    @staticmethod
    def _format_order(order: Optional[Dict]) -> Optional[Dict]:
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
