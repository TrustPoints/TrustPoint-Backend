from datetime import datetime
from bson import ObjectId
import bcrypt


class User:
    def __init__(self, mongo_db):
        self.collection = mongo_db.users
        self._ensure_indexes()
    
    def _ensure_indexes(self):
        # Ensure email uniqueness
        self.collection.create_index('email', unique=True)
    
    @staticmethod
    def hash_password(password: str) -> str:
        salt = bcrypt.gensalt(rounds=12)
        hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
        return hashed.decode('utf-8')
    
    @staticmethod
    def verify_password(password: str, hashed_password: str) -> bool:
        return bcrypt.checkpw(
            password.encode('utf-8'),
            hashed_password.encode('utf-8')
        )
    
    def create_user(self, full_name: str, email: str, password: str) -> dict:
        now = datetime.utcnow()
        
        user_doc = {
            'full_name': full_name,
            'email': email.lower().strip(),
            'password': self.hash_password(password),
            'profile_picture': None,
            'trust_score': 0,
            'language_preference': 'id',
            'created_at': now,
            'updated_at': now
        }
        
        result = self.collection.insert_one(user_doc)
        user_doc['_id'] = result.inserted_id
        
        # Remove password before returning
        return self._sanitize_user(user_doc)
    
    def find_by_email(self, email: str) -> dict:
        return self.collection.find_one({'email': email.lower().strip()})
    
    def find_by_id(self, user_id: str) -> dict:
        try:
            user = self.collection.find_one({'_id': ObjectId(user_id)})
            if user:
                return self._sanitize_user(user)
            return None
        except Exception:
            return None
    
    def update_profile(self, user_id: str, update_data: dict) -> dict:
        # Only allow specific fields to be updated
        allowed_fields = {'full_name', 'profile_picture', 'language_preference'}
        filtered_data = {k: v for k, v in update_data.items() if k in allowed_fields}
        
        if not filtered_data:
            return None
        
        filtered_data['updated_at'] = datetime.utcnow()
        
        try:
            result = self.collection.find_one_and_update(
                {'_id': ObjectId(user_id)},
                {'$set': filtered_data},
                return_document=True
            )
            if result:
                return self._sanitize_user(result)
            return None
        except Exception:
            return None
    
    def email_exists(self, email: str) -> bool:
        return self.collection.find_one({'email': email.lower().strip()}) is not None
    
    def change_password(self, user_id: str, old_password: str, new_password: str) -> dict:
        """Change user password after verifying old password"""
        try:
            # Get user with password
            user = self.collection.find_one({'_id': ObjectId(user_id)})
            if not user:
                return {'success': False, 'error': 'User not found'}
            
            # Verify old password
            if not self.verify_password(old_password, user['password']):
                return {'success': False, 'error': 'Current password is incorrect'}
            
            # Hash new password and update
            new_hashed = self.hash_password(new_password)
            result = self.collection.update_one(
                {'_id': ObjectId(user_id)},
                {
                    '$set': {
                        'password': new_hashed,
                        'updated_at': datetime.utcnow()
                    }
                }
            )
            
            if result.modified_count > 0:
                return {'success': True}
            return {'success': False, 'error': 'Failed to update password'}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def _sanitize_user(user: dict) -> dict:
        if user:
            sanitized = user.copy()
            sanitized.pop('password', None)
            # Convert ObjectId to string for JSON serialization
            if '_id' in sanitized:
                sanitized['user_id'] = str(sanitized.pop('_id'))
            return sanitized
        return None
