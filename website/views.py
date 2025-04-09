from flask import Blueprint, render_template, request, flash,redirect, url_for,send_file,current_app, jsonify
from flask_login import login_required, current_user
from .models import Ingredients, Recipe, Inventory, TempIngredients, dailyUsedMenuItem, User, ForecastedValues
from werkzeug.security import check_password_hash, generate_password_hash
from . import db
from sqlalchemy import func, desc
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import plotly.graph_objs as go
import plotly.io as pio


#my sarima codes
#from .sarima_util import train_sarima_for_all_items, make_predictions_for_all_items, get_file_modification_date, create_notepad_with_date, file_path, load_all_sarima_models
from .sarimaauto import forecastAllRecipes, checkForecastDates

from .misc_util import dateToWords, get_dates_with_no_entries, upload_excel_to_db, export_db_to_excel


#dont use streamlit

#import streamlit as st
import matplotlib
matplotlib.use('Agg')
import pandas as pd
import matplotlib.pyplot as plt
from io import BytesIO
import base64

#for export import
import os
from werkzeug.utils import secure_filename

views = Blueprint('views', __name__)


#get todays date
currentDateTime = datetime.now() #this also gets the current tam
dateToday = currentDateTime.date() #this removes the time
formattedDate = currentDateTime.strftime("%B %d, %Y") #stringMarch12

@views.route('/', methods=['GET', 'POST'])
@login_required
def home():
    allRecipe = Recipe.query.all()
    allInventory = Inventory.query.all()
    allIngredients = Ingredients.query.all()
    dailyUsed = dailyUsedMenuItem.query.all()
    
    #datetime
    #currentDateTime = datetime.now()
    #dateToday = currentDateTime.date()
    #formattedDate = dateToday.strftime("%Y-%m-%d") #string

    #sort the sales (not used)
    latestDateOrdered = dailyUsedMenuItem.query.order_by(desc(dailyUsedMenuItem.date)).first().date
    latestOrderedEntries = dailyUsedMenuItem.query.filter_by(date=latestDateOrdered).all()
    salesDate = dateToWords(latestDateOrdered)

    #list all dates with entry
    salesEntries = db.session.query(dailyUsedMenuItem.date).distinct().all()
    salesEntries1 = [date[0] for date in salesEntries]
    formattedDistinctDates = [date.strftime("%B %d, %Y") for date in salesEntries1]
    
    

    # Handle the selected date from dropdown
    salesDateQuery = request.args.get('salesDateQuery')
    if salesDateQuery:
        selected_date = datetime.strptime(salesDateQuery, "%B %d, %Y").strftime("%Y-%m-%d")
        latestOrderedEntries = dailyUsedMenuItem.query.filter_by(date=selected_date).all()
        latestSalesDateWords = salesDateQuery

    else:
        latestDateOrdered = dailyUsedMenuItem.query.order_by(desc(dailyUsedMenuItem.date)).first().date
        latestOrderedEntries = dailyUsedMenuItem.query.filter_by(date=latestDateOrdered).all()
        latestSalesDateWords = latestDateOrdered.strftime("%B %d, %Y")

    #generate bargraph
    dailyItems = [item.recipeItem for item in latestOrderedEntries]
    quantities = [item.quantity for item in latestOrderedEntries]

    # Create Matplotlib bar graph with smaller size
    fig, ax = plt.subplots(figsize=(8, 6))  # Adjust figure size as needed
    ax.bar(dailyItems, quantities, color='#3498db', alpha=0.8)  # Set bar color and opacity
    ax.set_xlabel('Recipe Item', fontsize=12)  # Customize x-axis label and font size
    ax.set_ylabel('Quantity', fontsize=12)  # Customize y-axis label and font size
    ax.set_title(f'Daily Used Menu Items - {latestSalesDateWords}', fontsize=14)  # Set title and font size
    ax.tick_params(axis='x', rotation=45)  # Rotate x-axis labels if necessary
    fig.tight_layout()

    # Save plot to a BytesIO object
    buffer = BytesIO()
    plt.savefig(buffer, format='png')
    buffer.seek(0)
    plot_data = base64.b64encode(buffer.getvalue()).decode()

    # Embed plot in HTML
    graph = f'<img src="data:image/png;base64,{plot_data}" alt="Daily Used Menu Items Graph" class="img-fluid">'
    
    # Close the plot to release resources
    plt.close(fig)
    # End of bargraph

    #stock check
    latestDateInven = Inventory.query.order_by(desc(Inventory.date)).first().date
    latestInventoryEntry = Inventory.query.filter_by(date=latestDateInven).all()
    latestInvenDateWords = latestDateInven.strftime("%B %d, %Y")

    allBelowMinimum = False
  

    for entry in latestInventoryEntry:
        ingredient = Ingredients.query.filter_by(ingredientName=entry.inventoryItem).first()
        if ingredient and entry.quantity < ingredient.minimumStock:
            allBelowMinimum = True
            break
    
    stockDate = dateToWords(latestDateInven)
    
    # For Inventory
    dates_with_no_entries_inventory = get_dates_with_no_entries(Inventory, db.session)
    # For dailyUsedMenuItem
    dates_with_no_entries_menu_item = get_dates_with_no_entries(dailyUsedMenuItem, db.session)



    return render_template("home.html",user=current_user, dateToday=formattedDate,
                           stockCheck=allBelowMinimum, stockDate=stockDate,
                           latestInventoryEntry=latestInventoryEntry,latestInvWord=latestInvenDateWords,
                           latestOrderedEntries=latestOrderedEntries,
                           salesDate=salesDate, allIngredients=allIngredients,
                           dateInvenNoEntries=dates_with_no_entries_inventory,
                           datesMenuUsedNoEntries=dates_with_no_entries_menu_item,
                           latestSalesDateWords=latestSalesDateWords, dailySalesDate=formattedDistinctDates,
                           dailyUsed=dailyUsed,
                           graph=graph)



