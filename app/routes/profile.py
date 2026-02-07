import logging
from flask import Blueprint, request, current_app

from app.models.user import User
from app.utils.auth import token_required, get_current_user_id
from app.utils.responses import (
    success_response, error_response, validation_error,
    unauthorized_error, not_found_error, database_error, 
    missing_data_error, server_error
)
from app.utils.validators import validate_profile_update

logger = logging.getLogger(__name__)

profile_bp = Blueprint('profile', __name__)


# =============================================================================
# Helper Functions
# =============================================================================

def _get_db():
    mongo = current_app.extensions.get('pymongo')
    return mongo.db if mongo else None


def _get_authenticated_user_id() -> tuple:
    user_id = get_current_user_id()
    if not user_id:
        return None, unauthorized_error()
    return user_id, None


# =============================================================================
# Profile Endpoints
# =============================================================================

@profile_bp.route('/profile', methods=['GET'])
@token_required
def get_profile():
    user_id, err = _get_authenticated_user_id()
    if err:
        return err
    
    db = _get_db()
    if db is None:
        return database_error()
    
    try:
        user_model = User(db)
        user = user_model.find_by_id(user_id)
        
        if not user:
            return not_found_error("User")
        
        return success_response(
            data={'user': user},
            message="Profil berhasil diambil"
        )
    except Exception:
        logger.exception("Get profile error")
        return server_error("Terjadi kesalahan saat mengambil profil")


@profile_bp.route('/profile/edit', methods=['PUT'])
@token_required
def update_profile():
    user_id, err = _get_authenticated_user_id()
    if err:
        return err
    
    data = request.get_json()
    if not data:
        return missing_data_error()
    
    is_valid, errors = validate_profile_update(data)
    if not is_valid:
        return validation_error(errors)
    
    # Filter to valid fields only
    update_data = {
        k: v for k, v in data.items() 
        if k in User.UPDATABLE_FIELDS
    }
    
    if not update_data:
        return error_response(
            message="Tidak ada data yang valid untuk diupdate",
            error_code="no_valid_data",
            status_code=400
        )
    
    db = _get_db()
    if db is None:
        return database_error()
    
    try:
        user_model = User(db)
        
        if not user_model.find_by_id(user_id):
            return not_found_error("User")
        
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
    except Exception:
        logger.exception("Update profile error")
        return server_error("Terjadi kesalahan saat mengupdate profil")


# =============================================================================
# Password Management
# =============================================================================

@profile_bp.route('/profile/change-password', methods=['POST'])
@token_required
def change_password():
    user_id, err = _get_authenticated_user_id()
    if err:
        return err
    
    data = request.get_json()
    if not data:
        return missing_data_error()
    
    # Extract and validate fields
    old_password = data.get('old_password', '').strip()
    new_password = data.get('new_password', '').strip()
    confirm_password = data.get('confirm_password', '').strip()
    
    # Validation checks
    validation_checks = [
        (not old_password, "Password lama harus diisi", "missing_old_password"),
        (not new_password, "Password baru harus diisi", "missing_new_password"),
        (not confirm_password, "Konfirmasi password harus diisi", "missing_confirm_password"),
        (new_password != confirm_password, "Password baru dan konfirmasi password tidak sama", "password_mismatch"),
        (len(new_password) < 6, "Password baru minimal 6 karakter", "password_too_short"),
        (old_password == new_password, "Password baru tidak boleh sama dengan password lama", "same_password"),
    ]
    
    for condition, message, code in validation_checks:
        if condition:
            return error_response(message=message, error_code=code, status_code=400)
    
    db = _get_db()
    if db is None:
        return database_error()
    
    try:
        user_model = User(db)
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
        
        return success_response(data=None, message="Password berhasil diubah")
    except Exception:
        logger.exception("Change password error")
        return server_error("Terjadi kesalahan saat mengubah password")
