from flask import Blueprint, request, jsonify, current_app
from bson import ObjectId
from datetime import datetime, timedelta
from functools import wraps
import logging

from app.utils.auth import token_required
from app.utils.responses import success_response, error_response
from app.utils.helpers import get_pagination_params

# ==================== SETUP ====================

admin_bp = Blueprint('admin', __name__)
logger = logging.getLogger(__name__)

# ==================== DECORATORS ====================

def admin_required(f):
    @wraps(f)
    def decorated(current_user, *args, **kwargs):
        if not current_user.get('is_admin', False):
            return error_response('Admin access required', 403)
        return f(current_user, *args, **kwargs)
    return decorated


def get_db():
    db = current_app.config.get('db')
    if db is None:
        return None
    return db


# ==================== DASHBOARD ====================

@admin_bp.route('/stats', methods=['GET'])
@token_required
@admin_required
def get_stats(current_user):
    try:
        db = get_db()
        if db is None:
            return error_response('Database not available', 500)
        
        # Calculate dates
        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        week_ago = today - timedelta(days=7)
        
        # Get counts
        total_users = db.users.count_documents({})
        new_users_this_week = db.users.count_documents({
            'created_at': {'$gte': week_ago}
        })
        
        total_orders = db.orders.count_documents({})
        pending_orders = db.orders.count_documents({'status': 'pending'})
        
        # Total points in system
        pipeline = [
            {'$group': {'_id': None, 'total': {'$sum': '$balance'}}}
        ]
        points_result = list(db.users.aggregate(pipeline))
        total_points = points_result[0]['total'] if points_result else 0
        
        # Transactions today
        transactions_today = db.transactions.count_documents({
            'created_at': {'$gte': today}
        }) if 'transactions' in db.list_collection_names() else 0
        
        return success_response({
            'total_users': total_users,
            'new_users_this_week': new_users_this_week,
            'total_orders': total_orders,
            'pending_orders': pending_orders,
            'total_points': total_points,
            'transactions_today': transactions_today,
        })
        
    except Exception as e:
        logger.exception('Failed to get stats')
        return error_response(f'Failed to get stats: {str(e)}', 500)


# ==================== USERS ====================

@admin_bp.route('/users', methods=['GET'])
@token_required
@admin_required
def get_users(current_user):
    """Get paginated list of users with optional search."""
    try:
        db = get_db()
        if db is None:
            return error_response('Database not available', 500)
        
        page, limit, skip = get_pagination_params(request)
        search = request.args.get('search', '').strip()
        
        # Build query
        query = {}
        if search:
            query['$or'] = [
                {'name': {'$regex': search, '$options': 'i'}},
                {'email': {'$regex': search, '$options': 'i'}},
                {'phone': {'$regex': search, '$options': 'i'}},
            ]
        
        # Get total count
        total = db.users.count_documents(query)
        
        # Get users
        users = list(db.users.find(query)
                    .sort('created_at', -1)
                    .skip(skip)
                    .limit(limit))
        
        # Format users
        for user in users:
            user['_id'] = str(user['_id'])
            user.pop('password', None)  # Remove password
            if 'created_at' in user:
                user['created_at'] = user['created_at'].isoformat()
        
        return success_response({
            'users': users,
            'page': page,
            'limit': limit,
            'total': total,
            'pages': (total + limit - 1) // limit,
        })
        
    except Exception as e:
        logger.exception('Failed to get users')
        return error_response(f'Failed to get users: {str(e)}', 500)


@admin_bp.route('/users/<user_id>', methods=['GET'])
@token_required
@admin_required
def get_user(current_user, user_id):
    """Get single user details."""
    try:
        db = get_db()
        if db is None:
            return error_response('Database not available', 500)
        
        user = db.users.find_one({'_id': ObjectId(user_id)})
        if not user:
            return error_response('User not found', 404)
        
        user['_id'] = str(user['_id'])
        user.pop('password', None)
        
        # Get order count
        user['total_orders'] = db.orders.count_documents({'requester_id': user_id})
        
        if 'created_at' in user:
            user['created_at'] = user['created_at'].isoformat()
        
        return success_response(user)
        
    except Exception as e:
        logger.exception('Failed to get user')
        return error_response(f'Failed to get user: {str(e)}', 500)


