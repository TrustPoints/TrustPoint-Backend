# TrustPoints Backend

Backend API untuk aplikasi TrustPoints - Platform P2P Delivery dengan sistem trust score.

## 🚀 Tech Stack

- **Python 3.12** - Runtime
- **Flask** - Web Framework
- **MongoDB** - Database
- **JWT (PyJWT)** - Authentication
- **bcrypt** - Password Hashing
- **Docker** - Containerization
- **Gunicorn** - Production Server

## 📁 Struktur Project

```
Backend/
├── app/
│   ├── __init__.py
│   ├── config.py              # Konfigurasi aplikasi
│   ├── models/
│   │   ├── __init__.py
│   │   └── user.py            # User model & database operations
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── auth.py            # Auth routes (register, login)
│   │   └── profile.py         # Profile routes (get, update)
│   └── utils/
│       ├── __init__.py
│       ├── auth.py            # JWT utilities & @token_required decorator
│       ├── responses.py       # Standardized API responses
│       └── validators.py      # Input validation
├── app.py                     # Application entry point
├── requirements.txt           # Python dependencies
├── Dockerfile                 # Docker image configuration
├── docker-compose.yml         # Multi-container orchestration
├── .env                       # Environment variables (jangan commit!)
├── .env.example               # Template environment variables
├── .gitignore                 # Git ignore rules
└── README.md                  # Dokumentasi ini
```

## 🗄️ Database Schema (Users)

```json
{
  "_id": "ObjectId",
  "full_name": "string",
  "email": "string (unique, lowercase)",
  "password": "string (bcrypt hashed)",
  "profile_picture": "string (URL) | null",
  "trust_score": "number (default: 0)",
  "language_preference": "string (default: 'id')",
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

## 🔌 API Endpoints

### Health Check

```
GET /health
```

Response:

```json
{
  "status": "healthy",
  "service": "TrustPoints API",
  "database": "connected"
}
```

### Register

```
POST /api/register
Content-Type: application/json

{
  "full_name": "John Doe",
  "email": "john@example.com",
  "password": "Password123"
}
```

Response (201):

```json
{
  "success": true,
  "message": "Registrasi berhasil",
  "data": {
    "user": {
      "user_id": "...",
      "full_name": "John Doe",
      "email": "john@example.com",
      "profile_picture": null,
      "trust_score": 0,
      "language_preference": "id",
      "created_at": "...",
      "updated_at": "..."
    },
    "token": "eyJ..."
  }
}
```

### Login

```
POST /api/login
Content-Type: application/json

{
  "email": "john@example.com",
  "password": "Password123"
}
```

Response (200):

```json
{
  "success": true,
  "message": "Login berhasil",
  "data": {
    "user": { ... },
    "token": "eyJ..."
  }
}
```

### Get Profile (Protected)

```
GET /api/profile
Authorization: Bearer <token>
```

Response (200):

```json
{
  "success": true,
  "message": "Profil berhasil diambil",
  "data": {
    "user": { ... }
  }
}
```

### Update Profile (Protected)

```
PUT /api/profile/edit
Authorization: Bearer <token>
Content-Type: application/json

{
  "full_name": "John Updated",
  "profile_picture": "https://example.com/photo.jpg",
  "language_preference": "en"
}
```

Response (200):

```json
{
  "success": true,
  "message": "Profil berhasil diupdate",
  "data": {
    "user": { ... }
  }
}
```

## 🐳 Cara Menjalankan dengan Docker

### 1. Clone & Setup Environment

```bash
# Masuk ke direktori project
cd Backend

# Copy environment file
cp .env.example .env

# Edit .env dan ganti nilai-nilai berikut:
# - JWT_SECRET_KEY (gunakan string random yang kuat)
# - SECRET_KEY (gunakan string random yang kuat)
```

### 2. Build & Run dengan Docker Compose

```bash
# Build dan jalankan semua services
docker-compose up --build

# Atau jalankan di background (detached mode)
docker-compose up --build -d
```

### 3. Verifikasi

```bash
# Cek status containers
docker-compose ps

# Cek logs
docker-compose logs -f api

# Test health endpoint
curl http://localhost:5000/health
```

### 4. Akses Aplikasi

- **API**: http://localhost:5000
- **MongoDB**: localhost:27017
- **Mongo Express** (opsional): http://localhost:8081
  - Untuk mengaktifkan: `docker-compose --profile debug up`

### 5. Stop Services

```bash
# Stop semua containers
docker-compose down

# Stop dan hapus volumes (reset database)
docker-compose down -v
```

## 🔧 Development Mode (Tanpa Docker)

### 1. Setup Virtual Environment

```bash
# Buat virtual environment
python3.12 -m venv venv

# Aktivasi (macOS/Linux)
source venv/bin/activate

# Aktivasi (Windows)
venv\Scripts\activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Setup MongoDB

Pastikan MongoDB sudah running di localhost:27017

### 4. Setup Environment

```bash
cp .env.example .env
# Edit .env dan sesuaikan MONGO_URI jika perlu
```

### 5. Run Application

```bash
# Development mode
python app.py

# Atau dengan Flask CLI
flask run --host=0.0.0.0 --port=5000
```

## 🔐 Keamanan

1. **Password Hashing**: Menggunakan bcrypt dengan 12 rounds
2. **JWT Tokens**: Token expires setelah 24 jam (configurable)
3. **Protected Routes**: Decorator `@token_required` untuk route yang membutuhkan auth
4. **Input Validation**: Validasi email, password strength, dan input lainnya
5. **Environment Variables**: Secrets disimpan di .env (tidak di-commit)

## 📝 Password Requirements

- Minimal 8 karakter
- Minimal 1 huruf besar
- Minimal 1 huruf kecil
- Minimal 1 angka

## 🌐 Supported Languages

- `id` - Indonesian (default)
- `en` - English

## 📄 License

MIT License - TrustPoints 2024
