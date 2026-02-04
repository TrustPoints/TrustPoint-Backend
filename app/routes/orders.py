"""
TrustPoints Order Routes
Handles order/delivery operations for Sender and Hunter
"""
from flask import Blueprint, request, current_app
from app.models.order import Order, OrderStatus, ItemCategory
from app.utils.auth import token_required, get_current_user_id
from app.utils.responses import success_response, error_response, validation_error
from app.utils.validators import validate_order_creation, validate_nearby_query

orders_bp = Blueprint('orders', __name__)


@orders_bp.route('/orders', methods=['POST'])
@token_required
def create_order():
    """
    Create a new order (Sender endpoint)
    
    Headers:
        Authorization: Bearer <token>
    
    Request Body:
        {
            "item": {
                "name": "string",
                "category": "FOOD|DOCUMENT|ELECTRONICS|FASHION|GROCERY|MEDICINE|OTHER",
                "weight": float (kg),
                "photo_url": "string" (optional),
                "description": "string" (optional),
                "is_fragile": boolean
            },
            "location": {
                "pickup": {
                    "address": "string",
                    "latitude": float,
                    "longitude": float
                },
                "destination": {
                    "address": "string",
                    "latitude": float,
                    "longitude": float
                }
            },
            "distance_km": float,
            "notes": "string" (optional)
        }
    
    Returns:
        201: Order created successfully
        400: Validation error
        401: Unauthorized
    """
    try:
        sender_id = get_current_user_id()
        
        if not sender_id:
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
        
        # Validate order data
        is_valid, errors = validate_order_creation(data)
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
        
        order_model = Order(mongo.db)
        
        # Create order
        order = order_model.create_order(
            sender_id=sender_id,
            item_data=data['item'],
            location_data=data['location'],
            distance_km=data['distance_km'],
            notes=data.get('notes')
        )
        
        return success_response(
            data={'order': order},
            message="Pesanan berhasil dibuat",
            status_code=201
        )
        
    except Exception as e:
        current_app.logger.error(f"Create order error: {str(e)}")
        return error_response(
            message="Terjadi kesalahan saat membuat pesanan",
            error_code="server_error",
            status_code=500
        )


@orders_bp.route('/orders/available', methods=['GET'])
@token_required
def get_available_orders():
    """
    Get all available orders (PENDING status) for Hunters
    Used for displaying markers on map and list view
    
    Headers:
        Authorization: Bearer <token>
    
    Query Parameters:
        limit: int (default 50, max 100)
        skip: int (default 0)
    
    Returns:
        200: List of available orders with coordinates for map markers
    """
    try:
        user_id = get_current_user_id()
        
        if not user_id:
            return error_response(
                message="User tidak terautentikasi",
                error_code="unauthorized",
                status_code=401
            )
        
        # Parse query parameters
        try:
            limit = min(int(request.args.get('limit', 50)), 100)
            skip = max(int(request.args.get('skip', 0)), 0)
        except ValueError:
            limit, skip = 50, 0
        
        # Get MongoDB from app context
        mongo = current_app.extensions.get('pymongo')
        if not mongo:
            return error_response(
                message="Database tidak tersedia",
                error_code="database_error",
                status_code=500
            )
        
        order_model = Order(mongo.db)
        orders = order_model.get_available_orders(limit=limit, skip=skip)
        total = order_model.count_available_orders()
        
        # Format for map markers (simplified data)
        map_markers = []
        for order in orders:
            map_markers.append({
                'order_id': order['order_id'],
                'pickup_coordinates': order['pickup_coordinates'],
                'destination_coordinates': order['destination_coordinates'],
                'item_name': order['item']['name'],
                'item_category': order['item']['category'],
                'distance_km': order['distance_km'],
                'trust_points_reward': order['trust_points_reward']
            })
        
        return success_response(
            data={
                'orders': orders,
                'map_markers': map_markers,
                'total': total,
                'limit': limit,
                'skip': skip
            },
            message="Daftar pesanan tersedia"
        )
        
    except Exception as e:
        current_app.logger.error(f"Get available orders error: {str(e)}")
        return error_response(
            message="Terjadi kesalahan saat mengambil daftar pesanan",
            error_code="server_error",
            status_code=500
        )


