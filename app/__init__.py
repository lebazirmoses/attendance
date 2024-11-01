from flask import Flask
from .extensions import db, login_manager  # Import from the new extensions file
from .config import Config
from .models import User
from werkzeug.security import generate_password_hash


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "main.login"

    # Import and register routes
    from .routes import main
    app.register_blueprint(main)

    with app.app_context():
        db.create_all()
        create_default_organizer()  # Ensure the default organizer is created on startup

    return app

def create_default_organizer():
    # Check if an organizer already exists
    organizer = User.query.filter_by(username="admin").first()
    if organizer is None:
        # Create default organizer credentials
        default_organizer = User(
            username="admin",
            password=generate_password_hash("admin123"),  # Hash the password
            name="Lebazir Moses",
            role="organizer"
        )
        db.session.add(default_organizer)
        db.session.commit()
        print("Default organizer created.")
    else:
        print("Default organizer already exists.")
