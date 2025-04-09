import pandas as pd
from statsmodels.tsa.statespace.sarimax import SARIMAX
import plotly.express as px
from . import db
from .models import dailyUsedMenuItem, ForecastedValues
import pickle
import os
from datetime import datetime

# Define the folder for saving the models
MODEL_FOLDER = 'models/'

# Ensure the folder exists (creates it if it doesn’t)
os.makedirs(MODEL_FOLDER, exist_ok=True)

file_path = 'last_run_info.txt'

def create_notepad_with_date(file_path):
    # Write the current date and time inside a Notepad (text) file
    with open(file_path, 'w') as file:
        current_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        file.write(f"Created on: {current_date}")
    #print(f"Notepad file created at {file_path} with date written inside.")

def get_file_modification_date(file_path):
    if os.path.exists(file_path):
        # Get the last modified time of the specified file
        timestamp = os.path.getmtime(file_path)
        # Convert it to a readable format with only month, day, and year
        mod_date = datetime.fromtimestamp(timestamp).strftime("%b %d %Y")
        return mod_date
    else:
        return None

def get_unique_recipe_items():
    # Query to get all unique recipeItem values
    unique_items = db.session.query(dailyUsedMenuItem.recipeItem).distinct().all()
    return [item[0] for item in unique_items]

def get_data_for_item(recipe_item):
    query = '''
    SELECT date, quantity
    FROM daily_used_menu_item
    WHERE recipeItem = :recipe_item
    ORDER BY date
    '''
    # Load data into a DataFrame
    df = pd.read_sql(query, db.engine, params={'recipe_item': recipe_item})
    
    # Ensure 'date' column is in datetime format and set it as the index
    df['date'] = pd.to_datetime(df['date'])
    
     # Remove any duplicate dates, keeping the first entry
    df = df.drop_duplicates(subset='date', keep='first')

    # Set the date column as the index
    df.set_index('date', inplace=True)
    
    # Set frequency to daily ('D'); adjust if data frequency is different (e.g., 'M' for monthly)
    df = df.asfreq('D')  
    
    # Fill or interpolate any missing values
    df['quantity'] = df['quantity'].interpolate(method='linear')  # Or use df['quantity'].fillna(method='ffill')

    # Drop any remaining NaNs after interpolation/filling if necessary
    df = df.dropna(subset=['quantity'])

    return df

def train_sarima_for_item(data):
    # Example SARIMA parameters, adjust as needed
    model = SARIMAX(data['quantity'], order=(1, 1, 1), seasonal_order=(1, 1, 1, 12))
    model_fit = model.fit(disp=False)
    return model_fit

def train_sarima_for_all_items():
    recipe_items = get_unique_recipe_items()
    models = {}
    
    for item in recipe_items:
        data = get_data_for_item(item)
        if not data.empty:
            model = train_sarima_for_item(data)
            models[item] = model
            # Optionally, save the model to a file and folder
            model_path = os.path.join(MODEL_FOLDER, f'{item}_sarima_model.pkl')
            with open(model_path, 'wb') as f:
                pickle.dump(model, f)
    create_notepad_with_date(file_path)
    return models

def load_all_sarima_models():
    models = {}

    # Check if the model folder exists
    if not os.path.exists(MODEL_FOLDER):
        print(f"Model folder '{MODEL_FOLDER}' does not exist.")
        return models
    
    # Iterate through all files in the model folder
    for filename in os.listdir(MODEL_FOLDER):
        if filename.endswith(".pkl"):  # Check if it's a pickle file
            model_path = os.path.join(MODEL_FOLDER, filename)
            try:
                with open(model_path, 'rb') as file:
                    model = pickle.load(file)
                    item_name = filename.replace('_sarima_model.pkl', '')  # Extract item name from filename
                    models[item_name] = model
            except Exception as e:
                print(f"Error loading {filename}: {e}")
    
    return models

def make_predictions(model_fit, steps):
    predictions = model_fit.get_forecast(steps=steps)
    pred_df = predictions.summary_frame()
    return pred_df

def make_predictions_for_all_items(models, steps):
    all_predictions = {}
    for item, model in models.items():
        pred_df = make_predictions(model, steps=steps)
        all_predictions[item] = pred_df
        save_predictions_to_db(item, pred_df)
    return all_predictions

def save_predictions_to_db(item, pred_df):
    # Ensure the 'date' column is in datetime format
    pred_df.index = pd.to_datetime(pred_df.index)
    
    for date, row in pred_df.iterrows():
        forecast_entry = ForecastedValues(
            recipeItem=item,
            date=date,
            forecasted_quantity=row['mean'],
            mean_se=row['mean_se'],
            ci_lower=row['mean_ci_lower'],
            ci_upper=row['mean_ci_upper'],
            actual_quantity=None  # Leave this as None initially
        )
        db.session.add(forecast_entry)
    
    # Commit the session to save all entries
    db.session.commit()

def update_actual_values(item, actual_data):
    for date, actual_quantity in actual_data.items():
        forecast = ForecastedValues.query.filter_by(recipeItem=item, date=date).first()
        if forecast:
            forecast.actual_quantity = actual_quantity
            db.session.commit()

def load_predictions_for_comparison(item):
    forecasts = ForecastedValues.query.filter_by(recipeItem=item).all()
    pred_df = pd.DataFrame([(f.date, f.forecasted_quantity, f.actual_quantity) for f in forecasts],
                           columns=['date', 'forecasted_quantity', 'actual_quantity'])
    pred_df.set_index('date', inplace=True)
    return pred_df

def create_plot(df, pred_df):
    plot_df = pd.concat([df, pred_df[['mean']]], axis=0)
    fig = px.line(plot_df, y=['quantity', 'mean'], title='SARIMA Predictions', labels={'mean': 'Predicted'})
    return fig.to_html()

# Example usage
# Train SARIMA models for all items
#all_models = train_sarima_for_all_items()

# Make predictions for all items and save them
#all_predictions = make_predictions_for_all_items(all_models, steps=12)

# Example of how to update actual values (if available)
# actual_data = {'2024-09-10': 14.5, '2024-09-11': 16.2}
# update_actual_values('Fish Fillet', actual_data)

# Example of how to plot forecast vs actual for a specific item
def plot_forecast_vs_actual(item):
    pred_df = load_predictions_for_comparison(item)
    actual_data = get_data_for_item(item)  # Actual data to plot
    fig = create_plot(actual_data, pred_df)
    return fig

# Example usage:
# fig_html = plot_forecast_vs_actual('Fish Fillet')
# Display `fig_html` in your Flask template or save to a file