@views.route('/inventory', methods=['GET','POST'])
@login_required
def inventory():
    allIngredients = Ingredients.query.order_by(Ingredients.ingredientName).all()


    if request.method == 'POST':
        if request.form['action'] == 'addAll':
            form_data = {}
            has_empty_field = False 

            for dailyList in allIngredients:
                ingredient_name = dailyList.ingredientName
                quantity = request.form.get(ingredient_name)
                date = request.form.get('currentDate')
                #begInv = request.form.get('prev'+ingredient_name)
                addInv = request.form.get('add'+ingredient_name)

                form_data[ingredient_name] = quantity
                if quantity is not None and quantity != '':
                    #date = datetime.strptime(date, '%Y-%m-%d').date()
                    date_object = datetime.strptime(date, "%B %d, %Y").date()
                    if addInv is None:
                        addInv = 0

                    inventory = Inventory(
                        inventoryItem=ingredient_name,
                        quantity=int(quantity),
                        #beginQuantity=int(begInv),
                        date=date_object,
                        stockAdd=addInv,
                        user_id=current_user.id,
                        postedBy=current_user.first_name + " " + current_user.last_name
                    )
                    db.session.add(inventory)
                else:
                    has_empty_field = True

            if has_empty_field:
                flash('One or more fields are empty', category='error')
            else:
                db.session.commit()
                flash('Logged Daily Inventory', category='success')
                return redirect(url_for('views.inventory'))
    
        if request.form['action'] == 'checkInventory':
            date = request.form.get('checkInventory')
            dateCheck = Inventory.query.filter(Inventory.date == 
                                                date).first()
            date_obj = datetime.strptime(date, "%Y-%m-%d").date()
            chosenDate = date_obj.strftime("%B %d, %Y")

            


            if date == "":
                flash('No inventory on that date', category='error')
            if date_obj > dateToday:
                flash('Date selected cannot be in the future',category='error')
            else:
                dateCheck = Inventory.query.filter(Inventory.date == 
                            date).first()
                if dateCheck:
                    selectedDate = datetime.strptime(date, '%Y-%m-%d').date()
                    previousDate = selectedDate - timedelta(days=1)

                    filteredDate = Inventory.query.filter_by(date=date).order_by(Inventory.inventoryItem).all()
                    filteredDate2 = Inventory.query.filter_by(date=previousDate).all()
                    postedBy = filteredDate[0].postedBy

                    hasEditDate = Inventory.query.filter_by(date=selectedDate).filter(Inventory.editDate.isnot(None)).first()
                    editDate= False
                    editedBy= False
                    editAuth=False

                    if hasEditDate is not None:
                        editDate= hasEditDate.editDate
                        editedBy= hasEditDate.editedBy
                        editAuth= hasEditDate.authBy
                    else:
                        editDate=False
                    return render_template("inventory.html", user=current_user, dateToday=formattedDate,
                                    checkInv=filteredDate,prevInv=filteredDate2,
                                    date=date_obj,dateWords=chosenDate,
                                    previousDate=previousDate,
                                    postedBy=postedBy, editDate=editDate,
                                    editedBy=editedBy,editAuth=editAuth,
                                    minIngredients=allIngredients,selectDate=date)            
                else:
                    selectedDate = datetime.strptime(date, '%Y-%m-%d').date()
                    previousDate = selectedDate - timedelta(days=1)
                    
                    #in word
                    
                    filteredDate2 = Inventory.query.filter_by(date=previousDate).all()
                    

                    return render_template("inventory.html", user=current_user, dateToday=formattedDate,
                                    dailyList=allIngredients, date=chosenDate,
                                    prevInv=filteredDate2)
                
        if request.form['action'] == 'authSupervisor':
            user_name = request.form.get('authName')
            password = request.form.get('authPass')
            selectedDate = request.form.get('currentDate')
            selectDate = request.form.get('selectDate')

            date_obj = datetime.strptime(selectedDate, "%Y-%m-%d").date()
            selectedDateWords = date_obj.strftime("%B %d, %Y")

            filteredDate = Inventory.query.filter_by(date=selectDate).order_by(Inventory.inventoryItem).all()
            
            authUser = User.query.filter_by(user_name=user_name).first()
            if authUser:
                if authUser.position == "Clerk":
                    flash('User not authorized',category='error')
                else:
                    if check_password_hash(authUser.password, password):
                        flash('Authorization successful!',category='success')
                        editFilteredDate = Inventory.query.filter_by(date=selectedDate).order_by(Inventory.inventoryItem).all()
                        authBy = authUser.first_name + " " + authUser.last_name

                        return render_template("inventory.html",editFilteredDate=editFilteredDate,
                                               authBy=authBy, editCurrentDate=date_obj,
                                                dateWords=selectedDateWords, filteredDate=filteredDate,
                                               selectDate=selectDate,
                                               user=current_user)
                    else:
                        flash('Incorrect password',category='error')
            else:
                flash('Username is invalid',category='error')

        if request.form['action'] == 'editInventory':
            dateEdit = request.form.get('dateToEdit')
            authorizedBy = request.form.get('authUser')
            date_obj = datetime.strptime(dateEdit, "%Y-%m-%d").date()
            
            selectDate=request.form.get('selectDate') #no usee
            filteredDate = Inventory.query.filter_by(date=date_obj).order_by(Inventory.inventoryItem).all()

            editFilteredDate = Inventory.query.filter_by(date=date_obj).all()
            #form_data = {}
            has_empty_field = False

            for editItems in filteredDate:
                ingredient_name = editItems.inventoryItem
                quantity = request.form.get('add'+ ingredient_name)

                
                #form_data[ingredient_name] = quantity
                if quantity is not None and quantity.strip() != '':                    
                        editItems.quantity=int(quantity)
                        editItems.editedBy=current_user.first_name + " " + current_user.last_name
                        editItems.authBy=authorizedBy
                        editItems.editDate=datetime.now().date()                    
                else:
                    has_empty_field = True

            if has_empty_field:
                flash('One or more fields are empty', category='error')
            else:
                db.session.commit()
                flash('Logged Daily Inventory', category='success')
                return redirect(url_for('views.inventory'))
        
        

        #for testing only
        #if request.form['action'] == 'deleteAll':
            #db.session.query(Inventory).delete()
            #db.session.commit()
            #flash('Deleted Daily Inventory', category='success')
            #return redirect(url_for('views.inventory'))             
    if request.method == 'GET':
        date = request.args.get('date')

        if date:
            #selectedDate = datetime.strptime(date, '%Y-%m-%d').date()

            return render_template("inventory.html", user=current_user, dateToday=formattedDate,
                                   dailyList=allIngredients,date=date)
    return render_template("inventory.html", user=current_user)

