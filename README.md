# TrustPoints Backend

Backend API untuk aplikasi TrustPoints - Platform P2P Delivery dengan sistem Trust Points.

## 🚀 Tech Stack

- **Python 3.12** - Runtime
- **Flask 3.0** - Web Framework
- **Flask-SocketIO** - Real-time WebSocket
- **MongoDB 7.0** - Database
- **JWT (PyJWT)** - Authentication
- **bcrypt** - Password Hashing
- **Docker** - Containerization
- **Gunicorn + Eventlet** - Production Server

## 📁 Struktur Project

```
backend/
├── app/
│   ├── __init__.py            # Flask app factory
│   ├── config.py              # Konfigurasi aplikasi
│   ├── socket_events.py       # WebSocket event handlers
│   ├── models/
│   │   ├── __init__.py
│   │   ├── base.py            # Abstract base model class
│   │   ├── user.py            # User model (auth, points, profile)
│   │   ├── order.py           # Order model (P2P delivery)
│   │   ├── activity.py        # Activity log model
│   │   └── chat.py            # Chat/messaging model
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── auth.py            # Auth routes (register, login)
│   │   ├── profile.py         # Profile routes (get, update, password)
│   │   ├── orders.py          # Order routes (create, claim, deliver)
│   │   ├── wallet.py          # Wallet routes (balance, earn, redeem)
│   │   ├── activity.py        # Activity history routes
│   │   └── chat.py            # Chat routes (messages)
│   └── utils/
│       ├── __init__.py
│       ├── auth.py            # JWT utilities & @token_required
│       ├── responses.py       # Standardized API responses
│       ├── validators.py      # Input validation
│       └── helpers.py         # Route helper functions (DRY)
├── app.py                     # Application entry point
├── requirements.txt           # Python dependencies
├── Dockerfile                 # Docker image configuration
├── docker-compose.yml         # Multi-container orchestration
├── .env.example               # Template environment variables
└── README.md                  # Dokumentasi ini
```

## 🗄️ Database Schema

### Users Collection

