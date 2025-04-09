from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from os import path, makedirs
from flask_login import LoginManager
from flask_migrate import Migrate #for updating models
from werkzeug.security import generate_password_hash
from sqlalchemy.sql import func


#account creation
def create_admin():
    from . import db
    from .models import User

    # Check if the 'admin' user exists, case-insensitive
    adminCheck = User.query.filter_by(user_name='admin').first()
    
    if not adminCheck:
        # Create the admin user if not found
        admin = User(
            user_name='admin',
            password=generate_password_hash('admin777', method='scrypt'),  # Hash the password
            position='admin',
            first_name='admin',
            last_name='admin'
        )
        
        # Add the admin to the session and commit the changes to the database
        db.session.add(admin)
        db.session.commit()

db = SQLAlchemy()
migrate = Migrate()  # Create Migrate object for udpating models
DB_NAME = "database.db"


def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'amacc'
    app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{DB_NAME}"
    db.init_app(app)
    migrate.init_app(app, db)  # **Initialize Migrate with app and db**

    ###FOR TESTING IMPORT EXPORT###
    UPLOAD_FOLDER = 'uploads/'
    EXPORT_FOLDER = 'exports/'
    app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
    app.config['EXPORT_FOLDER'] = EXPORT_FOLDER

    # Create the directories if they don't exist
    makedirs(UPLOAD_FOLDER, exist_ok=True)
    makedirs(EXPORT_FOLDER, exist_ok=True)
    ###

    from .views import views
    from .auth import auth

    app.register_blueprint(views, url_prefix='/')
    app.register_blueprint(auth, url_prefix='/')

    from .models import User, Inventory, Recipe, Ingredients, recipe_ingredients

    #new database only
    #with app.app_context():
        #db.create_all()
        


    
    login_manager = LoginManager()
    login_manager.login_view = 'auth.login'
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(id):
        return User.query.get(int(id))
    

    return app


