import re
from typing import Tuple, List, Optional


def validate_email(email: str) -> Tuple[bool, Optional[str]]:
    if not email:
        return False, "Email wajib diisi"
    
    # Basic email regex pattern
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    
    if not re.match(pattern, email.strip()):
        return False, "Format email tidak valid"
    
    return True, None


def validate_password(password: str) -> Tuple[bool, Optional[str]]:
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
    if not full_name:
        return False, "Nama lengkap wajib diisi"
    
    if len(full_name.strip()) < 2:
        return False, "Nama lengkap minimal 2 karakter"
    
    if len(full_name.strip()) > 100:
        return False, "Nama lengkap maksimal 100 karakter"
    
    return True, None


def validate_language_preference(language: str) -> Tuple[bool, Optional[str]]:
    allowed_languages = ['id', 'en'] 
    
    if language and language not in allowed_languages:
        return False, f"Bahasa harus salah satu dari: {', '.join(allowed_languages)}"
    
    return True, None


def validate_registration_data(data: dict) -> Tuple[bool, List[str]]:
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
    
    # Validate default_address if provided
    if 'default_address' in data and data['default_address']:
        addr = data['default_address']
        if not isinstance(addr, dict):
            errors.append("Format alamat tidak valid")
        else:
            if 'address' not in addr or not addr['address']:
                errors.append("Alamat wajib diisi")
            elif len(addr['address']) > 500:
                errors.append("Alamat terlalu panjang (maksimal 500 karakter)")
            
            if 'latitude' in addr and 'longitude' in addr:
                is_valid, error = validate_coordinates(addr['latitude'], addr['longitude'])
                if not is_valid:
                    errors.append(error)
            else:
                errors.append("Koordinat latitude dan longitude wajib diisi")
    
    return len(errors) == 0, errors


# ============================================
# ORDER VALIDATORS
# ============================================

VALID_CATEGORIES = ['FOOD', 'DOCUMENT', 'ELECTRONICS', 'FASHION', 'GROCERY', 'MEDICINE', 'OTHER']


def validate_coordinates(lat: float, lng: float) -> Tuple[bool, Optional[str]]:
    try:
        lat = float(lat)
        lng = float(lng)
    except (TypeError, ValueError):
        return False, "Koordinat harus berupa angka"
    
    if not (-90 <= lat <= 90):
        return False, "Latitude harus antara -90 dan 90"
    
    if not (-180 <= lng <= 180):
        return False, "Longitude harus antara -180 dan 180"
    
    return True, None


def validate_item_data(item: dict) -> Tuple[bool, List[str]]:
    errors = []
    
    if not item:
        return False, ["Data item wajib diisi"]
    
    # Validate item name
    name = item.get('name', '')
    if not name or len(name.strip()) < 2:
        errors.append("Nama barang minimal 2 karakter")
    if len(name) > 100:
        errors.append("Nama barang maksimal 100 karakter")
    
    # Validate category
    category = item.get('category', 'OTHER')
    if category not in VALID_CATEGORIES:
        errors.append(f"Kategori harus salah satu dari: {', '.join(VALID_CATEGORIES)}")
    
    # Validate weight
    weight = item.get('weight', 0)
    try:
        weight = float(weight)
        if weight < 0:
            errors.append("Berat tidak boleh negatif")
        if weight > 50:
            errors.append("Berat maksimal 50 kg")
    except (TypeError, ValueError):
        errors.append("Berat harus berupa angka")
    
    # Validate photo_url if provided
    photo_url = item.get('photo_url')
    if photo_url and (not isinstance(photo_url, str) or len(photo_url) > 500):
        errors.append("URL foto tidak valid atau terlalu panjang")
    
    # Validate description
    description = item.get('description', '')
    if len(description) > 500:
        errors.append("Deskripsi maksimal 500 karakter")
    
    return len(errors) == 0, errors


