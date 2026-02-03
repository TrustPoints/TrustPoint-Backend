"""
TrustPoints Response Helpers
Standardized API response formatting
"""
from flask import jsonify
from typing import Any, Optional


def success_response(data: Any = None, message: str = "Success", status_code: int = 200):
    """
    Create a standardized success response
    
    Args:
        data: Response data
        message: Success message
        status_code: HTTP status code
        
    Returns:
        Flask response tuple
    """
    response = {
        'success': True,
        'message': message
    }
    
    if data is not None:
        response['data'] = data
    
    return jsonify(response), status_code


def error_response(message: str, error_code: str = "error", status_code: int = 400, errors: Optional[list] = None):
    """
    Create a standardized error response
    
    Args:
        message: Error message
        error_code: Machine-readable error code
        status_code: HTTP status code
        errors: List of detailed errors
        
    Returns:
        Flask response tuple
    """
    response = {
        'success': False,
        'message': message,
        'error': error_code
    }
    
    if errors:
        response['errors'] = errors
    
    return jsonify(response), status_code


def validation_error(errors: list):
    """
    Create a validation error response
    
    Args:
        errors: List of validation errors
        
    Returns:
        Flask response tuple
    """
    return error_response(
        message="Validasi gagal",
        error_code="validation_error",
        status_code=422,
        errors=errors
    )
