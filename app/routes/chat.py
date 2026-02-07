"""
TrustPoints Chat Routes
Handles chat messaging between sender and hunter
"""
from flask import Blueprint, request, current_app
from app.models.chat import Chat
from app.models.order import Order
from app.utils.auth import token_required, get_current_user_id
from app.utils.responses import success_response, error_response, validation_error

chat_bp = Blueprint('chat', __name__)


@chat_bp.route('/chat/<order_id>/messages', methods=['GET'])
@token_required
def get_messages(order_id):
    """
    Get all messages for an order
    
    Headers:
        Authorization: Bearer <token>
    
    Query Params:
        limit: Maximum messages to return (default: 100)
        skip: Messages to skip for pagination (default: 0)
    
    Returns:
        200: List of messages
        401: Unauthorized
        403: Not authorized to view this chat
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
        
        # Get MongoDB
        mongo = current_app.extensions.get('pymongo')
        if not mongo:
            return error_response(
                message="Database tidak tersedia",
                error_code="database_error",
                status_code=500
            )
        
        # Check if order exists and user is participant
        order_model = Order(mongo.db)
        order = order_model.find_by_object_id(order_id)
        
        if not order:
            return error_response(
                message="Pesanan tidak ditemukan",
                error_code="order_not_found",
                status_code=404
            )
        
        # Check if user is sender or hunter
        if order['sender_id'] != user_id and order.get('hunter_id') != user_id:
            return error_response(
                message="Anda tidak memiliki akses ke chat ini",
                error_code="forbidden",
                status_code=403
            )
        
        # Get query params
        limit = request.args.get('limit', 100, type=int)
        skip = request.args.get('skip', 0, type=int)
        
        # Get messages
        chat_model = Chat(mongo.db)
        messages = chat_model.get_messages(order_id, limit=limit, skip=skip)
        
        # Mark messages as read
        chat_model.mark_as_read(order_id, user_id)
        
        return success_response(
            data={
                'messages': messages,
                'count': len(messages),
                'order_id': order_id
            },
            message="Pesan berhasil diambil"
        )
        
    except Exception as e:
        current_app.logger.error(f"Get messages error: {str(e)}")
        return error_response(
            message="Terjadi kesalahan saat mengambil pesan",
            error_code="server_error",
            status_code=500
        )


@chat_bp.route('/chat/<order_id>/send', methods=['POST'])
@token_required
def send_message(order_id):
    """
    Send a chat message
    
    Headers:
        Authorization: Bearer <token>
    
    Request Body:
        {
            "message": "string"
        }
    
    Returns:
        201: Message sent successfully
        400: Invalid data
        401: Unauthorized
        403: Not authorized to send to this chat
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
        
        data = request.get_json()
        if not data or not data.get('message'):
            return error_response(
                message="Pesan tidak boleh kosong",
                error_code="missing_message",
                status_code=400
            )
        
        message_text = data['message'].strip()
        if len(message_text) > 1000:
            return error_response(
                message="Pesan terlalu panjang (maksimal 1000 karakter)",
                error_code="message_too_long",
                status_code=400
            )
        
        # Get MongoDB
        mongo = current_app.extensions.get('pymongo')
        if not mongo:
            return error_response(
                message="Database tidak tersedia",
                error_code="database_error",
                status_code=500
            )
        
        # Check if order exists and user is participant
        order_model = Order(mongo.db)
        order = order_model.find_by_object_id(order_id)
        
        if not order:
            return error_response(
                message="Pesanan tidak ditemukan",
                error_code="order_not_found",
                status_code=404
            )
        
        # Check if user is sender or hunter
        is_sender = order['sender_id'] == user_id
        is_hunter = order.get('hunter_id') == user_id
        
        if not is_sender and not is_hunter:
            return error_response(
                message="Anda tidak memiliki akses ke chat ini",
                error_code="forbidden",
                status_code=403
            )
        
        # Check order status - only allow chat for active orders
        from app.models.order import OrderStatus
        if order['status'] in [OrderStatus.DELIVERED, OrderStatus.CANCELLED]:
            return error_response(
                message="Tidak dapat mengirim pesan untuk pesanan yang sudah selesai atau dibatalkan",
                error_code="order_closed",
                status_code=400
            )
        
        # Get sender name from user
        from app.models.user import User
        user_model = User(mongo.db)
        user = user_model.find_by_id(user_id)
        sender_name = user.get('full_name', 'Unknown') if user else 'Unknown'
        
        # Send message
        chat_model = Chat(mongo.db)
        message = chat_model.send_message(
            order_id=order_id,
            sender_id=user_id,
            sender_name=sender_name,
            message=message_text,
            message_type='text'
        )
        
        return success_response(
            data={'message': message},
            message="Pesan berhasil dikirim",
            status_code=201
        )
        
    except Exception as e:
        current_app.logger.error(f"Send message error: {str(e)}")
        return error_response(
            message="Terjadi kesalahan saat mengirim pesan",
            error_code="server_error",
            status_code=500
        )


