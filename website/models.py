from . import db
from flask_login import UserMixin
from sqlalchemy.sql import func
from datetime import datetime, date


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    user_name = db.Column(db.String(150), unique=True)
    password = db.Column(db.String(150))
    first_name = db.Column(db.String(150))
    last_name = db.Column(db.String(150))
    position = db.Column(db.String(20))
    secret_question = db.Column(db.String(150))
    secret_answer = db.Column(db.String(150))
    

class Ingredients(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ingredientName = db.Column(db.String(10000), unique=True)
    minimumStock = db.Column(db.Integer)
    unitOfMeasure = db.Column(db.Text)
    
class Recipe(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    recipeName = db.Column(db.String(150))      
    numberOfServings = db.Column(db.Integer)
    ingredients = db.Column(db.String(150))
    quantity = db.Column(db.Integer)
    unitOfMeasure = db.Column(db.String(150))
    #ingredientList = db.relationship('Ingredients', secondary=recipe_ingredients, backref='used_by')   
    #ingredientlist not used

class Inventory(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    inventoryItem = db.Column(db.String(150))
    quantity = db.Column(db.Integer)
    stockAdd = db.Column(db.Integer)
    date = db.Column(db.Date)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    postedBy = db.Column(db.String(150))
    editedBy = db.Column(db.String(150))
    editDate = db.Column(db.Date)
    authBy = db.Column(db.String(150))

class TempIngredients(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    recipeIngredients = db.Column(db.String(150))
    recipeQuantity = db.Column(db.Integer)
    recipeUOM = db.Column(db.String(100))

class dailyUsedMenuItem(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    recipeItem = db.Column(db.String(150))
    quantity = db.Column(db.Integer)
    date = db.Column(db.Date)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    postedBy = db.Column(db.String(150))
    editedBy = db.Column(db.String(150))
    editDate = db.Column(db.Date)
    authBy = db.Column(db.String(150))

class ForecastedValues(db.Model, UserMixin):
    __tablename__ = 'forecasted_values'  # Ensure this matches your actual table name

    id = db.Column(db.Integer, primary_key=True)
    recipeItem = db.Column(db.String(150), nullable=False)
    date = db.Column(db.Date, nullable=False)
    forecasted_quantity = db.Column(db.Float, nullable=False)
    mean_se = db.Column(db.Float, nullable=False)
    ci_lower = db.Column(db.Float, nullable=False)
    ci_upper = db.Column(db.Float, nullable=False)
    actual_quantity = db.Column(db.Float, nullable=True)  # This will be updated later
    dateToday = db.Column(db.Date, nullable=True) #this is the last entry on dailyUsedMenuItem
    # Optional: Add an index to speed up queries
    __table_args__ = (db.Index('idx_recipe_date', 'recipeItem', 'date'),)

#not used
class dailyInventoryList(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    inventoryItems = db.Column(db.String(150))
    unitOfMeasure = db.Column(db.String(150))
    minimumStock = db.Column(db.Integer)
#end
    
#no use 
recipe_ingredients = db.Table('recipe_ingredients',
    db.Column('recipe_name',db.Integer, db.ForeignKey('recipe.id')),
    db.Column('ingredients', db.Integer, db.ForeignKey('ingredients.id'))                               
)
#end
