
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from sqlalchemy import func
from .models import dailyUsedMenuItem,ForecastedValues
import pandas as pd
import numpy as np
import logging



from . import db

def dateToWords(date):
    difference = relativedelta(datetime.now(), date)
    if difference.years:
        return f"{difference.years} year(s) ago"
    elif difference.months:
        return f"{difference.months} month(s) ago"
    elif difference.days:
        return f"{difference.days} day(s) ago"
    else:
        return "Today"
    
def get_dates_with_no_entries(model, session):
    # Get the first date entry
    first_date_entry = session.query(func.min(model.date)).scalar()
    if not first_date_entry:
        return []

    # Get the current date
    current_date = datetime.now().date()

    # Generate a list of dates from the first date entry to the current date
    date_range = [first_date_entry + timedelta(days=i) for i in range((current_date - first_date_entry).days + 1)]

    # Query the dates that have entries in the model table
    dates_with_entries = session.query(model.date).distinct().all()
    dates_with_entries = [date[0] for date in dates_with_entries]

    # Find the dates with no entries
    dates_with_no_entries = [date.strftime("%B %d, %Y") for date in date_range if date not in dates_with_entries]

    return dates_with_no_entries

#def get_dates_with_no_entries(model, session):
    # Get the first date entry
    first_date_entry = session.query(func.min(model.date)).scalar()
    if not first_date_entry:
        return []

    # Get the current date
    current_date = datetime.now().date()

    # Generate a list of dates from the first date entry to the current date
    date_range = [first_date_entry + timedelta(days=i) for i in range((current_date - first_date_entry).days + 1)]

    # Query the dates that have entries in the model table and convert them to datetime.date
    dates_with_entries = session.query(model.date).distinct().all()
    dates_with_entries = {date[0] for date in dates_with_entries}  # Use a set for faster lookup

    # Find the dates with no entries, comparison is done with datetime.date objects
    dates_with_no_entries = [
        date for date in date_range if date not in dates_with_entries
    ]

    # Sort the list of missing dates, then format them as strings
    sorted_dates_with_no_entries = [
        date.strftime("%B %d, %Y") for date in sorted(dates_with_no_entries)
    ]

    return sorted_dates_with_no_entries

# Function to export the database to an Excel file
#def export_db_to_excel(file_path):
    records = dailyUsedMenuItem.query.all()
    data = []
    for record in records:
        data.append({
            'id': record.id,
            'recipeItem': record.recipeItem,
            'quantity': record.quantity,
            'date': record.date,
            'user_id': record.user_id,
            'postedBy': record.postedBy,
            'editedBy': record.editedBy,
            'editDate': record.editDate,
            'authBy': record.authBy
        })
    df = pd.DataFrame(data)
    df.to_excel(file_path, index=False)

def export_db_to_excel(file_path):
    records = ForecastedValues.query.all()  # Query all records from the ForecastedValues model
    data = []
    for record in records:
        data.append({
            'id': record.id,
            'recipeItem': record.recipeItem,
            'date': record.date,
            'forecasted_quantity': record.forecasted_quantity,
            'mean_se': record.mean_se,
            'ci_lower': record.ci_lower,
            'ci_upper': record.ci_upper,
            'actual_quantity': record.actual_quantity
        })
    df = pd.DataFrame(data)
    df.to_excel(file_path, index=False)

# Function to upload Excel to the database
def upload_excel_to_db(file_path):
    df = pd.read_excel(file_path)
    
    # Log the first few rows to inspect the data
    logging.debug(f"DataFrame head:\n{df.head()}")
    
    # Replace NaN with None for integer fields
    df['quantity'] = df['quantity'].replace({np.nan: None})
    df['user_id'] = df['user_id'].replace({np.nan: None})
    
    # Replace NaT (Not a Time) with None for date fields
    df['date'] = df['date'].replace({pd.NaT: None})
    df['editDate'] = df['editDate'].replace({pd.NaT: None})
    
    # Log the cleaned data
    logging.debug(f"Cleaned DataFrame head:\n{df.head()}")
    
    for _, row in df.iterrows():
        date = pd.to_datetime(row['date']).date() if 'date' in row and not pd.isna(row['date']) else None
        edit_date = pd.to_datetime(row['editDate']).date() if 'editDate' in row and not pd.isna(row['editDate']) else None
        
        # Log each row being processed
        logging.debug(f"Processing row: {row}")
        
        # Create a new record
        record = dailyUsedMenuItem(
            recipeItem=row['recipeItem'],
            quantity=row['quantity'],
            date=date,
            user_id=row['user_id'],
            postedBy=row['postedBy'],
            editedBy=row.get('editedBy'),
            editDate=edit_date,
            authBy=row.get('authBy')
        )
        
        try:
            db.session.add(record)
            db.session.commit()
        except Exception as e:
            logging.error(f"Error adding record: {e}")
            db.session.rollback()