@views.route('/ingredients',methods=['GET', 'POST'])
@login_required
def ingredients():
    
    #authorization check
    allowed_positions = ['admin', 'Manager', 'Supervisor' ]

    if current_user.position not in allowed_positions:
        flash('You are not authorized to access this page.', category='error')
        return redirect(url_for('views.home'))
    
    allIngredients = Ingredients.query.order_by(Ingredients.ingredientName).all()
    
    
    if request.method == 'POST':
        if request.form['action'] == 'add':
            ingredientName = request.form.get('ingredientName')
            minimumStock = request.form.get('minimumStock')
            nameCheck = Ingredients.query.filter(func.lower(Ingredients.ingredientName) == 
                                                 func.lower(ingredientName)).first()
            if nameCheck:
                flash('Ingredient already exists',category='error')
            elif len(ingredientName) < 2:
                flash('Name is too short', category='error')
            else:
                new_ingredient = Ingredients(ingredientName=ingredientName,minimumStock=minimumStock)
                db.session.add(new_ingredient)
                db.session.commit()
                flash('Ingredient added to list', category='success')
                return redirect(url_for('views.ingredients'))
        if request.form['action'] == 'remove':
            ingredientName = request.form.get('ingredientListSelect')
            Ingredients.query.filter_by(ingredientName=ingredientName).delete()
            db.session.commit()
            flash('Ingredient removed list', category='success')
            return redirect(url_for('views.ingredients'))
    return render_template("ingredients.html",user=current_user, allIngredients=allIngredients,dateToday=formattedDate)
   

