import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
login_manager.login_view = 'main.login' # 'main' is the blueprint name, 'login' is the function name
login_manager.login_message_category = 'info'


def create_app(config_class=None):
    app = Flask(__name__, instance_relative_config=True)

    # Configuration
    # Default configuration
    app.config.from_mapping(
        SECRET_KEY=os.environ.get('SECRET_KEY') or 'dev_secret_key', # IMPORTANT: Change this in production!
        SQLALCHEMY_DATABASE_URI=os.environ.get('DATABASE_URL') or \
            'sqlite:///' + os.path.join(app.instance_path, 'site.db'),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        # Add other configurations here
        UPLOAD_FOLDER=os.path.join(app.root_path, '..', 'data', 'student_images'), # For student images
        ALLOWED_EXTENSIONS={'png', 'jpg', 'jpeg'}
    )

    if config_class:
        app.config.from_object(config_class)
    else:
        # Load the instance config, if it exists, when not testing
        app.config.from_pyfile('config.py', silent=True)

    # Ensure the instance folder exists
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    # Ensure the UPLOAD_FOLDER exists
    try:
        os.makedirs(app.config['UPLOAD_FOLDER'])
    except OSError:
        pass

    # Ensure the data folder for embeddings exists (if storing as files)
    # For this project, embeddings will be stored in the DB, but this is good practice
    # data_embeddings_path = os.path.join(app.root_path, '..', 'data', 'face_embeddings')
    # try:
    #     os.makedirs(data_embeddings_path)
    # except OSError:
    #     pass


    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)

    from app.models import User # Import here to avoid circular dependencies
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Register Blueprints
    from app.routes import bp as main_bp
    app.register_blueprint(main_bp)

    # Example route
    @app.route('/hello')
    def hello():
        return "Hello, World! App is running."

    return app