```json
{
  "_id": "ObjectId",
  "full_name": "string",
  "email": "string (unique, lowercase)",
  "password": "string (bcrypt hashed)",
  "profile_picture": "string (URL) | null",
  "points": "number (default: 100)",
  "trust_score": "number (default: 0)",
  "default_address": "string | null",
  "language_preference": "string (default: 'id')",
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

### Orders Collection

```json
{
  "_id": "ObjectId",
  "order_id": "string (TP-YYYYMMDDHHMMSS-XXXXXXXX)",
  "sender_id": "string",
  "hunter_id": "string | null",
  "status": "PENDING | CLAIMED | IN_TRANSIT | DELIVERED | CANCELLED",
  "item": {
    "name": "string",
    "category": "FOOD | DOCUMENT | ELECTRONICS | FASHION | GROCERY | MEDICINE | OTHER",
    "weight": "number (kg)",
    "photo_url": "string | null",
    "description": "string",
    "is_fragile": "boolean"
  },
  "location": {
    "pickup": { "address": "string", "coords": "GeoJSON Point" },
    "destination": { "address": "string", "coords": "GeoJSON Point" }
  },
  "distance_km": "number",
  "points_cost": "number (sender pays)",
  "trust_points_reward": "number (hunter earns)",
  "notes": "string | null",
  "claimed_at": "datetime | null",
  "picked_up_at": "datetime | null",
  "delivered_at": "datetime | null",
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

### Activities Collection

```json
{
  "_id": "ObjectId",
  "user_id": "string",
  "activity_type": "ORDER_CREATED | ORDER_CLAIMED | ORDER_DELIVERED | POINTS_EARNED | POINTS_SPENT | POINTS_TRANSFERRED",
  "title": "string",
  "description": "string",
  "metadata": { ... },
  "created_at": "datetime"
}
```

### Chats Collection

```json
{
  "_id": "ObjectId",
  "order_id": "string",
  "sender_id": "string",
  "sender_name": "string",
  "message": "string",
  "message_type": "text | system | location",
  "is_read": "boolean",
  "created_at": "datetime"
}
```

## 🔌 API Endpoints

### Health Check

| Method | Endpoint  | Description           |
| ------ | --------- | --------------------- |
| GET    | `/health` | Service health status |

### Authentication

| Method | Endpoint        | Description       |
| ------ | --------------- | ----------------- |
| POST   | `/api/register` | Register new user |
| POST   | `/api/login`    | Login user        |

### Profile (🔐 Protected)

| Method | Endpoint                       | Description              |
| ------ | ------------------------------ | ------------------------ |
| GET    | `/api/profile`                 | Get current user profile |
| PUT    | `/api/profile/edit`            | Update profile           |
| POST   | `/api/profile/change-password` | Change password          |

### Wallet (🔐 Protected)

| Method | Endpoint               | Description             |
| ------ | ---------------------- | ----------------------- |
| GET    | `/api/wallet/balance`  | Get points balance      |
| POST   | `/api/wallet/earn`     | Add points (admin)      |
| POST   | `/api/wallet/redeem`   | Spend points            |
| POST   | `/api/wallet/transfer` | Transfer points to user |

### Orders (🔐 Protected)

| Method | Endpoint                               | Description                   |
| ------ | -------------------------------------- | ----------------------------- |
| POST   | `/api/orders`                          | Create new order (Sender)     |
| POST   | `/api/orders/estimate-cost`            | Estimate delivery cost        |
| GET    | `/api/orders/available`                | Get available orders (Hunter) |
| GET    | `/api/orders/nearby?lat=&lng=&radius=` | Get nearby orders             |
| GET    | `/api/orders/<order_id>`               | Get order detail              |
| PUT    | `/api/orders/claim/<order_id>`         | Claim order (Hunter)          |
| PUT    | `/api/orders/pickup/<order_id>`        | Start delivery (Hunter)       |
| PUT    | `/api/orders/deliver/<order_id>`       | Complete delivery (Hunter)    |
| PUT    | `/api/orders/cancel/<order_id>`        | Cancel order (Sender)         |
| GET    | `/api/orders/my-orders`                | Get my orders (Sender)        |
| GET    | `/api/orders/my-deliveries`            | Get my deliveries (Hunter)    |
| GET    | `/api/orders/categories`               | Get item categories           |

### Activity (🔐 Protected)

| Method | Endpoint                       | Description                    |
| ------ | ------------------------------ | ------------------------------ |
| GET    | `/api/activity/`               | Get all activities (paginated) |
| GET    | `/api/activity/recent?limit=5` | Get recent activities          |

### Chat (🔐 Protected)

| Method | Endpoint                        | Description       |
| ------ | ------------------------------- | ----------------- |
| GET    | `/api/chat/<order_id>/messages` | Get chat messages |
| POST   | `/api/chat/<order_id>/send`     | Send message      |
| PUT    | `/api/chat/<order_id>/read`     | Mark as read      |

## 💰 Points System

### Pricing (Sender pays)

- **Base**: 10 pts per km
- **Weight**: +5 pts per kg (over 1kg)
- **Fragile**: +20% surcharge
- **Minimum**: 10 pts

### Rewards (Hunter earns)

- **Base**: 10 pts per km
- **Fragile bonus**: +50%
- **Minimum**: 5 pts

### Conversion Rate

- **1 pts = Rp 100**

## 🐳 Docker Commands

```bash
# Build & run
docker-compose up --build -d

# View logs
docker-compose logs -f trustpoints-api

# Restart API
docker-compose restart trustpoints-api

# Stop all
docker-compose down

# Reset database
docker-compose down -v
```

## 🔐 Security Features

1. **Password Hashing**: bcrypt with 12 rounds
2. **JWT Tokens**: 24h expiry (configurable)
3. **Protected Routes**: `@token_required` decorator
4. **Input Validation**: Email, password, coordinates
5. **Environment Variables**: Secrets in .env

## 📝 Code Standards

Project ini mengikuti prinsip:

- **DRY** - Helper functions untuk response & database
- **Type Safety** - Type hints dengan `typing` module
- **Enums** - `OrderStatus`, `ItemCategory`, `ActivityType`
- **Maintainability** - Section separators & docstrings

## 📄 License

MIT License - TrustPoints 2024