@views.route('/forecast',methods=['GET', 'POST'])
@login_required
def forecast():

    """""
    modDate = get_file_modification_date(file_path)
    models = {}

    if request.method == 'POST':
        if request.form['action'] == 'trainModel':
            models = train_sarima_for_all_items()
            flash('Forecast Model Trained', category='success')
            return render_template("forecast.html",user=current_user,dateToday=formattedDate,
                                   modDate=modDate,models=models
                                   )
        if request.form['action'] == 'loadModel':
            models = load_all_sarima_models()
            flash('Forecast Model Loaded', category='success')
            return render_template("forecast.html",user=current_user,dateToday=formattedDate,
                                   modDate=modDate,models=models)
        if request.form['action'] == 'forecast':
            steps = request.form.get('minimumDays')
            steps = int(steps)
            models = load_all_sarima_models()

            if not steps:
                flash('Please provide a valid number for days.', category='error')
                return render_template("forecast.html", user=current_user, dateToday=formattedDate, modDate=modDate)
            else:
                if models:
                    make_predictions_for_all_items(models, steps)
                    # Retrieve the latest forecast entry by ordering the dates in descending order
                    latest_forecast = ForecastedValues.query.order_by(ForecastedValues.date.desc()).first()

                    # If there is a latest forecast, get the date
                    if latest_forecast:
                        latest_date = latest_forecast.date.strftime('%b %d, %Y')  # Format the date as "Month Day, Year"
                    else:
                        latest_date = None

                    
                    # Render the template with forecasted values and the latest date
                    return render_template("forecast.html", user=current_user, dateToday=formattedDate,
                                        modDate=modDate, models=models, predictions=formatted_forecasts,
                                        latest_date=latest_date)  
                else:
                    flash('No models found, please train or load models first.', category='error')
                    return render_template("forecast.html", user=current_user, dateToday=formattedDate,
                                        modDate=modDate, models=models)
        if request.form['action'] == 'showData' :
            # Retrieve the latest forecast entry by ordering the dates in descending order
            latest_forecast = ForecastedValues.query.order_by(ForecastedValues.date.desc()).first()

            # If there is a latest forecast, get the date
            if latest_forecast:
                latest_date = latest_forecast.date.strftime('%b %d, %Y')  # Format the date as "Month Day, Year"
            else:
                latest_date = None

            # If you want to load forecasted values from the database
            forecasted_values = ForecastedValues.query.filter(ForecastedValues.date == latest_forecast.date).all()  # Get all forecasted values from the DB

            # Format the forecasted data
            formatted_forecasts = [
                {
                    "recipe_item": forecast.recipeItem,
                    "date": forecast.date.strftime('%b %d, %Y'),  # Format date as "Month Day, Year"
                    "forecasted_quantity": forecast.forecasted_quantity,
                    "mean_se": forecast.mean_se,
                    "ci_lower": forecast.ci_lower,
                    "ci_upper": forecast.ci_upper,
                }
                for forecast in forecasted_values
            ]
            
            # Calculate totals for the forecasted values
            total_forecasted_quantity = sum(f['forecasted_quantity'] for f in formatted_forecasts)
            total_ci_lower = sum(f['ci_lower'] for f in formatted_forecasts)
            total_ci_upper = sum(f['ci_upper'] for f in formatted_forecasts)

            # Render the template with forecasted values and the latest date
            return render_template("forecast.html", user=current_user, dateToday=formattedDate,
                                modDate=modDate, models=models, predictions=formatted_forecasts,
                                total_forecasted_quantity=total_forecasted_quantity,
                                total_ci_lower=total_ci_lower, total_ci_upper=total_ci_upper,
                                latest_date=latest_date)  # Pass the latest date to the template
    """
    lastEntry = db.session.query(dailyUsedMenuItem).order_by(dailyUsedMenuItem.date.desc()).first()
    lastEntryToWords = lastEntry.date.strftime("%B %d, %Y")

    if lastEntry:
        lastEntryDate = lastEntry.date

        dateDifference = dateToday - lastEntryDate
        daysDifference = dateDifference.days

    if request.method == 'POST':
        if request.form['action'] == 'forecast':

            
            dtFrom = request.form.get('dtFrom')
            dtTo = request.form.get('dtTo')
            dateFrom = datetime.strptime(dtFrom, "%Y-%m-%d").date()
            dateTo = datetime.strptime(dtTo, "%Y-%m-%d").date()
            
            dateFromFormatted = datetime.strptime(dtFrom, "%Y-%m-%d").strftime("%B %d, %Y")
            dateToFormatted = datetime.strptime(dtTo, "%Y-%m-%d").strftime("%B %d, %Y")
            
            checkRequestedDates = checkForecastDates(dateFrom, dateTo)

            if not checkRequestedDates:
                #compute steps
                forecastDaysInput = int(request.form.get('forecastDaysInput'))
                daysAdvance = int(request.form.get('minusCurrentDate'))
                totalSteps = daysDifference + forecastDaysInput + daysAdvance

                with current_app.app_context():
                    forecastAllRecipes(totalSteps)
                    
            latestEntryForecasted = db.session.query(ForecastedValues).order_by(ForecastedValues.dateToday.desc()).first()

            # Filter only forecasted values that fall in the selected date range
            # and are part of the latest forecast batch (based on dateToday)
            results = (
                db.session.query(
                    ForecastedValues.recipeItem,
                    func.sum(ForecastedValues.forecasted_quantity).label('total')
                )
                .filter(
                    ForecastedValues.date.between(dateFrom, dateTo),
                    ForecastedValues.dateToday == latestEntryForecasted.dateToday
                )
                .group_by(ForecastedValues.recipeItem)
                .order_by(ForecastedValues.recipeItem)
                .all()
            )

            forecast_summary = [
                {'recipe': r.recipeItem, 'total': float(r.total)} for r in results]

            context = {
                'dailyUsed' : {
                    'lastEntry' : lastEntry,
                    'lastEntryToWords' : lastEntryToWords
                },
                'forecastSummary': forecast_summary,
                'dt_from': dateFromFormatted,
                'dt_to': dateToFormatted,
                'dt_from_raw': dateFrom,
                'dt_to_raw': dateTo

            }

            return render_template("forecast.html",user=current_user,dateToday=formattedDate,
                                    **context)


    context = {
        'dailyUsed' : {
            'lastEntry' : lastEntry,
            'lastEntryToWords' : lastEntryToWords
        }
    }
    return render_template("forecast.html",user=current_user,dateToday=formattedDate, 
                           **context)

