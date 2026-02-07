from flask import current_app, request as flask_request
from flask_socketio import emit, join_room, leave_room, disconnect
from app.models.chat import Chat
from app.models.order import Order
from app.models.user import User
from app.utils.auth import decode_token
import jwt


def register_socket_events(socketio):
    # Store connected users: {user_id: sid}
    connected_users = {}
    
    @socketio.on('connect')
    def handle_connect(auth=None):
        """Handle client connection with JWT authentication"""
        try:
            # Get token from auth data or query params
            token = None
            
            # Try auth object first
            if auth and isinstance(auth, dict):
                token = auth.get('token')
            
            # Fallback to query params
            if not token:
                token = flask_request.args.get('token')
            
            current_app.logger.info(f"WebSocket connect attempt, token present: {token is not None}")
            
            if not token:
                current_app.logger.warning("WebSocket: No token provided")
                emit('error', {'message': 'Token tidak ditemukan'})
                return True  # Allow connection but mark as unauthenticated
            
            # Verify token
            try:
                payload = jwt.decode(
                    token,
                    current_app.config['JWT_SECRET_KEY'],
                    algorithms=['HS256']
                )
                user_id = payload.get('user_id')
                
                if not user_id:
                    current_app.logger.warning("WebSocket: Token has no user_id")
                    emit('error', {'message': 'Token tidak valid'})
                    return True
                
                # Store connection with user_id in session
                sid = flask_request.sid
                connected_users[user_id] = sid
                
                # Store user_id in socket session for later use
                from flask_socketio import rooms
                
                emit('connected', {
                    'message': 'Terhubung ke server',
                    'user_id': user_id
                })
                
                current_app.logger.info(f"User {user_id} connected via WebSocket (sid: {sid})")
                return True
                
            except jwt.ExpiredSignatureError:
                current_app.logger.warning("WebSocket: Token expired")
                emit('error', {'message': 'Token sudah kadaluarsa'})
                return True
            except jwt.InvalidTokenError as e:
                current_app.logger.warning(f"WebSocket: Invalid token - {str(e)}")
                emit('error', {'message': 'Token tidak valid'})
                return True
                
        except Exception as e:
            current_app.logger.error(f"WebSocket connect error: {str(e)}")
            emit('error', {'message': 'Gagal terhubung'})
            return True
    
    @socketio.on('disconnect')
    def handle_disconnect():
        try:
            # Remove from connected users
            for user_id, sid in list(connected_users.items()):
                if sid == flask_request.sid:
                    del connected_users[user_id]
                    current_app.logger.info(f"User {user_id} disconnected from WebSocket")
                    break
        except Exception as e:
            current_app.logger.error(f"WebSocket disconnect error: {str(e)}")
    
    @socketio.on('join_chat')
    def handle_join_chat(data):
        try:
            order_id = data.get('order_id')
            if not order_id:
                emit('error', {'message': 'Order ID diperlukan'})
                return
            
            # Get user_id from connected users
            user_id = None
            for uid, sid in connected_users.items():
                if sid == flask_request.sid:
                    user_id = uid
                    break
            
            if not user_id:
                # Try to get from token in query
                token = flask_request.args.get('token')
                if token:
                    try:
                        payload = jwt.decode(
                            token,
                            current_app.config['JWT_SECRET_KEY'],
                            algorithms=['HS256']
                        )
                        user_id = payload.get('user_id')
                        if user_id:
                            connected_users[user_id] = flask_request.sid
                    except:
                        pass
            
            if not user_id:
                emit('error', {'message': 'User tidak terautentikasi'})
                return
            
            # Verify user is participant of this order
            mongo = current_app.extensions.get('pymongo')
            if not mongo:
                emit('error', {'message': 'Database tidak tersedia'})
                return
            
            order_model = Order(mongo.db)
            order = order_model.find_by_object_id(order_id)
            
            if not order:
                emit('error', {'message': 'Pesanan tidak ditemukan'})
                return
            
            # Check if user is sender or hunter
            if order['sender_id'] != user_id and order.get('hunter_id') != user_id:
                emit('error', {'message': 'Anda tidak memiliki akses ke chat ini'})
                return
            
            # Join the room
            room = f"chat_{order_id}"
            join_room(room)
            
            emit('joined_chat', {
                'order_id': order_id,
                'room': room,
                'message': 'Berhasil bergabung ke chat'
            })
            
            current_app.logger.info(f"User {user_id} joined chat room {room}")
            
        except Exception as e:
            current_app.logger.error(f"Join chat error: {str(e)}")
            emit('error', {'message': 'Gagal bergabung ke chat'})
    
    @socketio.on('leave_chat')
    def handle_leave_chat(data):
        try:
            order_id = data.get('order_id')
            if not order_id:
                return
            
            room = f"chat_{order_id}"
            leave_room(room)
            
            emit('left_chat', {
                'order_id': order_id,
                'message': 'Keluar dari chat'
            })
            
        except Exception as e:
            current_app.logger.error(f"Leave chat error: {str(e)}")
    
    @socketio.on('send_message')
    def handle_send_message(data):
        try:
            order_id = data.get('order_id')
            message_text = data.get('message', '').strip()
            
            if not order_id:
                emit('error', {'message': 'Order ID diperlukan'})
                return
            
            if not message_text:
                emit('error', {'message': 'Pesan tidak boleh kosong'})
                return
            
            if len(message_text) > 1000:
                emit('error', {'message': 'Pesan terlalu panjang (maksimal 1000 karakter)'})
                return
            
            # Get user_id from connected users
            user_id = None
            for uid, sid in connected_users.items():
                if sid == flask_request.sid:
                    user_id = uid
                    break
            
            if not user_id:
                emit('error', {'message': 'User tidak terautentikasi'})
                return
            
            # Get MongoDB
            mongo = current_app.extensions.get('pymongo')
            if not mongo:
                emit('error', {'message': 'Database tidak tersedia'})
                return
            
            # Verify user is participant
            order_model = Order(mongo.db)
            order = order_model.find_by_object_id(order_id)
            
            if not order:
                emit('error', {'message': 'Pesanan tidak ditemukan'})
                return
            
            # Check if user is sender or hunter
            is_sender = order['sender_id'] == user_id
            is_hunter = order.get('hunter_id') == user_id
            
            if not is_sender and not is_hunter:
                emit('error', {'message': 'Anda tidak memiliki akses ke chat ini'})
                return
            
            # Check order status
            from app.models.order import OrderStatus
            if order['status'] in [OrderStatus.DELIVERED, OrderStatus.CANCELLED]:
                emit('error', {'message': 'Tidak dapat mengirim pesan untuk pesanan yang sudah selesai atau dibatalkan'})
                return
            
            # Get sender name
            user_model = User(mongo.db)
            user = user_model.find_by_id(user_id)
            sender_name = user.get('full_name', 'Unknown') if user else 'Unknown'
            
            # Save message to database
            chat_model = Chat(mongo.db)
            message = chat_model.send_message(
                order_id=order_id,
                sender_id=user_id,
                sender_name=sender_name,
                message=message_text,
                message_type='text'
            )
            
            # Broadcast to room
            room = f"chat_{order_id}"
            emit('new_message', {
                'order_id': order_id,
                'message': message
            }, room=room)
            
            current_app.logger.info(f"Message sent in room {room} by user {user_id}")
            
        except Exception as e:
            current_app.logger.error(f"Send message error: {str(e)}")
            emit('error', {'message': 'Gagal mengirim pesan'})
    
    @socketio.on('typing')
    def handle_typing(data):
        try:
            order_id = data.get('order_id')
            is_typing = data.get('is_typing', False)
            
            if not order_id:
                return
            
            # Get user_id
            user_id = None
            for uid, sid in connected_users.items():
                if sid == flask_request.sid:
                    user_id = uid
                    break
            
            if not user_id:
                return
            
            room = f"chat_{order_id}"
            emit('user_typing', {
                'order_id': order_id,
                'user_id': user_id,
                'is_typing': is_typing
            }, room=room, include_self=False)
            
        except Exception as e:
            current_app.logger.error(f"Typing indicator error: {str(e)}")
    
    @socketio.on('mark_read')
    def handle_mark_read(data):
        try:
            order_id = data.get('order_id')
            if not order_id:
                return
            
            # Get user_id
            user_id = None
            for uid, sid in connected_users.items():
                if sid == flask_request.sid:
                    user_id = uid
                    break
            
            if not user_id:
                return
            
            # Mark as read in database
            mongo = current_app.extensions.get('pymongo')
            if mongo:
                chat_model = Chat(mongo.db)
                chat_model.mark_as_read(order_id, user_id)
                
                # Notify other user in room
                room = f"chat_{order_id}"
                emit('messages_read', {
                    'order_id': order_id,
                    'reader_id': user_id
                }, room=room, include_self=False)
                
        except Exception as e:
            current_app.logger.error(f"Mark read error: {str(e)}")
    
    return socketio
