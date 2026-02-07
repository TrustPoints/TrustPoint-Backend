from functools import wraps
from typing import Any, Callable, Optional, Tuple, Type

from flask import current_app, request

from app.utils.responses import error_response


def get_mongo():
    mongo = current_app.extensions.get('pymongo')
    if not mongo:
        return None
    return mongo


def get_db():
    mongo = get_mongo()
    return mongo.db if mongo else None


def require_json(f: Callable) -> Callable:
    @wraps(f)
    def decorated(*args, **kwargs):
        data = request.get_json()
        if not data:
            return error_response(
                message="Data tidak ditemukan",
                error_code="missing_data",
                status_code=400
            )
        return f(*args, **kwargs)
    return decorated


def get_pagination_params(default_limit: int = 50, max_limit: int = 100) -> Tuple[int, int]:
    try:
        limit = min(int(request.args.get('limit', default_limit)), max_limit)
        skip = max(int(request.args.get('skip', 0)), 0)
    except (ValueError, TypeError):
        limit, skip = default_limit, 0
    
    return limit, skip


def get_page_params(default_limit: int = 10, max_limit: int = 50) -> Tuple[int, int, int]:
    try:
        page = max(int(request.args.get('page', 1)), 1)
        limit = min(int(request.args.get('limit', default_limit)), max_limit)
    except (ValueError, TypeError):
        page, limit = 1, default_limit
    
    skip = (page - 1) * limit
    return page, limit, skip


def clamp(value: int, min_val: int, max_val: int) -> int:
    return max(min_val, min(value, max_val))


class ModelRegistry:
    _models = {}
    
    @classmethod
    def get(cls, model_class: Type, db=None) -> Any:
        if db is None:
            db = get_db()
            if db is None:
                return None
        
        key = model_class.__name__
        if key not in cls._models:
            cls._models[key] = model_class(db)
        
        return cls._models[key]
    
    @classmethod
    def clear(cls):
        cls._models.clear()