@views.route('/dailyusage',methods=['GET', 'POST'])
@login_required
def dailyusage():
    allRecipe = Recipe.query.all()
    distinctRecipe = db.session.query(Recipe.recipeName).distinct().all()
    allUsedMenu = dailyUsedMenuItem.query.all()

    if request.method == 'POST':
        if request.form['action'] == 'addAll':
            form_data = {}
            has_empty_field = False 

            for dailyList in distinctRecipe:
                recipeItem = dailyList.recipeName
                quantity = request.form.get(recipeItem)
                date = request.form.get('currentDate')
                #date_object = datetime.strptime(date, "%B %d, %Y")
                #formatted_date = date_object.strftime("%Y-%m-%d")
                


                form_data[recipeItem] = quantity
                if quantity is not None and quantity != '':
                    date_object = datetime.strptime(date, "%B %d, %Y").date()
                    
                    #if addInv is None:
                        #addInv = 0

                    inventory = dailyUsedMenuItem(
                        recipeItem=recipeItem,
                        quantity=int(quantity),
                        date=date_object,
                        user_id=current_user.id,
                        postedBy=current_user.first_name + " " + current_user.last_name
                    )
                    db.session.add(inventory)
                else:
                    has_empty_field = True

            if has_empty_field:
                flash('One or more fields are empty', category='error')
            else:
                db.session.commit()
                flash('Logged Daily Inventory', category='success')
                return redirect(url_for('views.dailyusage'))
        #if request.form['action'] == 'deleteAll':
            #db.session.query(dailyUsedMenuItem).delete()
            #db.session.commit()
            #flash('Deleted Daily Inventory', category='success')
            #return redirect(url_for('views.dailyusage'))
    
        if request.form['action'] == 'checkOrdered':
            date = request.form.get('checkOrdered')
            date_obj = datetime.strptime(date, "%Y-%m-%d").date()
            chosenDate = date_obj.strftime("%B %d, %Y")

            if date == "":
                flash('No data on that date', category='error')
            elif date_obj > dateToday:
                flash('Date selected cannot be in the future',category='error')
            else:
                dateCheck = dailyUsedMenuItem.query.filter(dailyUsedMenuItem.date == 
                            date).first()
                if dateCheck:
                    #selectedDate = datetime.strptime(date, '%Y-%m-%d').date()
                    #previousDate = selectedDate - timedelta(days=1)

                    filteredDate = dailyUsedMenuItem.query.filter_by(date=date).all()
                    #filteredDate2 = Inventory.query.filter_by(date=previousDate).all()
                    postedBy = filteredDate[0].postedBy

                    hasEditDate = dailyUsedMenuItem.query.filter_by(date=date).filter(dailyUsedMenuItem.editDate.isnot(None)).first()
                    editDate= False
                    editedBy= False
                    editAuth= False

                    if hasEditDate is not None:
                        editDate= hasEditDate.editDate
                        editedBy= hasEditDate.editedBy
                        editAuth= hasEditDate.authBy
                    else:
                        editDate=False
                    return render_template("dailyusage.html", user=current_user, dateToday=formattedDate,
                                    checkInv=filteredDate, editedBy=editedBy,
                                    date=date_obj, dateWords=chosenDate,
                                    editDate=editDate, editAuth=editAuth,
                                    postedBy=postedBy)            
                else:
                    
                    distinctRecipe = db.session.query(Recipe.recipeName).distinct().all()
                           
                    return render_template("dailyusage.html", user=current_user, dateToday=formattedDate,
                                    dailyList=distinctRecipe, date=chosenDate,
                                    allRecipe=allRecipe
                                    )        
        if request.form['action'] == 'authSupervisor1':
            user_name = request.form.get('authName')
            password = request.form.get('authPass')
            selectedDate = request.form.get('currentDate')
            date_obj = datetime.strptime(selectedDate, "%Y-%m-%d").date()
            selectedDateWords = date_obj.strftime("%B %d, %Y")
            
            authUser = User.query.filter_by(user_name=user_name).first()
            if authUser:
                if authUser.position == "Clerk":
                    flash('User not authorized',category='error')
                else:
                    if check_password_hash(authUser.password, password):
                        flash('Authorization successful!',category='success')
                        editFilteredDate = dailyUsedMenuItem.query.filter_by(date=selectedDate).order_by(dailyUsedMenuItem.recipeItem).all()
                        authBy = authUser.first_name + " " + authUser.last_name

                        return render_template("dailyusage.html",editFilteredDate=editFilteredDate,
                                               authBy=authBy, editCurrentDate=selectedDate,
                                               selectedDateWords=selectedDateWords,
                                               user=current_user,dateToday=formattedDate,)
                    else:
                        flash('Incorrect password',category='error')
            else:
                flash('Username is invalid',category='error')
        #edit daily usage
        if request.form['action'] == 'editDailyUsage':
            dateEdit = request.form.get('dateToEdit')
            authorizedBy = request.form.get('authUser')

            editFilteredDate = dailyUsedMenuItem.query.filter_by(date=dateEdit).all()
            #form_data = {}
            has_empty_field = False

            for editItems in editFilteredDate:
                recipe_name = editItems.recipeItem
                quantity = request.form.get('add'+ recipe_name)

                #form_data[ingredient_name] = quantity
                if quantity is not None and quantity != '':                    
                        editItems.quantity=int(quantity)
                        editItems.editedBy=current_user.first_name + " " + current_user.last_name
                        editItems.authBy=authorizedBy
                        editItems.editDate=datetime.now().date()                    
                else:
                    has_empty_field = True

            if has_empty_field:
                flash('One or more fields are empty', category='error')
            else:
                db.session.commit()
                flash('Logged Daily Usage', category='success')
                return redirect(url_for('views.dailyusage'))
        if request.form['action'] == 'checkDateRange':
            fromDate = request.form.get('checkInventoryFrom')
            toDate = request.form.get('checkInventoryTo')
            date_objFrom = datetime.strptime(fromDate, "%Y-%m-%d").date()
            date_objTo = datetime.strptime(toDate, "%Y-%m-%d").date()
            fromDateWords = date_objFrom.strftime("%B %d, %Y")
            toDateWords = date_objTo.strftime("%B %d, %Y")

            if date_objTo > dateToday:
                flash('Date selected cannot be in the future',category='error')
            return render_template("dailyusage.html", user=current_user, dateToday=formattedDate,
                                toDate=toDateWords,fromDate=fromDateWords)
        
        ##############
        ###TEST#######
        ##############
        #if request.form['action'] == 'importCSV':
            #flash('Import Success',category='success')
            #return render_template("")

        #if request.form['action'] == 'exportCSV':
            #flash('Export Success',category='success')
            #redirect(url_for('views.export'))
        ###############
        ######END######
        ###############
    if request.method == 'GET':
        date = request.args.get('date')
        distinctRecipe = db.session.query(Recipe.recipeName).distinct().all()

        if date:
            return render_template("dailyusage.html", user=current_user, dateToday=formattedDate,
                                date=date, allRecipe=allRecipe, 
                                dailyList=distinctRecipe)  
              
    return render_template("dailyusage.html",user=current_user, dateToday=formattedDate,
                           allRecipe=allRecipe,distinctRecipe=distinctRecipe)

