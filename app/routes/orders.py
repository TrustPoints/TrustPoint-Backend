import logging
from typing import Optional, Tuple
from flask import Blueprint, request, current_app

from app.models.order import Order, OrderStatus, ItemCategory
from app.models.user import User
from app.models.activity import Activity
from app.utils.auth import token_required, get_current_user_id
from app.utils.responses import (
    success_response, error_response, validation_error,
    unauthorized_error, not_found_error, forbidden_error,
    database_error, missing_data_error, server_error
)
from app.utils.validators import validate_order_creation, validate_nearby_query
from app.utils.helpers import clamp

logger = logging.getLogger(__name__)

orders_bp = Blueprint('orders', __name__)


# =============================================================================
# Constants
# =============================================================================

ITEM_CATEGORIES = [
    {'code': 'FOOD', 'name': 'Makanan', 'icon': '🍔'},
    {'code': 'DOCUMENT', 'name': 'Dokumen', 'icon': '📄'},
    {'code': 'ELECTRONICS', 'name': 'Elektronik', 'icon': '📱'},
    {'code': 'FASHION', 'name': 'Fashion', 'icon': '👕'},
    {'code': 'GROCERY', 'name': 'Groceries', 'icon': '🛒'},
    {'code': 'MEDICINE', 'name': 'Obat', 'icon': '💊'},
    {'code': 'OTHER', 'name': 'Lainnya', 'icon': '📦'}
]

VALID_SENDER_STATUSES = {OrderStatus.PENDING, OrderStatus.CLAIMED, 
                         OrderStatus.IN_TRANSIT, OrderStatus.DELIVERED, OrderStatus.CANCELLED}
VALID_HUNTER_STATUSES = {OrderStatus.CLAIMED, OrderStatus.IN_TRANSIT, OrderStatus.DELIVERED}
CANCELLABLE_STATUSES = {OrderStatus.PENDING, OrderStatus.CLAIMED}


# =============================================================================
# Helper Functions
# =============================================================================

def _get_db():
    mongo = current_app.extensions.get('pymongo')
    return mongo.db if mongo else None


def _get_authenticated_user_id() -> Tuple[Optional[str], Optional[tuple]]:
    user_id = get_current_user_id()
    if not user_id:
        return None, unauthorized_error()
    return user_id, None


def _get_order_or_error(order_model: Order, order_id: str) -> Tuple[Optional[dict], Optional[tuple]]:
    order = order_model.find_by_id(order_id)
    if not order:
        return None, not_found_error("Pesanan")
    return order, None


def _parse_pagination_params(default_limit: int = 50, max_limit: int = 100) -> Tuple[int, int]:
    try:
        limit = clamp(int(request.args.get('limit', default_limit)), min_val=1, max_val=max_limit)
        skip = max(int(request.args.get('skip', 0)), 0)
    except ValueError:
        limit, skip = default_limit, 0
    return limit, skip


def _format_map_markers(orders: list) -> list:
    return [{
        'order_id': order['order_id'],
        'pickup_coordinates': order['pickup_coordinates'],
        'destination_coordinates': order['destination_coordinates'],
        'item_name': order['item']['name'],
        'item_category': order['item']['category'],
        'distance_km': order['distance_km'],
        'trust_points_reward': order['trust_points_reward']
    } for order in orders]


# =============================================================================
# Order Creation & Estimation
# =============================================================================

