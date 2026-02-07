import logging
from flask import Blueprint, request, current_app

from app.models.activity import Activity
from app.utils.auth import token_required, get_current_user_id
from app.utils.responses import success_response, database_error, server_error
from app.utils.helpers import clamp

logger = logging.getLogger(__name__)

activity_bp = Blueprint('activity', __name__)


# =============================================================================
# Helper Functions
# =============================================================================

def _get_db():
    mongo = current_app.extensions.get('pymongo')
    return mongo.db if mongo else None


def _build_pagination_response(page: int, limit: int, total: int) -> dict:
    return {
        'page': page,
        'limit': limit,
        'total': total,
        'total_pages': (total + limit - 1) // limit
    }


# =============================================================================
# Activity Endpoints
# =============================================================================

@activity_bp.route('/recent', methods=['GET'])
@token_required
def get_recent_activities():
    user_id = get_current_user_id()
    limit = clamp(request.args.get('limit', 5, type=int), min_val=1, max_val=20)
    
    db = _get_db()
    if db is None:
        return database_error()
    
    try:
        activity_model = Activity(db)
        activities = activity_model.get_recent_activities(user_id, limit=limit)
        
        return success_response(
            data={'activities': activities},
            message="Berhasil mendapatkan aktivitas terbaru"
        )
    except Exception:
        logger.exception("Error getting recent activities")
        return server_error("Terjadi kesalahan saat mengambil aktivitas")


@activity_bp.route('/', methods=['GET'])
@token_required
def get_all_activities():
    user_id = get_current_user_id()
    
    page = max(1, request.args.get('page', 1, type=int))
    limit = clamp(request.args.get('limit', 10, type=int), min_val=1, max_val=50)
    skip = (page - 1) * limit
    
    db = _get_db()
    if db is None:
        return database_error()
    
    try:
        activity_model = Activity(db)
        activities = activity_model.get_user_activities(user_id, limit=limit, skip=skip)
        total = activity_model.count_user_activities(user_id)
        
        return success_response(
            data={
                'activities': activities,
                'pagination': _build_pagination_response(page, limit, total)
            },
            message="Berhasil mendapatkan semua aktivitas"
        )
    except Exception:
        logger.exception("Error getting all activities")
        return server_error("Terjadi kesalahan saat mengambil aktivitas")