def validate_location_data(location: dict) -> Tuple[bool, List[str]]:
    errors = []
    
    if not location:
        return False, ["Data lokasi wajib diisi"]
    
    # Validate pickup
    pickup = location.get('pickup', {})
    if not pickup:
        errors.append("Lokasi pickup wajib diisi")
    else:
        if not pickup.get('address') or len(pickup['address'].strip()) < 5:
            errors.append("Alamat pickup minimal 5 karakter")
        if len(pickup.get('address', '')) > 300:
            errors.append("Alamat pickup maksimal 300 karakter")
        
        lat = pickup.get('latitude')
        lng = pickup.get('longitude')
        if lat is None or lng is None:
            errors.append("Koordinat pickup wajib diisi")
        else:
            is_valid, error = validate_coordinates(lat, lng)
            if not is_valid:
                errors.append(f"Koordinat pickup: {error}")
    
    # Validate destination
    destination = location.get('destination', {})
    if not destination:
        errors.append("Lokasi tujuan wajib diisi")
    else:
        if not destination.get('address') or len(destination['address'].strip()) < 5:
            errors.append("Alamat tujuan minimal 5 karakter")
        if len(destination.get('address', '')) > 300:
            errors.append("Alamat tujuan maksimal 300 karakter")
        
        lat = destination.get('latitude')
        lng = destination.get('longitude')
        if lat is None or lng is None:
            errors.append("Koordinat tujuan wajib diisi")
        else:
            is_valid, error = validate_coordinates(lat, lng)
            if not is_valid:
                errors.append(f"Koordinat tujuan: {error}")
    
    return len(errors) == 0, errors


def validate_order_creation(data: dict) -> Tuple[bool, List[str]]:
    errors = []
    
    # Validate item
    is_valid, item_errors = validate_item_data(data.get('item', {}))
    if not is_valid:
        errors.extend(item_errors)
    
    # Validate location
    is_valid, location_errors = validate_location_data(data.get('location', {}))
    if not is_valid:
        errors.extend(location_errors)
    
    # Validate distance
    distance = data.get('distance_km')
    if distance is None:
        errors.append("Jarak pengiriman wajib diisi")
    else:
        try:
            distance = float(distance)
            if distance <= 0:
                errors.append("Jarak pengiriman harus lebih dari 0")
            if distance > 100:
                errors.append("Jarak pengiriman maksimal 100 km")
        except (TypeError, ValueError):
            errors.append("Jarak pengiriman harus berupa angka")
    
    # Validate notes if provided
    notes = data.get('notes', '')
    if notes and len(notes) > 500:
        errors.append("Catatan maksimal 500 karakter")
    
    return len(errors) == 0, errors


def validate_nearby_query(lat: str, lng: str, radius: str = None) -> Tuple[bool, List[str], dict]:
    errors = []
    parsed = {}
    
    # Parse and validate latitude
    if lat is None:
        errors.append("Parameter 'lat' wajib diisi")
    else:
        try:
            parsed['latitude'] = float(lat)
            if not (-90 <= parsed['latitude'] <= 90):
                errors.append("Latitude harus antara -90 dan 90")
        except ValueError:
            errors.append("Latitude harus berupa angka")
    
    # Parse and validate longitude
    if lng is None:
        errors.append("Parameter 'lng' wajib diisi")
    else:
        try:
            parsed['longitude'] = float(lng)
            if not (-180 <= parsed['longitude'] <= 180):
                errors.append("Longitude harus antara -180 dan 180")
        except ValueError:
            errors.append("Longitude harus berupa angka")
    
    # Parse and validate radius (optional, default 10km)
    if radius is not None:
        try:
            parsed['radius'] = float(radius)
            if parsed['radius'] <= 0:
                errors.append("Radius harus lebih dari 0")
            if parsed['radius'] > 50:
                errors.append("Radius maksimal 50 km")
        except ValueError:
            errors.append("Radius harus berupa angka")
    else:
        parsed['radius'] = 10.0  # Default 10km
    
    return len(errors) == 0, errors, parsed
