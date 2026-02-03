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


@profile_bp.route('/profile/change-password', methods=['POST'])
@token_required
def change_password():
    """
    Change current user's password
    
    Headers:
        Authorization: Bearer <token>
    
    Request Body:
        {
            "old_password": "string" (required),
            "new_password": "string" (required),
            "confirm_password": "string" (required)
        }
    
    Returns:
        200: Password changed successfully
        400: Invalid data / Password mismatch
        401: Unauthorized / Wrong old password
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
        
        # Validate required fields
        old_password = data.get('old_password', '').strip()
        new_password = data.get('new_password', '').strip()
        confirm_password = data.get('confirm_password', '').strip()
        
        if not old_password:
            return error_response(
                message="Password lama harus diisi",
                error_code="missing_old_password",
                status_code=400
            )
        
        if not new_password:
            return error_response(
                message="Password baru harus diisi",
                error_code="missing_new_password",
                status_code=400
            )
        
        if not confirm_password:
            return error_response(
                message="Konfirmasi password harus diisi",
                error_code="missing_confirm_password",
                status_code=400
            )
        
        # Validate password match
        if new_password != confirm_password:
            return error_response(
                message="Password baru dan konfirmasi password tidak sama",
                error_code="password_mismatch",
                status_code=400
            )
        
        # Validate password length
        if len(new_password) < 6:
            return error_response(
                message="Password baru minimal 6 karakter",
                error_code="password_too_short",
                status_code=400
            )
        
        # Check if new password is same as old password
        if old_password == new_password:
            return error_response(
                message="Password baru tidak boleh sama dengan password lama",
                error_code="same_password",
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
        
        # Change password
        result = user_model.change_password(user_id, old_password, new_password)
        
        if not result['success']:
            if result['error'] == 'Current password is incorrect':
                return error_response(
                    message="Password lama tidak sesuai",
                    error_code="wrong_old_password",
                    status_code=401
                )
            return error_response(
                message=result.get('error', 'Gagal mengubah password'),
                error_code="change_password_failed",
                status_code=500
            )
        
        return success_response(
            data=None,
            message="Password berhasil diubah"
        )
        
    except Exception as e:
        current_app.logger.error(f"Change password error: {str(e)}")
        return error_response(
            message="Terjadi kesalahan saat mengubah password",
            error_code="server_error",
            status_code=500
        )
