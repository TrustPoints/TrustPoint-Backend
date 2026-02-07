from functools import wraps
from flask import request, jsonify, current_app, g
import jwt
from datetime import datetime, timedelta


def generate_token(user_id: str) -> str:
    expiration_hours = current_app.config.get('JWT_EXPIRATION_HOURS', 240)
    
    payload = {
        'user_id': user_id,
        'exp': datetime.utcnow() + timedelta(hours=expiration_hours),
        'iat': datetime.utcnow()
    }
    
    token = jwt.encode(
        payload,
        current_app.config['JWT_SECRET_KEY'],
        algorithm='HS256'
    )
    
    return token


def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(
            token,
            current_app.config['JWT_SECRET_KEY'],
            algorithms=['HS256']
        )
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        
        # Check for token in Authorization header
        auth_header = request.headers.get('Authorization')
        
        if auth_header:
            # Expected format: "Bearer <token>"
            parts = auth_header.split()
            if len(parts) == 2 and parts[0].lower() == 'bearer':
                token = parts[1]
        
        if not token:
            return jsonify({
                'success': False,
                'message': 'Token akses diperlukan',
                'error': 'missing_token'
            }), 401
        
        # Decode and verify token
        payload = decode_token(token)
        
        if not payload:
            return jsonify({
                'success': False,
                'message': 'Token tidak valid atau sudah kadaluarsa',
                'error': 'invalid_token'
            }), 401
        
        # Store user_id in Flask's g object for access in route
        g.current_user_id = payload.get('user_id')
        
        return f(*args, **kwargs)
    
    return decorated


def get_current_user_id() -> str:
    return getattr(g, 'current_user_id', None)
