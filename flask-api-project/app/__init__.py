from flask import Flask

def create_app():
    app = Flask(__name__)
    
    # Load configuration
    app.config.from_pyfile('../.env')

    # Register blueprints
    from .api.routes import api as api_blueprint
    app.register_blueprint(api_blueprint, url_prefix='/api')

    return app