from flask import Flask
from app.routes.ai_routes import ai_bp

def create_app():
    app = Flask(__name__)
    app.register_blueprint(ai_bp, url_prefix='/api')
    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)