@admin_bp.route('/users', methods=['POST'])
@token_required
@admin_required
def create_user(current_user):
    try:
        db = get_db()
        if db is None:
            return error_response('Database not available', 500)
        
        data = request.get_json()
        
        # Validate required fields
        required = ['name', 'email', 'password']
        for field in required:
            if not data.get(field):
                return error_response(f'{field} is required', 400)
        
        # Check if email exists
        if db.users.find_one({'email': data['email']}):
            return error_response('Email already exists', 400)
        
        # Hash password
        from werkzeug.security import generate_password_hash
        
        user = {
            'name': data['name'],
            'email': data['email'],
            'phone': data.get('phone', ''),
            'password': generate_password_hash(data['password']),
            'balance': 0,
            'rating': 0.0,
            'rating_count': 0,
            'is_admin': data.get('is_admin', False),
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow(),
        }
        
        result = db.users.insert_one(user)
        user['_id'] = str(result.inserted_id)
        user.pop('password', None)
        
        return success_response(user, 'User created successfully', 201)
        
    except Exception as e:
        logger.exception('Failed to create user')
        return error_response(f'Failed to create user: {str(e)}', 500)


@admin_bp.route('/users/<user_id>', methods=['PUT'])
@token_required
@admin_required
def update_user(current_user, user_id):
    """Update a user."""
    try:
        db = get_db()
        if db is None:
            return error_response('Database not available', 500)
        
        data = request.get_json()
        
        # Check if user exists
        user = db.users.find_one({'_id': ObjectId(user_id)})
        if not user:
            return error_response('User not found', 404)
        
        # Build update
        update = {'updated_at': datetime.utcnow()}
        
        allowed_fields = ['name', 'email', 'phone', 'is_admin']
        for field in allowed_fields:
            if field in data:
                update[field] = data[field]
        
        # Check email uniqueness if changed
        if 'email' in update and update['email'] != user['email']:
            if db.users.find_one({'email': update['email']}):
                return error_response('Email already exists', 400)
        
        # Update password if provided
        if data.get('password'):
            from werkzeug.security import generate_password_hash
            update['password'] = generate_password_hash(data['password'])
        
        db.users.update_one(
            {'_id': ObjectId(user_id)},
            {'$set': update}
        )
        
        return success_response(None, 'User updated successfully')
        
    except Exception as e:
        logger.exception('Failed to update user')
        return error_response(f'Failed to update user: {str(e)}', 500)


@admin_bp.route('/users/<user_id>', methods=['DELETE'])
@token_required
@admin_required
def delete_user(current_user, user_id):
    """Delete a user."""
    try:
        db = get_db()
        if db is None:
            return error_response('Database not available', 500)
        
        # Check if user exists
        user = db.users.find_one({'_id': ObjectId(user_id)})
        if not user:
            return error_response('User not found', 404)
        
        # Prevent deleting self
        if str(user['_id']) == current_user.get('user_id'):
            return error_response('Cannot delete yourself', 400)
        
        db.users.delete_one({'_id': ObjectId(user_id)})
        
        return success_response(None, 'User deleted successfully')
        
    except Exception as e:
        logger.exception('Failed to delete user')
        return error_response(f'Failed to delete user: {str(e)}', 500)


@admin_bp.route('/users/<user_id>/balance', methods=['POST'])
@token_required
@admin_required
def adjust_balance(current_user, user_id):
    """Adjust user balance (add or deduct points)."""
    try:
        db = get_db()
        if db is None:
            return error_response('Database not available', 500)
        
        data = request.get_json()
        
        amount = data.get('amount', 0)
        balance_type = data.get('type', 'add')  # 'add' or 'deduct'
        note = data.get('note', 'Admin adjustment')
        
        if amount <= 0:
            return error_response('Amount must be positive', 400)
        
        # Get user
        user = db.users.find_one({'_id': ObjectId(user_id)})
        if not user:
            return error_response('User not found', 404)
        
        # Calculate new balance
        current_balance = user.get('balance', 0)
        if balance_type == 'deduct':
            if current_balance < amount:
                return error_response('Insufficient balance', 400)
            new_balance = current_balance - amount
        else:
            new_balance = current_balance + amount
        
        # Update balance
        db.users.update_one(
            {'_id': ObjectId(user_id)},
            {
                '$set': {
                    'balance': new_balance,
                    'updated_at': datetime.utcnow()
                }
            }
        )
        
        # Record transaction
        transaction = {
            'user_id': user_id,
            'user_name': user.get('name', 'Unknown'),
            'type': 'credit' if balance_type == 'add' else 'debit',
            'amount': amount,
            'balance_before': current_balance,
            'balance_after': new_balance,
            'note': note,
            'admin_id': current_user.get('user_id'),
            'created_at': datetime.utcnow(),
        }
        db.transactions.insert_one(transaction)
        
        return success_response({
            'balance': new_balance,
            'previous_balance': current_balance,
        }, 'Balance updated successfully')
        
    except Exception as e:
        logger.exception('Failed to adjust balance')
        return error_response(f'Failed to adjust balance: {str(e)}', 500)