@chat_bp.route('/chat/<order_id>/unread', methods=['GET'])
@token_required
def get_unread_count(order_id):
    """
    Get unread message count for an order
    
    Headers:
        Authorization: Bearer <token>
    
    Returns:
        200: Unread count
        401: Unauthorized
        403: Not authorized
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
        
        # Get MongoDB
        mongo = current_app.extensions.get('pymongo')
        if not mongo:
            return error_response(
                message="Database tidak tersedia",
                error_code="database_error",
                status_code=500
            )
        
        # Check if order exists and user is participant
        order_model = Order(mongo.db)
        order = order_model.find_by_object_id(order_id)
        
        if not order:
            return error_response(
                message="Pesanan tidak ditemukan",
                error_code="order_not_found",
                status_code=404
            )
        
        # Check if user is sender or hunter
        if order['sender_id'] != user_id and order.get('hunter_id') != user_id:
            return error_response(
                message="Anda tidak memiliki akses ke chat ini",
                error_code="forbidden",
                status_code=403
            )
        
        # Get unread count
        chat_model = Chat(mongo.db)
        unread_count = chat_model.get_unread_count(order_id, user_id)
        
        return success_response(
            data={
                'unread_count': unread_count,
                'order_id': order_id
            },
            message="Jumlah pesan belum dibaca"
        )
        
    except Exception as e:
        current_app.logger.error(f"Get unread count error: {str(e)}")
        return error_response(
            message="Terjadi kesalahan",
            error_code="server_error",
            status_code=500
        )


@chat_bp.route('/chat/<order_id>/read', methods=['PUT'])
@token_required
def mark_messages_read(order_id):
    """
    Mark all messages as read
    
    Headers:
        Authorization: Bearer <token>
    
    Returns:
        200: Messages marked as read
        401: Unauthorized
        403: Not authorized
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
        
        # Get MongoDB
        mongo = current_app.extensions.get('pymongo')
        if not mongo:
            return error_response(
                message="Database tidak tersedia",
                error_code="database_error",
                status_code=500
            )
        
        # Check if order exists and user is participant
        order_model = Order(mongo.db)
        order = order_model.find_by_object_id(order_id)
        
        if not order:
            return error_response(
                message="Pesanan tidak ditemukan",
                error_code="order_not_found",
                status_code=404
            )
        
        # Check if user is sender or hunter
        if order['sender_id'] != user_id and order.get('hunter_id') != user_id:
            return error_response(
                message="Anda tidak memiliki akses ke chat ini",
                error_code="forbidden",
                status_code=403
            )
        
        # Mark as read
        chat_model = Chat(mongo.db)
        marked_count = chat_model.mark_as_read(order_id, user_id)
        
        return success_response(
            data={
                'marked_count': marked_count,
                'order_id': order_id
            },
            message="Pesan ditandai sudah dibaca"
        )
        
    except Exception as e:
        current_app.logger.error(f"Mark read error: {str(e)}")
        return error_response(
            message="Terjadi kesalahan",
            error_code="server_error",
            status_code=500
        )