@views.route('/recipecreate', methods=['GET','POST'])
@login_required
def recipecreate():
    allowed_positions = ['admin', 'Manager', 'Supervisor' ]

    if current_user.position not in allowed_positions:
        flash('You are not authorized to access this page.', category='error')
        return redirect(url_for('views.home'))
    
    allIngredients = Ingredients.query.order_by(Ingredients.ingredientName).all()
    allRecipes =  Recipe.query.all()
    distinctRecipe = db.session.query(Recipe.recipeName).distinct().all()

    tempIngredients = TempIngredients.query.all()
    
    recipeListSelection = request.form.get('recipeListSelect')
    filteredRecipeName = Recipe.query.filter_by(recipeName=recipeListSelection).all()

    
    if request.method == 'POST':
        if request.form['action'] == 'addTemp':
            ingredientName = request.form.get('ingredientListSelect')
            ingredientQuantity = request.form.get('ingredientsQuantity')
            ingredientUOM = request.form.get('ingredientsUOM')


            currentIng = TempIngredients.query.filter_by(recipeIngredients=ingredientName).first()

            if currentIng:
                flash('Ingredient already in list', category='error')
            elif len(ingredientQuantity) < 1:
                flash('Input Quantity',category='error')
            else:
                new_ingredient = TempIngredients(recipeIngredients=ingredientName, recipeQuantity=ingredientQuantity,recipeUOM=ingredientUOM)
                db.session.add(new_ingredient)
                db.session.commit()
                flash('Ingredient added to current ingredient list', category='success')
                return redirect(url_for('views.recipecreate'))
        if request.form['action'] == 'addRecipe':
            recipeName = request.form.get('recipeName')
            numberOfServings = request.form.get('numberOfServings',type=int)

            allTempIng = TempIngredients.query.all()
            nameCheck = Recipe.query.filter(func.lower(Recipe.recipeName) == 
                        func.lower(recipeName)).first()

            if nameCheck:
                flash('Recipe already exists',category='error')
            elif len(recipeName) < 1:
                flash('Please input recipe name', category="error")
            elif not numberOfServings:
                flash('Please input number', category="error")
            else:
                for allTempIng in allTempIng:
                    newRecipe = Recipe(recipeName=recipeName, numberOfServings=numberOfServings,
                                    ingredients=allTempIng.recipeIngredients,quantity=allTempIng.recipeQuantity,
                                    unitOfMeasure=allTempIng.recipeUOM)
                    db.session.add(newRecipe)
                    db.session.query(TempIngredients).delete()
                    db.session.commit()
                flash('Recipe added', category='success')
            
            return redirect(url_for('views.recipecreate'))
        if request.form['action'] == 'removeAll':
            db.session.query(TempIngredients).delete()
            db.session.commit()
            return redirect(url_for('views.recipecreate'))
        
        if request.form['action'] == 'viewRecipe':            
            return render_template('recipecreate.html',user=current_user,dateToday=formattedDate,
                                   allRecipes=allRecipes,distinctRecipe=distinctRecipe,
                                   recipeName=recipeListSelection, tempIngredients=tempIngredients,
                                   filteredRecipeName=filteredRecipeName,allIngredients=allIngredients)
        if request.form['action'] == 'removeRecipe':
            for recipe in filteredRecipeName:
                db.session.delete(recipe)                
            db.session.commit()
            return redirect(url_for('views.recipecreate'))

    return render_template("recipecreate.html",user=current_user,dateToday=formattedDate,
                           allIngredients=allIngredients, allRecipes=allRecipes,
                           tempIngredients=tempIngredients,distinctRecipe=distinctRecipe)

