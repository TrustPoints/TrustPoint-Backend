import logging
from flask import Blueprint, request, current_app

from app.models.user import User
from app.utils.auth import generate_token
from app.utils.responses import (
    success_response, error_response, validation_error,
    database_error, missing_data_error, server_error
)
from app.utils.validators import validate_registration_data

logger = logging.getLogger(__name__)

auth_bp = Blueprint('auth', __name__)


def _get_db():
    mongo = current_app.extensions.get('pymongo')
    return mongo.db if mongo else None


@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    if not data:
        return missing_data_error()
    
    is_valid, errors = validate_registration_data(data)
    if not is_valid:
        return validation_error(errors)
    
    db = _get_db()
    if db is None:
        return database_error()
    
    user_model = User(db)
    
    if user_model.email_exists(data['email']):
        return error_response(
            message="Email sudah terdaftar",
            error_code="email_exists",
            status_code=409
        )
    
    try:
        user = user_model.create_user(
            full_name=data['full_name'].strip(),
            email=data['email'],
            password=data['password']
        )
        
        token = generate_token(user['user_id'])
        
        return success_response(
            data={'user': user, 'token': token},
            message="Registrasi berhasil",
            status_code=201
        )
    except Exception:
        logger.exception("Registration failed")
        return server_error("Terjadi kesalahan saat registrasi")


@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    if not data:
        return missing_data_error()
    
    email = data.get('email', '').strip()
    password = data.get('password', '')
    
    if not email:
        return error_response(
            message="Email wajib diisi",
            error_code="missing_email",
            status_code=400
        )
    
    if not password:
        return error_response(
            message="Password wajib diisi",
            error_code="missing_password",
            status_code=400
        )
    
    db = _get_db()
    if db is None:
        return database_error()
    
    user_model = User(db)
    
    try:
        user = user_model.find_by_email(email)
        if not user or not User.verify_password(password, user['password']):
            return error_response(
                message="Email atau password salah",
                error_code="invalid_credentials",
                status_code=401
            )
        
        user_id = str(user['_id'])
        token = generate_token(user_id)
        
        return success_response(
            data={
                'user': User._sanitize_user(user),
                'token': token
            },
            message="Login berhasil"
        )
    except Exception:
        logger.exception("Login failed")
        return server_error("Terjadi kesalahan saat login")
