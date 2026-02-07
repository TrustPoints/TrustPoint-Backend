from flask import Blueprint, request, current_app
from app.models.activity import Activity
from app.utils.auth import token_required, get_current_user_id
from app.utils.responses import success_response, error_response

activity_bp = Blueprint('activity', __name__)


@activity_bp.route('/recent', methods=['GET'])
@token_required
def get_recent_activities():
    """Get recent activities for current user (for dashboard)"""
    user_id = get_current_user_id()
    
    # Get limit from query params, default to 5
    limit = request.args.get('limit', 5, type=int)
    limit = min(max(limit, 1), 20)  # Clamp between 1 and 20
    
    mongo = current_app.extensions.get('pymongo')
    if not mongo:
        return error_response(
            message="Database tidak tersedia",
            error_code="database_error",
            status_code=500
        )
    
    activity_model = Activity(mongo.db)
    activities = activity_model.get_recent_activities(user_id, limit=limit)
    
    return success_response(
        data={'activities': activities},
        message="Berhasil mendapatkan aktivitas terbaru"
    )


@activity_bp.route('/', methods=['GET'])
@token_required
def get_all_activities():
    """Get all activities for current user with pagination"""
    user_id = get_current_user_id()
    
    # Get pagination params
    page = request.args.get('page', 1, type=int)
    limit = request.args.get('limit', 10, type=int)
    limit = min(max(limit, 1), 50)  # Clamp between 1 and 50
    skip = (page - 1) * limit
    
    mongo = current_app.extensions.get('pymongo')
    if not mongo:
        return error_response(
            message="Database tidak tersedia",
            error_code="database_error",
            status_code=500
        )
    
    activity_model = Activity(mongo.db)
    activities = activity_model.get_user_activities(user_id, limit=limit, skip=skip)
    total = activity_model.count_user_activities(user_id)
    
    return success_response(
        data={
            'activities': activities,
            'pagination': {
                'page': page,
                'limit': limit,
                'total': total,
                'total_pages': (total + limit - 1) // limit
            }
        },
        message="Berhasil mendapatkan semua aktivitas"
    )