@orders_bp.route('/orders', methods=['POST'])
@token_required
def create_order():
    sender_id, err = _get_authenticated_user_id()
    if err:
        return err
    
    data = request.get_json()
    if not data:
        return missing_data_error()
    
    is_valid, errors = validate_order_creation(data)
    if not is_valid:
        return validation_error(errors)
    
    db = _get_db()
    if db is None:
        return database_error()
    
    try:
        order_model = Order(db)
        user_model = User(db)
        
        # Calculate delivery cost
        distance_km = data['distance_km']
        weight_kg = data['item'].get('weight', 0)
        is_fragile = data['item'].get('is_fragile', False)
        points_cost = order_model.calculate_delivery_cost(distance_km, weight_kg, is_fragile)
        
        # Check sender balance
        user_points = user_model.get_points(sender_id)
        if not user_points['success']:
            return error_response(
                message="Gagal mengecek saldo points",
                error_code="balance_check_failed",
                status_code=400
            )
        
        current_balance = user_points['points']
        if current_balance < points_cost:
            return error_response(
                message="Saldo tidak mencukupi. Butuh lebih banyak points.",
                error_code="insufficient_points",
                status_code=400,
                data={
                    'required_points': points_cost,
                    'current_balance': current_balance,
                    'shortage': points_cost - current_balance
                }
            )
        
        # Deduct points
        deduct_result = user_model.deduct_points(
            sender_id, points_cost, "Payment for delivery order"
        )
        if not deduct_result['success']:
            return error_response(
                message="Gagal memotong saldo points",
                error_code="payment_failed",
                status_code=400
            )
        
        # Create order
        order = order_model.create_order(
            sender_id=sender_id,
            item_data=data['item'],
            location_data=data['location'],
            distance_km=data['distance_km'],
            notes=data.get('notes')
        )
        
        # Log activity
        Activity(db).log_order_created(
            user_id=sender_id,
            order_id=order.get('order_id', ''),
            points_cost=points_cost
        )
        
        return success_response(
            data={
                'order': order,
                'payment': {
                    'points_deducted': points_cost,
                    'new_balance': deduct_result['new_balance']
                }
            },
            message=f"Pesanan berhasil dibuat. {points_cost} pts telah dipotong dari saldo Anda.",
            status_code=201
        )
    except Exception:
        logger.exception("Create order error")
        return server_error("Terjadi kesalahan saat membuat pesanan")


@orders_bp.route('/orders/estimate-cost', methods=['POST'])
@token_required
def estimate_delivery_cost():
    user_id, err = _get_authenticated_user_id()
    if err:
        return err
    
    data = request.get_json()
    if not data or 'distance_km' not in data:
        return error_response(
            message="Distance (distance_km) diperlukan",
            error_code="missing_distance",
            status_code=400
        )
    
    db = _get_db()
    if db is None:
        return database_error()
    
    try:
        distance_km = float(data.get('distance_km', 0))
        weight_kg = float(data.get('weight_kg', 0))
        is_fragile = data.get('is_fragile', False)
        
        # Calculate costs
        points_cost = Order.calculate_delivery_cost(distance_km, weight_kg, is_fragile)
        hunter_reward = Order.calculate_trust_points(distance_km, is_fragile)
        
        # Get user balance
        user_model = User(db)
        user_points = user_model.get_points(user_id)
        current_balance = user_points.get('points', 0) if user_points['success'] else 0
        
        return success_response(
            data={
                'estimated_cost': points_cost,
                'hunter_reward': hunter_reward,
                'current_balance': current_balance,
                'can_afford': current_balance >= points_cost,
                'shortage': max(0, points_cost - current_balance),
                'breakdown': {
                    'base_cost': int(distance_km * 10),
                    'weight_surcharge': int((weight_kg - 1) * 5) if weight_kg > 1 else 0,
                    'fragile_surcharge': '20%' if is_fragile else '0%'
                }
            },
            message="Estimasi biaya pengiriman"
        )
    except Exception:
        logger.exception("Estimate cost error")
        return server_error("Terjadi kesalahan saat menghitung estimasi")


# =============================================================================
# Order Discovery (Hunter)
# =============================================================================

@orders_bp.route('/orders/available', methods=['GET'])
@token_required
def get_available_orders():
    user_id, err = _get_authenticated_user_id()
    if err:
        return err
    
    limit, skip = _parse_pagination_params()
    
    db = _get_db()
    if db is None:
        return database_error()
    
    try:
        order_model = Order(db)
        orders = order_model.get_available_orders(limit=limit, skip=skip)
        total = order_model.count_available_orders()
        
        return success_response(
            data={
                'orders': orders,
                'map_markers': _format_map_markers(orders),
                'total': total,
                'limit': limit,
                'skip': skip
            },
            message="Daftar pesanan tersedia"
        )
    except Exception:
        logger.exception("Get available orders error")
        return server_error("Terjadi kesalahan saat mengambil daftar pesanan")


@orders_bp.route('/orders/nearby', methods=['GET'])
@token_required
def get_nearby_orders():
    user_id, err = _get_authenticated_user_id()
    if err:
        return err
    
    # Validate coordinates
    is_valid, errors, parsed = validate_nearby_query(
        request.args.get('lat'),
        request.args.get('lng'),
        request.args.get('radius')
    )
    if not is_valid:
        return validation_error(errors)
    
    limit, _ = _parse_pagination_params()
    
    db = _get_db()
    if db is None:
        return database_error()
    
    try:
        order_model = Order(db)
        orders = order_model.get_nearby_orders(
            latitude=parsed['latitude'],
            longitude=parsed['longitude'],
            radius_km=parsed['radius'],
            limit=limit
        )
        
        return success_response(
            data={
                'orders': orders,
                'map_markers': _format_map_markers(orders),
                'search_params': {
                    'latitude': parsed['latitude'],
                    'longitude': parsed['longitude'],
                    'radius_km': parsed['radius']
                },
                'count': len(orders)
            },
            message=f"Ditemukan {len(orders)} pesanan dalam radius {parsed['radius']} km"
        )
    except Exception:
        logger.exception("Get nearby orders error")
        return server_error("Terjadi kesalahan saat mencari pesanan terdekat")


