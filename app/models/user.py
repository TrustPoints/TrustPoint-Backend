from datetime import datetime
from typing import Dict, Optional, Set
from bson import ObjectId
import bcrypt


class User:
    # Fields allowed for profile updates
    UPDATABLE_FIELDS: Set[str] = {'full_name', 'profile_picture', 'language_preference', 'default_address'}
    
    # Points conversion rate: 1 pts = Rp100
    POINTS_TO_RUPIAH: int = 100
    
    def __init__(self, mongo_db):
        self.collection = mongo_db.users
        self._ensure_indexes()
    
    def _ensure_indexes(self) -> None:
        self.collection.create_index('email', unique=True)
    
    # ===========================================
    # Password Utilities
    # ===========================================
    
    @staticmethod
    def hash_password(password: str) -> str:
        salt = bcrypt.gensalt(rounds=12)
        return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')
    
    @staticmethod
    def verify_password(password: str, hashed: str) -> bool:
        return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
    
    # ===========================================
    # User CRUD Operations
    # ===========================================
    
    def create_user(self, full_name: str, email: str, password: str) -> Dict:
        now = datetime.utcnow()
        
        user_doc = {
            'full_name': full_name.strip(),
            'email': email.lower().strip(),
            'password': self.hash_password(password),
            'profile_picture': None,
            'trust_score': 0,
            'points': 0,
            'language_preference': 'id',
            'default_address': None,
            'created_at': now,
            'updated_at': now
        }
        
        result = self.collection.insert_one(user_doc)
        user_doc['_id'] = result.inserted_id
        
        return self._sanitize_user(user_doc)
    
    def find_by_email(self, email: str) -> Optional[Dict]:
        return self.collection.find_one({'email': email.lower().strip()})
    
    def find_by_id(self, user_id: str) -> Optional[Dict]:
        try:
            user = self.collection.find_one({'_id': ObjectId(user_id)})
            return self._sanitize_user(user) if user else None
        except Exception:
            return None
    
    def email_exists(self, email: str) -> bool:
        return self.collection.find_one({'email': email.lower().strip()}) is not None
    
    def update_profile(self, user_id: str, update_data: Dict) -> Optional[Dict]:
        filtered = {k: v for k, v in update_data.items() if k in self.UPDATABLE_FIELDS}
        
        if not filtered:
            return None
        
        filtered['updated_at'] = datetime.utcnow()
        
        try:
            result = self.collection.find_one_and_update(
                {'_id': ObjectId(user_id)},
                {'$set': filtered},
                return_document=True
            )
            return self._sanitize_user(result) if result else None
        except Exception:
            return None
    
    # ===========================================
    # Password Management
    # ===========================================
    
    def change_password(self, user_id: str, old_password: str, new_password: str) -> Dict:
        try:
            user = self.collection.find_one({'_id': ObjectId(user_id)})
            if not user:
                return {'success': False, 'error': 'User not found'}
            
            if not self.verify_password(old_password, user['password']):
                return {'success': False, 'error': 'Current password is incorrect'}
            
            result = self.collection.update_one(
                {'_id': ObjectId(user_id)},
                {'$set': {
                    'password': self.hash_password(new_password),
                    'updated_at': datetime.utcnow()
                }}
            )
            
            return {'success': True} if result.modified_count > 0 else {'success': False, 'error': 'Failed to update password'}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    # ===========================================
    # Points Management
    # ===========================================
    
    def get_points(self, user_id: str) -> Dict:
        try:
            user = self.collection.find_one({'_id': ObjectId(user_id)})
            if not user:
                return {'success': False, 'error': 'User not found'}
            
            points = user.get('points', 0)
            return {
                'success': True,
                'points': points,
                'rupiah_equivalent': points * self.POINTS_TO_RUPIAH
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def add_points(self, user_id: str, points: int, reason: Optional[str] = None) -> Dict:
        try:
            result = self.collection.find_one_and_update(
                {'_id': ObjectId(user_id)},
                {
                    '$inc': {'points': points},
                    '$set': {'updated_at': datetime.utcnow()}
                },
                return_document=True
            )
            if result:
                return {
                    'success': True,
                    'new_balance': result.get('points', 0),
                    'added': points
                }
            return {'success': False, 'error': 'User not found'}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def deduct_points(self, user_id: str, points: int, reason: Optional[str] = None) -> Dict:
        try:
            user = self.collection.find_one({'_id': ObjectId(user_id)})
            if not user:
                return {'success': False, 'error': 'User not found'}
            
            if user.get('points', 0) < points:
                return {'success': False, 'error': 'Insufficient points'}
            
            result = self.collection.find_one_and_update(
                {'_id': ObjectId(user_id)},
                {
                    '$inc': {'points': -points},
                    '$set': {'updated_at': datetime.utcnow()}
                },
                return_document=True
            )
            if result:
                return {
                    'success': True,
                    'new_balance': result.get('points', 0),
                    'deducted': points
                }
            return {'success': False, 'error': 'Failed to deduct points'}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    # ===========================================
    # Data Formatting
    # ===========================================
    
    @staticmethod
    def _sanitize_user(user: Optional[Dict]) -> Optional[Dict]:
        if not user:
            return None
        
        sanitized = user.copy()
        sanitized.pop('password', None)
        
        if '_id' in sanitized:
            sanitized['user_id'] = str(sanitized.pop('_id'))
        
        return sanitized
