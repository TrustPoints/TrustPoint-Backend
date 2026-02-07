import logging
from typing import Optional
from flask import Blueprint, request, current_app

from app.models.user import User
from app.utils.auth import token_required, get_current_user_id
from app.utils.responses import (
    success_response, error_response,
    database_error, missing_data_error, not_found_error
)

logger = logging.getLogger(__name__)

wallet_bp = Blueprint('wallet', __name__)


# =============================================================================
# Helper Functions
# =============================================================================

def _get_db():
    mongo = current_app.extensions.get('pymongo')
    return mongo.db if mongo else None


def _validate_points(points) -> Optional[tuple]:
    if not isinstance(points, int) or points <= 0:
        return ("Poin harus berupa bilangan positif", "invalid_points")
    return None


def _format_balance_response(balance: int) -> dict:
    return {
        'points': balance,
        'rupiah_equivalent': balance * User.POINTS_TO_RUPIAH,
        'conversion_rate': f'1 pts = Rp{User.POINTS_TO_RUPIAH}'
    }


# =============================================================================
# Balance Endpoints
# =============================================================================

@wallet_bp.route('/balance', methods=['GET'])
@token_required
def get_balance():
    user_id = get_current_user_id()
    
    db = _get_db()
    if db is None:
        return database_error()
    
    user_model = User(db)
    result = user_model.get_points(user_id)
    
    if result['success']:
        return success_response(
            data={
                'points': result['points'],
                'rupiah_equivalent': result['rupiah_equivalent'],
                'conversion_rate': f'1 pts = Rp{User.POINTS_TO_RUPIAH}'
            },
            message="Berhasil mendapatkan saldo"
        )
    
    return error_response(
        message=result.get('error', 'Gagal mendapatkan saldo'),
        error_code="get_balance_failed",
        status_code=400
    )


# =============================================================================
# Points Operations
# =============================================================================

@wallet_bp.route('/earn', methods=['POST'])
@token_required
def earn_points():
    user_id = get_current_user_id()
    data = request.get_json()
    
    if not data or 'points' not in data:
        return error_response(
            message="Jumlah poin diperlukan",
            error_code="missing_points",
            status_code=400
        )
    
    points = data.get('points', 0)
    reason = data.get('reason', 'Points earned')
    
    validation_err = _validate_points(points)
    if validation_err:
        return error_response(
            message=validation_err[0],
            error_code=validation_err[1],
            status_code=400
        )
    
    db = _get_db()
    if db is None:
        return database_error()
    
    user_model = User(db)
    result = user_model.add_points(user_id, points, reason)
    
    if result['success']:
        return success_response(
            data={
                'added': result['added'],
                'new_balance': result['new_balance'],
                'rupiah_equivalent': result['new_balance'] * User.POINTS_TO_RUPIAH
            },
            message=f'Berhasil mendapatkan {points} pts'
        )
    
    return error_response(
        message=result.get('error', 'Gagal menambah poin'),
        error_code="earn_failed",
        status_code=400
    )


@wallet_bp.route('/redeem', methods=['POST'])
@token_required
def redeem_points():
    user_id = get_current_user_id()
    data = request.get_json()
    
    if not data or 'points' not in data:
        return error_response(
            message="Jumlah poin diperlukan",
            error_code="missing_points",
            status_code=400
        )
    
    points = data.get('points', 0)
    reason = data.get('reason', 'Points redeemed')
    
    validation_err = _validate_points(points)
    if validation_err:
        return error_response(
            message=validation_err[0],
            error_code=validation_err[1],
            status_code=400
        )
    
    db = _get_db()
    if db is None:
        return database_error()
    
    user_model = User(db)
    result = user_model.deduct_points(user_id, points, reason)
    
    if result['success']:
        return success_response(
            data={
                'redeemed': result['deducted'],
                'new_balance': result['new_balance'],
                'rupiah_equivalent': result['new_balance'] * User.POINTS_TO_RUPIAH
            },
            message=f'Berhasil menukarkan {points} pts'
        )
    
    return error_response(
        message=result.get('error', 'Gagal menukarkan poin'),
        error_code="redeem_failed",
        status_code=400
    )


# =============================================================================
# Transfer Operations
# =============================================================================

@wallet_bp.route('/transfer', methods=['POST'])
@token_required
def transfer_points():
    user_id = get_current_user_id()
    data = request.get_json()
    
    if not data:
        return missing_data_error()
    
    recipient_email = data.get('recipient_email')
    points = data.get('points', 0)
    
    if not recipient_email:
        return error_response(
            message="Email penerima diperlukan",
            error_code="missing_recipient",
            status_code=400
        )
    
    validation_err = _validate_points(points)
    if validation_err:
        return error_response(
            message=validation_err[0],
            error_code=validation_err[1],
            status_code=400
        )
    
    db = _get_db()
    if db is None:
        return database_error()
    
    user_model = User(db)
    
    # Find recipient
    recipient = user_model.find_by_email(recipient_email)
    if not recipient:
        return not_found_error("Penerima")
    
    recipient_id = str(recipient['_id'])
    
    # Prevent self-transfer
    if recipient_id == user_id:
        return error_response(
            message="Tidak dapat transfer ke diri sendiri",
            error_code="self_transfer",
            status_code=400
        )
    
    # Deduct from sender
    deduct_result = user_model.deduct_points(
        user_id, points, f'Transfer to {recipient_email}'
    )
    if not deduct_result['success']:
        return error_response(
            message=deduct_result.get('error', 'Gagal transfer poin'),
            error_code="transfer_failed",
            status_code=400
        )
    
    # Add to recipient
    add_result = user_model.add_points(
        recipient_id, points, 'Transfer from user'
    )
    if not add_result['success']:
        # Rollback - refund sender
        user_model.add_points(user_id, points, 'Refund - transfer failed')
        return error_response(
            message="Gagal menyelesaikan transfer",
            error_code="transfer_incomplete",
            status_code=400
        )
    
    return success_response(
        data={
            'transferred': points,
            'new_balance': deduct_result['new_balance'],
            'rupiah_equivalent': deduct_result['new_balance'] * User.POINTS_TO_RUPIAH
        },
        message=f'Berhasil transfer {points} pts ke {recipient_email}'
    )

