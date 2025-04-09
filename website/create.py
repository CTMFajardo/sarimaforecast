from . import db
from .models import User
from sqlalchemy import func
from werkzeug.security import generate_password_hash

##not used


#admin check and creation
def create_admin():
    if not User.query.filter(func.lower(User.user_name) == func.lower('admin')).first():
        admin = User(
            user_name='admin',
            password=generate_password_hash('admin777', method='scrypt'),
            position='admin',
            first_name='admin',
            last_name='admin'
        )
        
        db.session.add(admin)
        
        db.session.commit()
