"""
TrustPoints Input Validators
Validation utilities for user input
"""
import re
from typing import Tuple, List, Optional


def validate_email(email: str) -> Tuple[bool, Optional[str]]:
    """
    Validate email format
    
    Args:
        email: Email string to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not email:
        return False, "Email wajib diisi"
    
    # Basic email regex pattern
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    
    if not re.match(pattern, email.strip()):
        return False, "Format email tidak valid"
    
    return True, None


def validate_password(password: str) -> Tuple[bool, Optional[str]]:
    """
    Validate password strength
    
    Requirements:
    - Minimum 8 characters
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one digit
    
    Args:
        password: Password string to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not password:
        return False, "Password wajib diisi"
    
    if len(password) < 8:
        return False, "Password minimal 8 karakter"
    
    if not re.search(r'[A-Z]', password):
        return False, "Password harus mengandung minimal 1 huruf besar"
    
    if not re.search(r'[a-z]', password):
        return False, "Password harus mengandung minimal 1 huruf kecil"
    
    if not re.search(r'\d', password):
        return False, "Password harus mengandung minimal 1 angka"
    
    return True, None


def validate_full_name(full_name: str) -> Tuple[bool, Optional[str]]:
    """
    Validate full name
    
    Args:
        full_name: Name string to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not full_name:
        return False, "Nama lengkap wajib diisi"
    
    if len(full_name.strip()) < 2:
        return False, "Nama lengkap minimal 2 karakter"
    
    if len(full_name.strip()) > 100:
        return False, "Nama lengkap maksimal 100 karakter"
    
    return True, None


def validate_language_preference(language: str) -> Tuple[bool, Optional[str]]:
    """
    Validate language preference
    
    Args:
        language: Language code to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    allowed_languages = ['id', 'en']  # Indonesian and English
    
    if language and language not in allowed_languages:
        return False, f"Bahasa harus salah satu dari: {', '.join(allowed_languages)}"
    
    return True, None


def validate_registration_data(data: dict) -> Tuple[bool, List[str]]:
    """
    Validate all registration data
    
    Args:
        data: Registration data dictionary
        
    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    errors = []
    
    # Validate full name
    is_valid, error = validate_full_name(data.get('full_name', ''))
    if not is_valid:
        errors.append(error)
    
    # Validate email
    is_valid, error = validate_email(data.get('email', ''))
    if not is_valid:
        errors.append(error)
    
    # Validate password
    is_valid, error = validate_password(data.get('password', ''))
    if not is_valid:
        errors.append(error)
    
    return len(errors) == 0, errors


def validate_profile_update(data: dict) -> Tuple[bool, List[str]]:
    """
    Validate profile update data
    
    Args:
        data: Profile update data dictionary
        
    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    errors = []
    
    # Validate full name if provided
    if 'full_name' in data:
        is_valid, error = validate_full_name(data['full_name'])
        if not is_valid:
            errors.append(error)
    
    # Validate language preference if provided
    if 'language_preference' in data:
        is_valid, error = validate_language_preference(data['language_preference'])
        if not is_valid:
            errors.append(error)
    
    # Validate profile picture URL if provided
    if 'profile_picture' in data and data['profile_picture']:
        url = data['profile_picture']
        if not isinstance(url, str) or len(url) > 500:
            errors.append("URL foto profil tidak valid atau terlalu panjang")
    
    return len(errors) == 0, errors
