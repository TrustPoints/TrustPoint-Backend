from flask import Blueprint, request, current_app
from app.models.user import User
from app.utils.auth import generate_token
from app.utils.responses import success_response, error_response, validation_error
from app.utils.validators import validate_registration_data, validate_email, validate_password

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/register', methods=['POST'])
def register():
    try:
        data = request.get_json()
        
        if not data:
            return error_response(
                message="Data tidak ditemukan",
                error_code="missing_data",
                status_code=400
            )
        
        # Validate input data
        is_valid, errors = validate_registration_data(data)
        if not is_valid:
            return validation_error(errors)
        
        # Get MongoDB from app context
        mongo = current_app.extensions.get('pymongo')
        if not mongo:
            return error_response(
                message="Database tidak tersedia",
                error_code="database_error",
                status_code=500
            )
        
        user_model = User(mongo.db)
        
        # Check if email already exists
        if user_model.email_exists(data['email']):
            return error_response(
                message="Email sudah terdaftar",
                error_code="email_exists",
                status_code=409
            )
        
        # Create new user
        user = user_model.create_user(
            full_name=data['full_name'].strip(),
            email=data['email'],
            password=data['password']
        )
        
        # Generate JWT token
        token = generate_token(user['user_id'])
        
        return success_response(
            data={
                'user': user,
                'token': token
            },
            message="Registrasi berhasil",
            status_code=201
        )
        
    except Exception as e:
        current_app.logger.error(f"Registration error: {str(e)}")
        return error_response(
            message="Terjadi kesalahan saat registrasi",
            error_code="server_error",
            status_code=500
        )


@auth_bp.route('/login', methods=['POST'])
def login():
    try:
        data = request.get_json()
        
        if not data:
            return error_response(
                message="Data tidak ditemukan",
                error_code="missing_data",
                status_code=400
            )
        
        email = data.get('email', '').strip()
        password = data.get('password', '')
        
        # Basic validation
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
        
        # Get MongoDB from app context
        mongo = current_app.extensions.get('pymongo')
        if not mongo:
            return error_response(
                message="Database tidak tersedia",
                error_code="database_error",
                status_code=500
            )
        
        user_model = User(mongo.db)
        
        # Find user by email
        user = user_model.find_by_email(email)
        
        if not user:
            return error_response(
                message="Email atau password salah",
                error_code="invalid_credentials",
                status_code=401
            )
        
        # Verify password
        if not User.verify_password(password, user['password']):
            return error_response(
                message="Email atau password salah",
                error_code="invalid_credentials",
                status_code=401
            )
        
        # Generate JWT token
        user_id = str(user['_id'])
        token = generate_token(user_id)
        
        # Sanitize user data for response
        user_data = User._sanitize_user(user)
        
        return success_response(
            data={
                'user': user_data,
                'token': token
            },
            message="Login berhasil"
        )
        
    except Exception as e:
        current_app.logger.error(f"Login error: {str(e)}")
        return error_response(
            message="Terjadi kesalahan saat login",
            error_code="server_error",
            status_code=500
        )