#@views.route('/recipelist', methods=['GET','POST'])
#@login_required
#def recipelist():
    allowed_positions = ['admin', 'Manager', 'Supervisor' ]

    if current_user.position not in allowed_positions:
        flash('You are not authorized to access this page.', category='error')
        return redirect(url_for('views.home'))
    
    allRecipe = Recipe.query.all()
    distinctRecipe = db.session.query(Recipe.recipeName).distinct().all()


    if request.method == "POST":
        recipeListSelection = request.form.get('recipeListSelect')
        filteredRecipeName = Recipe.query.filter_by(recipeName=recipeListSelection).all()

        if request.form['action'] == 'viewRecipe':
            
            return render_template('recipelist.html',user=current_user,dateToday=formattedDate,
                                   allRecipe=allRecipe,distinctRecipe=distinctRecipe,
                                   recipeName=recipeListSelection, filteredRecipeName=filteredRecipeName)
        if request.form['action'] == 'removeRecipe':
            for recipe in filteredRecipeName:
                db.session.delete(recipe)                
            db.session.commit()
            return redirect(url_for('views.recipelist'))

    

    return render_template("recipelist.html",user=current_user,dateToday=formattedDate,
                           allRecipe=allRecipe,distinctRecipe=distinctRecipe)

@views.route('/editaccount',methods=['GET', 'POST'])
@login_required
def editaccount():
    if request.method == 'POST':
        old_password = request.form['oldPassword']
        new_password = request.form['newPassword']
        new_password_repeat = request.form['newPassword2']
        user_id = request.form['passUser']

        user = User.query.get(user_id)

        # Check if old password matches
        if check_password_hash(user.password, old_password):
            # Check if new password matches repeated new password
            if old_password == new_password:
                #check if old and new password is the same
                flash('Old Password and New Password should not be the same',category='error')
            else:
                if new_password == new_password_repeat:
                    # Update password
                    user.password = generate_password_hash(new_password, method='scrypt')
                    db.session.commit()
                    flash('Password updated successfully!', category='success')
                else:
                    flash('New passwords do not match!', category='error')
        else:
            flash('Old password incorrect!', category='error')

    return render_template("editaccount.html",user=current_user,dateToday=formattedDate)