# =============================================================================
# Order Details
# =============================================================================

@orders_bp.route('/orders/<order_id>', methods=['GET'])
@token_required
def get_order_detail(order_id):
    user_id, err = _get_authenticated_user_id()
    if err:
        return err
    
    db = _get_db()
    if db is None:
        return database_error()
    
    try:
        order_model = Order(db)
        order, err = _get_order_or_error(order_model, order_id)
        if err:
            return err
        
        return success_response(
            data={'order': order},
            message="Detail pesanan"
        )
    except Exception:
        logger.exception("Get order detail error")
        return server_error("Terjadi kesalahan saat mengambil detail pesanan")


# =============================================================================
# Order Lifecycle (Hunter Actions)
# =============================================================================

@orders_bp.route('/orders/claim/<order_id>', methods=['PUT'])
@token_required
def claim_order(order_id):
    hunter_id, err = _get_authenticated_user_id()
    if err:
        return err
    
    db = _get_db()
    if db is None:
        return database_error()
    
    try:
        order_model = Order(db)
        existing_order, err = _get_order_or_error(order_model, order_id)
        if err:
            return err
        
        # Validate claim conditions
        if existing_order['sender_id'] == hunter_id:
            return error_response(
                message="Tidak dapat mengambil pesanan sendiri",
                error_code="cannot_claim_own_order",
                status_code=400
            )
        
        if existing_order['status'] != OrderStatus.PENDING:
            return error_response(
                message=f"Pesanan tidak dapat diambil (status: {existing_order['status']})",
                error_code="order_not_available",
                status_code=400
            )
        
        # Claim order
        order = order_model.claim_order(order_id, hunter_id)
        if not order:
            return error_response(
                message="Gagal mengambil pesanan. Mungkin sudah diambil orang lain.",
                error_code="claim_failed",
                status_code=400
            )
        
        # Log activity
        Activity(db).log_order_claimed(user_id=hunter_id, order_id=order_id)
        
        return success_response(
            data={'order': order},
            message="Pesanan berhasil diambil! Silakan menuju lokasi pickup."
        )
    except Exception:
        logger.exception("Claim order error")
        return server_error("Terjadi kesalahan saat mengambil pesanan")


@orders_bp.route('/orders/pickup/<order_id>', methods=['PUT'])
@token_required
def pickup_order(order_id):
    hunter_id, err = _get_authenticated_user_id()
    if err:
        return err
    
    db = _get_db()
    if db is None:
        return database_error()
    
    try:
        order_model = Order(db)
        existing_order, err = _get_order_or_error(order_model, order_id)
        if err:
            return err
        
        # Check ownership
        if existing_order['hunter_id'] != hunter_id:
            return forbidden_error("pesanan ini")
        
        # Start delivery
        order = order_model.start_delivery(order_id, hunter_id)
        if not order:
            return error_response(
                message="Gagal memulai pengiriman. Pastikan pesanan dalam status CLAIMED.",
                error_code="pickup_failed",
                status_code=400
            )
        
        return success_response(
            data={'order': order},
            message="Pengiriman dimulai! Silakan menuju lokasi tujuan."
        )
    except Exception:
        logger.exception("Pickup order error")
        return server_error("Terjadi kesalahan saat memulai pengiriman")


