from flask import Flask
from app.api.routes import api

def create_app():
    app = Flask(__name__)
    # app.config.from_pyfile('app/config.py')

    app.register_blueprint(api)

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)