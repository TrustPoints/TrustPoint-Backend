from flask import jsonify
from typing import Any, Dict, List, Optional, Tuple

# Type alias for Flask response
FlaskResponse = Tuple[Any, int]


def success_response(
    data: Optional[Any] = None,
    message: str = "Success",
    status_code: int = 200
) -> FlaskResponse:
    response: Dict[str, Any] = {
        'success': True,
        'message': message
    }
    
    if data is not None:
        response['data'] = data
    
    return jsonify(response), status_code


def error_response(
    message: str,
    error_code: str = "error",
    status_code: int = 400,
    errors: Optional[List[str]] = None,
    data: Optional[Dict] = None
) -> FlaskResponse:
    response: Dict[str, Any] = {
        'success': False,
        'message': message,
        'error': error_code
    }
    
    if errors:
        response['errors'] = errors
    
    if data:
        response['data'] = data
    
    return jsonify(response), status_code


def validation_error(errors: List[str]) -> FlaskResponse:
    return error_response(
        message="Validasi gagal",
        error_code="validation_error",
        status_code=422,
        errors=errors
    )


# ===========================================
# Common Error Responses (DRY helpers)
# ===========================================

def unauthorized_error(message: str = "User tidak terautentikasi") -> FlaskResponse:
    return error_response(message=message, error_code="unauthorized", status_code=401)


def not_found_error(resource: str = "Resource") -> FlaskResponse:
    return error_response(message=f"{resource} tidak ditemukan", error_code="not_found", status_code=404)


def forbidden_error(message: str = "Akses ditolak") -> FlaskResponse:
    return error_response(message=message, error_code="forbidden", status_code=403)


def database_error() -> FlaskResponse:
    return error_response(message="Database tidak tersedia", error_code="database_error", status_code=500)


def server_error(message: str = "Terjadi kesalahan pada server") -> FlaskResponse:
    return error_response(message=message, error_code="server_error", status_code=500)


def missing_data_error() -> FlaskResponse:
    return error_response(message="Data tidak ditemukan", error_code="missing_data", status_code=400)