@orders_bp.route('/orders/deliver/<order_id>', methods=['PUT'])
@token_required
def deliver_order(order_id):
    hunter_id, err = _get_authenticated_user_id()
    if err:
        return err
    
    db = _get_db()
    if db is None:
        return database_error()
    
    try:
        order_model = Order(db)
        existing_order, err = _get_order_or_error(order_model, order_id)
        if err:
            return err
        
        # Check ownership
        if existing_order['hunter_id'] != hunter_id:
            return forbidden_error("pesanan ini")
        
        # Complete delivery
        order = order_model.complete_delivery(order_id, hunter_id)
        if not order:
            return error_response(
                message="Gagal menyelesaikan pengiriman. Pastikan pesanan dalam status IN_TRANSIT.",
                error_code="delivery_failed",
                status_code=400
            )
        
        # Award trust points
        trust_points_earned = order['trust_points_reward']
        user_model = User(db)
        points_result = user_model.add_points(
            hunter_id, trust_points_earned, f"Delivery completed: {order_id}"
        )
        
        if not points_result['success']:
            logger.warning(f"Failed to add points for hunter {hunter_id}: {points_result.get('error')}")
        
        # Log activity
        Activity(db).log_order_delivered(
            user_id=hunter_id,
            order_id=order_id,
            points_earned=trust_points_earned
        )
        
        return success_response(
            data={
                'order': order,
                'trust_points_earned': trust_points_earned,
                'new_points_balance': points_result.get('new_balance', 0) if points_result['success'] else None
            },
            message=f"Pengiriman selesai! Anda mendapatkan {trust_points_earned} Trust Points."
        )
    except Exception:
        logger.exception("Deliver order error")
        return server_error("Terjadi kesalahan saat menyelesaikan pengiriman")


# =============================================================================
# Order Management (Sender Actions)
# =============================================================================

@orders_bp.route('/orders/cancel/<order_id>', methods=['PUT'])
@token_required
def cancel_order(order_id):
    sender_id, err = _get_authenticated_user_id()
    if err:
        return err
    
    db = _get_db()
    if db is None:
        return database_error()
    
    try:
        order_model = Order(db)
        existing_order, err = _get_order_or_error(order_model, order_id)
        if err:
            return err
        
        # Check ownership
        if existing_order['sender_id'] != sender_id:
            return forbidden_error("pesanan ini")
        
        # Check if cancellable
        if existing_order['status'] not in CANCELLABLE_STATUSES:
            return error_response(
                message=f"Pesanan dengan status {existing_order['status']} tidak dapat dibatalkan",
                error_code="cannot_cancel",
                status_code=400
            )
        
        # Cancel order
        order = order_model.cancel_order(order_id, sender_id)
        if not order:
            return error_response(
                message="Gagal membatalkan pesanan",
                error_code="cancel_failed",
                status_code=400
            )
        
        return success_response(
            data={'order': order},
            message="Pesanan berhasil dibatalkan"
        )
    except Exception:
        logger.exception("Cancel order error")
        return server_error("Terjadi kesalahan saat membatalkan pesanan")


# =============================================================================
# Order History
# =============================================================================

@orders_bp.route('/orders/my-orders', methods=['GET'])
@token_required
def get_my_orders():
    user_id, err = _get_authenticated_user_id()
    if err:
        return err
    
    # Parse and validate status
    status = request.args.get('status')
    if status and status not in VALID_SENDER_STATUSES:
        status = None
    
    limit, skip = _parse_pagination_params()
    
    db = _get_db()
    if db is None:
        return database_error()
    
    try:
        order_model = Order(db)
        orders = order_model.get_sender_orders(user_id, status=status, limit=limit, skip=skip)
        
        return success_response(
            data={
                'orders': orders,
                'count': len(orders),
                'limit': limit,
                'skip': skip
            },
            message="Daftar pesanan Anda"
        )
    except Exception:
        logger.exception("Get my orders error")
        return server_error("Terjadi kesalahan saat mengambil daftar pesanan")


@orders_bp.route('/orders/my-deliveries', methods=['GET'])
@token_required
def get_my_deliveries():
    user_id, err = _get_authenticated_user_id()
    if err:
        return err
    
    # Parse and validate status
    status = request.args.get('status')
    if status and status not in VALID_HUNTER_STATUSES:
        status = None
    
    limit, skip = _parse_pagination_params()
    
    db = _get_db()
    if db is None:
        return database_error()
    
    try:
        order_model = Order(db)
        orders = order_model.get_hunter_orders(user_id, status=status, limit=limit, skip=skip)
        
        return success_response(
            data={
                'orders': orders,
                'count': len(orders),
                'limit': limit,
                'skip': skip
            },
            message="Daftar pengiriman Anda"
        )
    except Exception:
        logger.exception("Get my deliveries error")
        return server_error("Terjadi kesalahan saat mengambil daftar pengiriman")


# =============================================================================
# Reference Data
# =============================================================================

@orders_bp.route('/orders/categories', methods=['GET'])
def get_categories():
    return success_response(
        data={'categories': ITEM_CATEGORIES},
        message="Daftar kategori barang"
    )