#@views.route('/get_forecast_details/<recipe_name>')
#def get_forecast_details(recipe_name):
    latest_entry = db.session.query(ForecastedValues.dateToday).order_by(ForecastedValues.dateToday.desc()).first()
    if not latest_entry:
        return jsonify({'error': 'No forecast data found'}), 404

    latest_date_today = latest_entry.dateToday

    forecast_data = db.session.query(
        ForecastedValues.date,
        ForecastedValues.forecasted_quantity
    ).filter(
        ForecastedValues.recipeItem == recipe_name,
        ForecastedValues.dateToday == latest_date_today
    ).order_by(ForecastedValues.date).all()

    result = [{'date': f.date.strftime('%Y-%m-%d'), 'forecast': float(f.forecasted_quantity)} for f in forecast_data]
    return jsonify(result)

@views.route('/get_forecast_details/<recipe_name>')
def get_forecast_details(recipe_name):
    latest_entry = db.session.query(ForecastedValues.dateToday).order_by(ForecastedValues.dateToday.desc()).first()
    if not latest_entry:
        return jsonify({'error': 'No forecast data found'}), 404

    latest_date_today = latest_entry.dateToday

    # Get date range from request args
    dtFrom = datetime.strptime(request.args.get('dtFrom'), "%Y-%m-%d").date()
    dtTo = datetime.strptime(request.args.get('dtTo'), "%Y-%m-%d").date()

    # Apply filtering with 'between'
    forecast_data = db.session.query(
        ForecastedValues.date,
        ForecastedValues.forecasted_quantity
    ).filter(
        ForecastedValues.recipeItem == recipe_name,
        ForecastedValues.dateToday == latest_date_today,
        ForecastedValues.date.between(dtFrom, dtTo)  # Directly apply filtering
    ).order_by(ForecastedValues.date).all()

    result = [{'date': f.date.strftime('%Y-%m-%d'), 'forecast': float(f.forecasted_quantity)} for f in forecast_data]
    return jsonify(result)

@views.route('/get_grocery_list')
def get_grocery_list():
    dt_from = request.args.get('dt_from')
    dt_to = request.args.get('dt_to')

    try:
        date_from = datetime.strptime(dt_from, "%Y-%m-%d").date()
        date_to = datetime.strptime(dt_to, "%Y-%m-%d").date()
    except Exception:
        return jsonify({'error': 'Invalid dates'}), 400

    latest_entry = db.session.query(ForecastedValues.dateToday).order_by(ForecastedValues.dateToday.desc()).first()
    if not latest_entry:
        return jsonify([])

    latest_date_today = latest_entry.dateToday

    results = (
        db.session.query(
            Recipe.ingredients.label('ingredient'),
            func.sum(ForecastedValues.forecasted_quantity * Recipe.quantity).label('total_qty_needed'),
            Recipe.unitOfMeasure.label('unit')
        )
        .join(Recipe, ForecastedValues.recipeItem == Recipe.recipeName)
        .filter(
            ForecastedValues.dateToday == latest_date_today,
            ForecastedValues.date.between(date_from, date_to)
        )
        .group_by(Recipe.ingredients, Recipe.unitOfMeasure)
        .order_by(Recipe.ingredients)
        .all()
    )

    grocery_list = [
        {'ingredient': r.ingredient, 'total': round(r.total_qty_needed), 'unit': r.unit}
        for r in results
    ]
    return jsonify(grocery_list)

@views.route('/export')
def export():
    file_path = os.path.join(current_app.config['EXPORT_FOLDER'], 'exported_data.xlsx')
    export_db_to_excel(file_path)
    return send_file(file_path, as_attachment=True)

    # Route to upload an Excel file
@views.route('/upload', methods=['GET', 'POST'])
def upload():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file part')
            return redirect(request.url)
        file = request.files['file']
        if file.filename == '':
            flash('No selected file')
            return redirect(request.url)
        if file:
            filename = secure_filename(file.filename)
            file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            upload_excel_to_db(file_path)
            flash('File successfully uploaded and data added to the database')
            return redirect(url_for('views.upload'))

    return '''
    <!doctype html>
    <title>Upload new File</title>
    <h1>Upload new File</h1>
    <form method=post enctype=multipart/form-data>
      <input type=file name=file>
      <input type=submit value=Upload>
    </form>
    '''
@views.route('/handle_file_action', methods=['GET', 'POST'])
def handle_file_action():
    if request.method == 'POST':
        # Handle the import action
        if request.form['action'] == 'importCSV':
            file = request.files.get('file')
            if file:
                filename = secure_filename(file.filename)
                file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
                file.save(file_path)
                upload_excel_to_db(file_path)
                flash('Import Success', category='success')
            else:
                flash('No file selected for import', category='error')
            return redirect(url_for('views.handle_file_action'))

        # Handle the export action
        elif request.form['action'] == 'exportCSV':
            file_path = os.path.join(current_app.config['EXPORT_FOLDER'], 'exported_data.xlsx')
            export_db_to_excel(file_path)
            flash('Export Success', category='success')
            return send_file(file_path, as_attachment=True)

    # Render a template with the buttons if it's a GET request
    return redirect(url_for("views.dailyusage"))  # Replace with your actual template name