# ==================== ORDERS ====================

@admin_bp.route('/orders', methods=['GET'])
@token_required
@admin_required
def get_orders(current_user):
    """Get paginated list of orders with optional status filter."""
    try:
        db = get_db()
        if db is None:
            return error_response('Database not available', 500)
        
        page, limit, skip = get_pagination_params(request)
        status = request.args.get('status', '').strip()
        
        # Build query
        query = {}
        if status:
            query['status'] = status
        
        # Get total count
        total = db.orders.count_documents(query)
        
        # Get orders with user info
        pipeline = [
            {'$match': query},
            {'$sort': {'created_at': -1}},
            {'$skip': skip},
            {'$limit': limit},
            {
                '$lookup': {
                    'from': 'users',
                    'let': {'requester_id': {'$toObjectId': '$requester_id'}},
                    'pipeline': [
                        {'$match': {'$expr': {'$eq': ['$_id', '$$requester_id']}}},
                        {'$project': {'name': 1}}
                    ],
                    'as': 'requester'
                }
            },
            {
                '$lookup': {
                    'from': 'users',
                    'let': {'shopper_id': {'$toObjectId': {'$ifNull': ['$shopper_id', '000000000000000000000000']}}},
                    'pipeline': [
                        {'$match': {'$expr': {'$eq': ['$_id', '$$shopper_id']}}},
                        {'$project': {'name': 1}}
                    ],
                    'as': 'shopper'
                }
            },
            {
                '$addFields': {
                    'requester_name': {'$arrayElemAt': ['$requester.name', 0]},
                    'shopper_name': {'$arrayElemAt': ['$shopper.name', 0]}
                }
            },
            {
                '$project': {
                    'requester': 0,
                    'shopper': 0
                }
            }
        ]
        
        orders = list(db.orders.aggregate(pipeline))
        
        # Format orders
        for order in orders:
            order['_id'] = str(order['_id'])
            if 'created_at' in order:
                order['created_at'] = order['created_at'].isoformat()
            if 'updated_at' in order:
                order['updated_at'] = order['updated_at'].isoformat()
        
        return success_response({
            'orders': orders,
            'page': page,
            'limit': limit,
            'total': total,
            'pages': (total + limit - 1) // limit,
        })
        
    except Exception as e:
        logger.exception('Failed to get orders')
        return error_response(f'Failed to get orders: {str(e)}', 500)


@admin_bp.route('/orders/<order_id>', methods=['GET'])
@token_required
@admin_required
def get_order(current_user, order_id):
    """Get single order details."""
    try:
        db = get_db()
        if db is None:
            return error_response('Database not available', 500)
        
        order = db.orders.find_one({'_id': ObjectId(order_id)})
        if not order:
            return error_response('Order not found', 404)
        
        order['_id'] = str(order['_id'])
        
        # Get user info
        if order.get('requester_id'):
            requester = db.users.find_one({'_id': ObjectId(order['requester_id'])})
            order['requester_name'] = requester.get('name') if requester else None
        
        if order.get('shopper_id'):
            shopper = db.users.find_one({'_id': ObjectId(order['shopper_id'])})
            order['shopper_name'] = shopper.get('name') if shopper else None
        
        if 'created_at' in order:
            order['created_at'] = order['created_at'].isoformat()
        if 'updated_at' in order:
            order['updated_at'] = order['updated_at'].isoformat()
        
        return success_response(order)
        
    except Exception as e:
        logger.exception('Failed to get order')
        return error_response(f'Failed to get order: {str(e)}', 500)