@orders_bp.route('/orders/nearby', methods=['GET'])
@token_required
def get_nearby_orders():
    """
    Get orders near a specific location (Geospatial query)
    
    Headers:
        Authorization: Bearer <token>
    
    Query Parameters:
        lat: float (required) - User's latitude
        lng: float (required) - User's longitude
        radius: float (optional, default 10) - Search radius in km (max 50)
        limit: int (optional, default 50)
    
    Returns:
        200: List of nearby orders sorted by distance
    """
    try:
        user_id = get_current_user_id()
        
        if not user_id:
            return error_response(
                message="User tidak terautentikasi",
                error_code="unauthorized",
                status_code=401
            )
        
        # Validate query parameters
        lat = request.args.get('lat')
        lng = request.args.get('lng')
        radius = request.args.get('radius')
        
        is_valid, errors, parsed = validate_nearby_query(lat, lng, radius)
        if not is_valid:
            return validation_error(errors)
        
        try:
            limit = min(int(request.args.get('limit', 50)), 100)
        except ValueError:
            limit = 50
        
        # Get MongoDB from app context
        mongo = current_app.extensions.get('pymongo')
        if not mongo:
            return error_response(
                message="Database tidak tersedia",
                error_code="database_error",
                status_code=500
            )
        
        order_model = Order(mongo.db)
        orders = order_model.get_nearby_orders(
            latitude=parsed['latitude'],
            longitude=parsed['longitude'],
            radius_km=parsed['radius'],
            limit=limit
        )
        
        # Format for map markers
        map_markers = []
        for order in orders:
            map_markers.append({
                'order_id': order['order_id'],
                'pickup_coordinates': order['pickup_coordinates'],
                'destination_coordinates': order['destination_coordinates'],
                'item_name': order['item']['name'],
                'item_category': order['item']['category'],
                'distance_km': order['distance_km'],
                'trust_points_reward': order['trust_points_reward']
            })
        
        return success_response(
            data={
                'orders': orders,
                'map_markers': map_markers,
                'search_params': {
                    'latitude': parsed['latitude'],
                    'longitude': parsed['longitude'],
                    'radius_km': parsed['radius']
                },
                'count': len(orders)
            },
            message=f"Ditemukan {len(orders)} pesanan dalam radius {parsed['radius']} km"
        )
        
    except Exception as e:
        current_app.logger.error(f"Get nearby orders error: {str(e)}")
        return error_response(
            message="Terjadi kesalahan saat mencari pesanan terdekat",
            error_code="server_error",
            status_code=500
        )


