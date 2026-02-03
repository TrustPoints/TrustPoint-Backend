"""
TrustPoints Profile Routes
Handles user profile operations (protected routes)
"""
from flask import Blueprint, request, current_app
from app.models.user import User
from app.utils.auth import token_required, get_current_user_id
from app.utils.responses import success_response, error_response, validation_error
from app.utils.validators import validate_profile_update

profile_bp = Blueprint('profile', __name__)


@profile_bp.route('/profile', methods=['GET'])
@token_required
def get_profile():
    """
    Get current user's profile
    
    Headers:
        Authorization: Bearer <token>
    
    Returns:
        200: User profile data
        401: Unauthorized
        404: User not found
    """
    try:
        user_id = get_current_user_id()
        
        if not user_id:
            return error_response(
                message="User tidak terautentikasi",
                error_code="unauthorized",
                status_code=401
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
        user = user_model.find_by_id(user_id)
        
        if not user:
            return error_response(
                message="User tidak ditemukan",
                error_code="user_not_found",
                status_code=404
            )
        
        return success_response(
            data={'user': user},
            message="Profil berhasil diambil"
        )
        
    except Exception as e:
        current_app.logger.error(f"Get profile error: {str(e)}")
        return error_response(
            message="Terjadi kesalahan saat mengambil profil",
            error_code="server_error",
            status_code=500
        )


@profile_bp.route('/profile/edit', methods=['PUT'])
@token_required
def update_profile():
    """
    Update current user's profile
    
    Headers:
        Authorization: Bearer <token>
    
    Request Body:
        {
            "full_name": "string" (optional),
            "profile_picture": "string" (optional),
            "language_preference": "string" (optional)
        }
    
    Returns:
        200: Profile updated successfully
        400: Invalid data
        401: Unauthorized
        404: User not found
    """
    try:
        user_id = get_current_user_id()
        
        if not user_id:
            return error_response(
                message="User tidak terautentikasi",
                error_code="unauthorized",
                status_code=401
            )
        
        data = request.get_json()
        
        if not data:
            return error_response(
                message="Data tidak ditemukan",
                error_code="missing_data",
                status_code=400
            )
        
        # Validate update data
        is_valid, errors = validate_profile_update(data)
        if not is_valid:
            return validation_error(errors)
        
        # Check if any valid field is provided
        valid_fields = {'full_name', 'profile_picture', 'language_preference'}
        update_data = {k: v for k, v in data.items() if k in valid_fields}
        
        if not update_data:
            return error_response(
                message="Tidak ada data yang valid untuk diupdate",
                error_code="no_valid_data",
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
        
        # Check if user exists
        existing_user = user_model.find_by_id(user_id)
        if not existing_user:
            return error_response(
                message="User tidak ditemukan",
                error_code="user_not_found",
                status_code=404
            )
        
        # Update profile
        updated_user = user_model.update_profile(user_id, update_data)
        
        if not updated_user:
            return error_response(
                message="Gagal mengupdate profil",
                error_code="update_failed",
                status_code=500
            )
        
        return success_response(
            data={'user': updated_user},
            message="Profil berhasil diupdate"
        )
        
    except Exception as e:
        current_app.logger.error(f"Update profile error: {str(e)}")
        return error_response(
            message="Terjadi kesalahan saat mengupdate profil",
            error_code="server_error",
            status_code=500
        )