@admin_bp.route('/orders/<order_id>/status', methods=['PUT'])
@token_required
@admin_required
def update_order_status(current_user, order_id):
    """Update order status."""
    try:
        db = get_db()
        if db is None:
            return error_response('Database not available', 500)
        
        data = request.get_json()
        status = data.get('status')
        
        valid_statuses = ['pending', 'accepted', 'in_progress', 'completed', 'cancelled']
        if status not in valid_statuses:
            return error_response(f'Invalid status. Must be one of: {valid_statuses}', 400)
        
        # Check if order exists
        order = db.orders.find_one({'_id': ObjectId(order_id)})
        if not order:
            return error_response('Order not found', 404)
        
        # Update status
        db.orders.update_one(
            {'_id': ObjectId(order_id)},
            {
                '$set': {
                    'status': status,
                    'updated_at': datetime.utcnow()
                }
            }
        )
        
        return success_response(None, 'Order status updated successfully')
        
    except Exception as e:
        logger.exception('Failed to update order status')
        return error_response(f'Failed to update order status: {str(e)}', 500)


# ==================== TRANSACTIONS ====================

@admin_bp.route('/transactions', methods=['GET'])
@token_required
@admin_required
def get_transactions(current_user):
    """Get paginated list of transactions."""
    try:
        db = get_db()
        if db is None:
            return error_response('Database not available', 500)
        
        page, limit, skip = get_pagination_params(request)
        user_id = request.args.get('user_id', '').strip()
        
        # Build query
        query = {}
        if user_id:
            query['user_id'] = user_id
        
        # Get total count
        total = db.transactions.count_documents(query) if 'transactions' in db.list_collection_names() else 0
        
        # Get transactions
        transactions = []
        if 'transactions' in db.list_collection_names():
            transactions = list(db.transactions.find(query)
                              .sort('created_at', -1)
                              .skip(skip)
                              .limit(limit))
        
        # Format transactions
        for tx in transactions:
            tx['_id'] = str(tx['_id'])
            if 'created_at' in tx:
                tx['created_at'] = tx['created_at'].isoformat()
        
        return success_response({
            'transactions': transactions,
            'page': page,
            'limit': limit,
            'total': total,
            'pages': (total + limit - 1) // limit if total > 0 else 0,
        })
        
    except Exception as e:
        logger.exception('Failed to get transactions')
        return error_response(f'Failed to get transactions: {str(e)}', 500)


# ==================== ACTIVITIES ====================

@admin_bp.route('/activities', methods=['GET'])
@token_required
@admin_required
def get_activities(current_user):
    """Get paginated list of activities."""
    try:
        db = get_db()
        if db is None:
            return error_response('Database not available', 500)
        
        page, limit, skip = get_pagination_params(request)
        activity_type = request.args.get('type', '').strip()
        
        # Build query
        query = {}
        if activity_type:
            query['type'] = activity_type
        
        # Get total count
        total = db.activities.count_documents(query) if 'activities' in db.list_collection_names() else 0
        
        # Get activities with user info
        activities = []
        if 'activities' in db.list_collection_names():
            pipeline = [
                {'$match': query},
                {'$sort': {'created_at': -1}},
                {'$skip': skip},
                {'$limit': limit},
                {
                    '$lookup': {
                        'from': 'users',
                        'let': {'user_id': {'$toObjectId': {'$ifNull': ['$user_id', '000000000000000000000000']}}},
                        'pipeline': [
                            {'$match': {'$expr': {'$eq': ['$_id', '$$user_id']}}},
                            {'$project': {'name': 1}}
                        ],
                        'as': 'user'
                    }
                },
                {
                    '$addFields': {
                        'user_name': {'$arrayElemAt': ['$user.name', 0]}
                    }
                },
                {
                    '$project': {
                        'user': 0
                    }
                }
            ]
            activities = list(db.activities.aggregate(pipeline))
        
        # Format activities
        for activity in activities:
            activity['_id'] = str(activity['_id'])
            if 'created_at' in activity:
                activity['created_at'] = activity['created_at'].isoformat()
        
        return success_response({
            'activities': activities,
            'page': page,
            'limit': limit,
            'total': total,
            'pages': (total + limit - 1) // limit if total > 0 else 0,
        })
        
    except Exception as e:
        logger.exception('Failed to get activities')
        return error_response(f'Failed to get activities: {str(e)}', 500)