@orders_bp.route('/orders/<order_id>', methods=['GET'])
@token_required
def get_order_detail(order_id):
    """
    Get order detail by order_id
    
    Headers:
        Authorization: Bearer <token>
    
    Returns:
        200: Order detail
        404: Order not found
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
        
        order_model = Order(mongo.db)
        order = order_model.find_by_id(order_id)
        
        if not order:
            return error_response(
                message="Pesanan tidak ditemukan",
                error_code="order_not_found",
                status_code=404
            )
        
        return success_response(
            data={'order': order},
            message="Detail pesanan"
        )
        
    except Exception as e:
        current_app.logger.error(f"Get order detail error: {str(e)}")
        return error_response(
            message="Terjadi kesalahan saat mengambil detail pesanan",
            error_code="server_error",
            status_code=500
        )


@orders_bp.route('/orders/claim/<order_id>', methods=['PUT'])
@token_required
def claim_order(order_id):
    """
    Hunter claims an order
    Changes status from PENDING to CLAIMED
    
    Headers:
        Authorization: Bearer <token>
    
    Returns:
        200: Order claimed successfully
        400: Cannot claim order (already claimed, own order, etc)
        404: Order not found
    """
    try:
        hunter_id = get_current_user_id()
        
        if not hunter_id:
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
        
        order_model = Order(mongo.db)
        
        # Check if order exists
        existing_order = order_model.find_by_id(order_id)
        if not existing_order:
            return error_response(
                message="Pesanan tidak ditemukan",
                error_code="order_not_found",
                status_code=404
            )
        
        # Check if trying to claim own order
        if existing_order['sender_id'] == hunter_id:
            return error_response(
                message="Tidak dapat mengambil pesanan sendiri",
                error_code="cannot_claim_own_order",
                status_code=400
            )
        
        # Check if order is still pending
        if existing_order['status'] != OrderStatus.PENDING:
            return error_response(
                message=f"Pesanan tidak dapat diambil (status: {existing_order['status']})",
                error_code="order_not_available",
                status_code=400
            )
        
        # Claim the order
        order = order_model.claim_order(order_id, hunter_id)
        
        if not order:
            return error_response(
                message="Gagal mengambil pesanan. Mungkin sudah diambil orang lain.",
                error_code="claim_failed",
                status_code=400
            )
        
        return success_response(
            data={'order': order},
            message="Pesanan berhasil diambil! Silakan menuju lokasi pickup."
        )
        
    except Exception as e:
        current_app.logger.error(f"Claim order error: {str(e)}")
        return error_response(
            message="Terjadi kesalahan saat mengambil pesanan",
            error_code="server_error",
            status_code=500
        )


@orders_bp.route('/orders/pickup/<order_id>', methods=['PUT'])
@token_required
def pickup_order(order_id):
    """
    Hunter picks up the item (starts delivery)
    Changes status from CLAIMED to IN_TRANSIT
    
    Headers:
        Authorization: Bearer <token>
    
    Returns:
        200: Delivery started
        400: Cannot start delivery
        404: Order not found
    """
    try:
        hunter_id = get_current_user_id()
        
        if not hunter_id:
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
        
        order_model = Order(mongo.db)
        
        # Check if order exists
        existing_order = order_model.find_by_id(order_id)
        if not existing_order:
            return error_response(
                message="Pesanan tidak ditemukan",
                error_code="order_not_found",
                status_code=404
            )
        
        # Check if hunter owns this claimed order
        if existing_order['hunter_id'] != hunter_id:
            return error_response(
                message="Anda tidak memiliki akses ke pesanan ini",
                error_code="not_your_order",
                status_code=403
            )
        
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
        
    except Exception as e:
        current_app.logger.error(f"Pickup order error: {str(e)}")
        return error_response(
            message="Terjadi kesalahan saat memulai pengiriman",
            error_code="server_error",
            status_code=500
        )


@orders_bp.route('/orders/deliver/<order_id>', methods=['PUT'])
@token_required
def deliver_order(order_id):
    """
    Hunter completes delivery
    Changes status from IN_TRANSIT to DELIVERED
    
    Headers:
        Authorization: Bearer <token>
    
    Returns:
        200: Delivery completed, trust points awarded
        400: Cannot complete delivery
        404: Order not found
    """
    try:
        hunter_id = get_current_user_id()
        
        if not hunter_id:
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
        
        order_model = Order(mongo.db)
        
        # Check if order exists
        existing_order = order_model.find_by_id(order_id)
        if not existing_order:
            return error_response(
                message="Pesanan tidak ditemukan",
                error_code="order_not_found",
                status_code=404
            )
        
        # Check if hunter owns this order
        if existing_order['hunter_id'] != hunter_id:
            return error_response(
                message="Anda tidak memiliki akses ke pesanan ini",
                error_code="not_your_order",
                status_code=403
            )
        
        # Complete delivery
        order = order_model.complete_delivery(order_id, hunter_id)
        
        if not order:
            return error_response(
                message="Gagal menyelesaikan pengiriman. Pastikan pesanan dalam status IN_TRANSIT.",
                error_code="delivery_failed",
                status_code=400
            )
        
        # TODO: Add trust points to hunter's account
        trust_points_earned = order['trust_points_reward']
        
        return success_response(
            data={
                'order': order,
                'trust_points_earned': trust_points_earned
            },
            message=f"Pengiriman selesai! Anda mendapatkan {trust_points_earned} Trust Points."
        )
        
    except Exception as e:
        current_app.logger.error(f"Deliver order error: {str(e)}")
        return error_response(
            message="Terjadi kesalahan saat menyelesaikan pengiriman",
            error_code="server_error",
            status_code=500
        )


@orders_bp.route('/orders/cancel/<order_id>', methods=['PUT'])
@token_required
def cancel_order(order_id):
    """
    Sender cancels an order
    Only PENDING or CLAIMED orders can be cancelled
    
    Headers:
        Authorization: Bearer <token>
    
    Returns:
        200: Order cancelled
        400: Cannot cancel order
        404: Order not found
    """
    try:
        sender_id = get_current_user_id()
        
        if not sender_id:
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
        
        order_model = Order(mongo.db)
        
        # Check if order exists
        existing_order = order_model.find_by_id(order_id)
        if not existing_order:
            return error_response(
                message="Pesanan tidak ditemukan",
                error_code="order_not_found",
                status_code=404
            )
        
        # Check if sender owns this order
        if existing_order['sender_id'] != sender_id:
            return error_response(
                message="Anda tidak memiliki akses ke pesanan ini",
                error_code="not_your_order",
                status_code=403
            )
        
        # Check if order can be cancelled
        if existing_order['status'] not in [OrderStatus.PENDING, OrderStatus.CLAIMED]:
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
        
    except Exception as e:
        current_app.logger.error(f"Cancel order error: {str(e)}")
        return error_response(
            message="Terjadi kesalahan saat membatalkan pesanan",
            error_code="server_error",
            status_code=500
        )


@orders_bp.route('/orders/my-orders', methods=['GET'])
@token_required
def get_my_orders():
    """
    Get current user's orders (as sender)
    
    Headers:
        Authorization: Bearer <token>
    
    Query Parameters:
        status: string (optional) - Filter by status
        limit: int (default 50)
        skip: int (default 0)
    
    Returns:
        200: List of user's orders
    """
    try:
        user_id = get_current_user_id()
        
        if not user_id:
            return error_response(
                message="User tidak terautentikasi",
                error_code="unauthorized",
                status_code=401
            )
        
        # Parse query parameters
        status = request.args.get('status')
        if status and status not in [OrderStatus.PENDING, OrderStatus.CLAIMED, 
                                      OrderStatus.IN_TRANSIT, OrderStatus.DELIVERED,
                                      OrderStatus.CANCELLED]:
            status = None
        
        try:
            limit = min(int(request.args.get('limit', 50)), 100)
            skip = max(int(request.args.get('skip', 0)), 0)
        except ValueError:
            limit, skip = 50, 0
        
        # Get MongoDB from app context
        mongo = current_app.extensions.get('pymongo')
        if not mongo:
            return error_response(
                message="Database tidak tersedia",
                error_code="database_error",
                status_code=500
            )
        
        order_model = Order(mongo.db)
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
        
    except Exception as e:
        current_app.logger.error(f"Get my orders error: {str(e)}")
        return error_response(
            message="Terjadi kesalahan saat mengambil daftar pesanan",
            error_code="server_error",
            status_code=500
        )


@orders_bp.route('/orders/my-deliveries', methods=['GET'])
@token_required
def get_my_deliveries():
    """
    Get current user's deliveries (as hunter)
    
    Headers:
        Authorization: Bearer <token>
    
    Query Parameters:
        status: string (optional) - Filter by status
        limit: int (default 50)
        skip: int (default 0)
    
    Returns:
        200: List of user's deliveries
    """
    try:
        user_id = get_current_user_id()
        
        if not user_id:
            return error_response(
                message="User tidak terautentikasi",
                error_code="unauthorized",
                status_code=401
            )
        
        # Parse query parameters
        status = request.args.get('status')
        if status and status not in [OrderStatus.CLAIMED, OrderStatus.IN_TRANSIT, 
                                      OrderStatus.DELIVERED]:
            status = None
        
        try:
            limit = min(int(request.args.get('limit', 50)), 100)
            skip = max(int(request.args.get('skip', 0)), 0)
        except ValueError:
            limit, skip = 50, 0
        
        # Get MongoDB from app context
        mongo = current_app.extensions.get('pymongo')
        if not mongo:
            return error_response(
                message="Database tidak tersedia",
                error_code="database_error",
                status_code=500
            )
        
        order_model = Order(mongo.db)
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
        
    except Exception as e:
        current_app.logger.error(f"Get my deliveries error: {str(e)}")
        return error_response(
            message="Terjadi kesalahan saat mengambil daftar pengiriman",
            error_code="server_error",
            status_code=500
        )


@orders_bp.route('/orders/categories', methods=['GET'])
def get_categories():
    """
    Get list of available item categories
    
    Returns:
        200: List of categories
    """
    categories = [
        {'code': 'FOOD', 'name': 'Makanan', 'icon': '🍔'},
        {'code': 'DOCUMENT', 'name': 'Dokumen', 'icon': '📄'},
        {'code': 'ELECTRONICS', 'name': 'Elektronik', 'icon': '📱'},
        {'code': 'FASHION', 'name': 'Fashion', 'icon': '👕'},
        {'code': 'GROCERY', 'name': 'Groceries', 'icon': '🛒'},
        {'code': 'MEDICINE', 'name': 'Obat', 'icon': '💊'},
        {'code': 'OTHER', 'name': 'Lainnya', 'icon': '📦'}
    ]
    
    return success_response(
        data={'categories': categories},
        message="Daftar kategori barang"
    )
