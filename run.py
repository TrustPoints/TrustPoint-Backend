from flask import Flask, jsonify
from flask_pymongo import PyMongo
from app.config import get_config

# Initialize PyMongo
mongo = PyMongo()


def create_app(config_object=None):
    app = Flask(__name__)
    
    # Load configuration
    if config_object is None:
        config_object = get_config()
    
    app.config.from_object(config_object)
    
    # Initialize extensions
    mongo.init_app(app)
    
    # Store mongo in extensions for access in routes
    app.extensions['pymongo'] = mongo
    
    # Register blueprints
    from app.routes.auth import auth_bp
    from app.routes.profile import profile_bp
    from app.routes.orders import orders_bp
    from app.routes.chat import chat_bp
    
    app.register_blueprint(auth_bp, url_prefix='/api')
    app.register_blueprint(profile_bp, url_prefix='/api')
    app.register_blueprint(orders_bp, url_prefix='/api')
    app.register_blueprint(chat_bp, url_prefix='/api')
    
    # Health check endpoint
    @app.route('/health', methods=['GET'])
    def health_check():
        """Health check endpoint for Docker/Kubernetes"""
        try:
            # Check MongoDB connection
            mongo.db.command('ping')
            db_status = 'connected'
        except Exception:
            db_status = 'disconnected'
        
        return jsonify({
            'status': 'healthy',
            'service': 'TrustPoints API',
            'database': db_status
        })
    
    # Root endpoint
    @app.route('/', methods=['GET'])
    def root():
        """Root endpoint with API information"""
        return jsonify({
            'name': 'TrustPoints API',
            'version': '1.0.0',
            'description': 'Backend API for TrustPoints P2P Delivery Application',
            'endpoints': {
                'health': '/health',
                'auth': {
                    'register': 'POST /api/register',
                    'login': 'POST /api/login'
                },
                'profile': {
                    'get': 'GET /api/profile',
                    'edit': 'PUT /api/profile/edit',
                    'change_password': 'PUT /api/change-password'
                },
                'orders': {
                    'create': 'POST /api/orders',
                    'get_available': 'GET /api/orders/available',
                    'get_nearby': 'GET /api/orders/nearby?lat=&lng=&radius=',
                    'get_detail': 'GET /api/orders/<order_id>',
                    'claim': 'PUT /api/orders/claim/<order_id>',
                    'pickup': 'PUT /api/orders/pickup/<order_id>',
                    'deliver': 'PUT /api/orders/deliver/<order_id>',
                    'cancel': 'PUT /api/orders/cancel/<order_id>',
                    'my_orders': 'GET /api/orders/my-orders',
                    'my_deliveries': 'GET /api/orders/my-deliveries',
                    'categories': 'GET /api/orders/categories'
                }
            }
        })
    
    # Error handlers
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({
            'success': False,
            'message': 'Endpoint tidak ditemukan',
            'error': 'not_found'
        }), 404
    
    @app.errorhandler(405)
    def method_not_allowed(error):
        return jsonify({
            'success': False,
            'message': 'Method tidak diizinkan',
            'error': 'method_not_allowed'
        }), 405
    
    @app.errorhandler(500)
    def internal_error(error):
        return jsonify({
            'success': False,
            'message': 'Terjadi kesalahan internal server',
            'error': 'internal_server_error'
        }), 500
    
    return app


# Create application instance
app = create_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
