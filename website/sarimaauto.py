import pandas as pd
from pmdarima import auto_arima
from .models import Recipe, dailyUsedMenuItem, ForecastedValues
from sqlalchemy import func, and_
from . import db
from concurrent.futures import ThreadPoolExecutor
import warnings
from flask import current_app
from datetime import timedelta, datetime
import os
import pickle
from statsmodels.tsa.statespace.sarimax import SARIMAX
from pathlib import Path

def _save_sarima_model(model, recipe_name: str):

    os.makedirs("sarima_models", exist_ok=True)
    
    model_info = {
        'timestamp': datetime.now().date(),  # Single date serves both purposes
        'recipe': recipe_name,
        'order': model.order,
        'seasonal_order': model.seasonal_order,
        'aic': model.aic(),
        'model_summary': str(model.summary())  # Contains training dates in text
    }
    
    safe_name = "".join(c if c.isalnum() else "_" for c in recipe_name)
    with open(f"sarima_models/{safe_name}.pkl", 'wb') as f:
        pickle.dump(model_info, f)

def checkForecastDates(date_from, date_to):
    # Generate the list of dates from date_from to date_to
    date_range = [date_from + timedelta(days=i) for i in range((date_to - date_from).days + 1)]

    # Query ForecastedValues for dates between date_from and date_to
    forecasted_dates = db.session.query(ForecastedValues.date).filter(
        ForecastedValues.date.between(date_from, date_to)
    ).all()

    # Extract the dates from the query result
    forecasted_dates = [entry.date for entry in forecasted_dates]

    # Compare if all dates from the range are present in forecasted_dates
    missing_dates = [date for date in date_range if date not in forecasted_dates]

    if missing_dates:
        return False
    else:
        return True

def get_sarima_orders(recipe_name: str) -> dict:
    """
    Retrieves saved SARIMA parameters with consistent naming.
    
    Args:
        recipe_name: Name of the recipe (e.g. "Chicken Curry")
    
    Returns:
        {
            'order': (p, d, q),
            'seasonal_order': (P, D, Q, m),
            'last_saved': datetime.date,
            'aic': float
        }
    
    Raises:
        FileNotFoundError: If no model exists for this recipe
    """
    from pathlib import Path
    
    safe_name = "".join(c if c.isalnum() else "_" for c in recipe_name)
    filepath = Path(f"sarima_models/{safe_name}.pkl")
    
    if not filepath.exists():
        raise FileNotFoundError(f"No saved model for '{recipe_name}'")
    
    with open(filepath, 'rb') as f:
        data = pickle.load(f)
    
    return {
        'order': tuple(data['order']),  # (p, d, q)
        'seasonal_order': tuple(data['seasonal_order']),  # (P, D, Q, m)
        'last_saved': data['timestamp'],
        'aic': float(data['aic'])
    }

def getData(recipe_name: str):
    results = db.session.query(
        dailyUsedMenuItem.date,
        func.sum(dailyUsedMenuItem.quantity).label("total_quantity")
    ).filter(
        dailyUsedMenuItem.recipeItem == recipe_name
    ).group_by(
        dailyUsedMenuItem.date
    ).order_by(
        dailyUsedMenuItem.date
    ).all()

    # Convert to DataFrame
    df = pd.DataFrame(results, columns=['date', 'quantity'])

    return df

def forecastAutoSarima(data: pd.DataFrame, date_col: str, value_col: str, steps: int, seasonal_period: int = 12):
    """
    Forecast future values using seasonal auto_arima.

    Parameters:
    - data: pd.DataFrame containing your time series.
    - date_col: str, name of the datetime column.
    - value_col: str, name of the column to forecast.
    - steps: int, number of future periods to forecast.
    - seasonal_period: int, number of periods in a seasonal cycle (default is 12).

    Returns:
    - forecast: np.array of forecasted values
    - model: the fitted auto_arima model
    """
    # Ensure datetime index
    ts = data.copy()
    ts[date_col] = pd.to_datetime(ts[date_col])
    ts.set_index(date_col, inplace=True)
    
    series = ts[value_col]

    # Fit auto_arima model
    model = auto_arima(
        series,
        seasonal=True,
        m=seasonal_period,
        trace=True,
        error_action='ignore',
        suppress_warnings=True,
        stepwise=True
    )

    print(model.summary())

    # Predict future values
    forecast = model.predict(n_periods=steps)

    return forecast, model

def forecastAllRecipes(steps: int = 7, seasonal_period: int = 7):
    """
    Forecasts future usage for all distinct recipes and inserts into ForecastedValues table.

    Parameters:
    - steps (int): Number of future periods (days) to forecast.
    - seasonal_period (int): Seasonality period (e.g., 7 for weekly seasonality on daily data).

    Returns:
    - None
    """

    import warnings
    warnings.filterwarnings("ignore", category=FutureWarning)

    os.makedirs("sarima_models", exist_ok=True)
    
    # Write calibration date
    calib_file = Path("sarima_models/last_calibration.txt").absolute()
    calib_file.parent.mkdir(exist_ok=True)
    
    with calib_file.open('w') as f:
        f.write(datetime.now().strftime("%Y-%m-%d"))
    print(f"💾 Saved to: {calib_file}")

    # Get the latest available date from dailyUsedMenuItem
    latest_date = db.session.query(func.max(dailyUsedMenuItem.date)).scalar()
    if latest_date is None:
        print("No data in dailyUsedMenuItem.")
        return

    distinctRecipe = db.session.query(Recipe.recipeName).distinct().all()

    for allMenu in distinctRecipe:
        recipe_name = allMenu[0]

        df = getData(recipe_name)

        if not df.empty and len(df) > 10:
            try:
                forecast, model = forecastAutoSarima(
                    data=df,
                    date_col='date',
                    value_col='quantity',
                    steps=steps,
                    seasonal_period=seasonal_period
                )

                last_date = df['date'].max()
                future_dates = pd.date_range(start=last_date + pd.Timedelta(days=1), periods=steps)
                
                #pickle dump
                _save_sarima_model(model=model, recipe_name=recipe_name)

                for i in range(steps):
                    forecast_date = future_dates[i].date()

                    #Check if forecast already exists for this recipe, date, and dateToday
                    exists = db.session.query(ForecastedValues.id).filter(
                        and_(
                            ForecastedValues.recipeItem == recipe_name,
                            ForecastedValues.date == forecast_date,
                            ForecastedValues.dateToday == latest_date
                        )
                    ).first()

                    if exists:
                        continue  # Skip if already exists

                    # Create new forecast entry
                    entry = ForecastedValues(
                        recipeItem=recipe_name,
                        date=forecast_date,
                        forecasted_quantity=float(forecast[i]),
                        mean_se=0.0,      # Placeholder
                        ci_lower=0.0,     # Placeholder
                        ci_upper=0.0,     # Placeholder
                        actual_quantity=None,
                        dateToday=latest_date
                    )
                    db.session.add(entry)

            except Exception as e:
                print(f"Skipping '{recipe_name}' due to error: {e}")

    db.session.commit()
    print("Forecasting complete.")

def forecastSarima(
    data: pd.DataFrame,
    date_col: str,
    value_col: str,
    steps: int,
    order: tuple,
    seasonal_order: tuple
) -> tuple:
    """
    Manual SARIMA forecasting using explicit orders.
    
    Args:
        data: Time series DataFrame
        date_col: Name of datetime column
        value_col: Name of value column
        steps: Forecast horizon
        order: (p, d, q) non-seasonal order
        seasonal_order: (P, D, Q, m) seasonal order
    
    Returns:
        (forecast_values, fitted_model)
    """
    ts = data.copy()
    ts[date_col] = pd.to_datetime(ts[date_col])
    ts.set_index(date_col, inplace=True)
    
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        model = SARIMAX(
            ts[value_col],
            order=order,
            seasonal_order=seasonal_order,
            enforce_stationarity=False,
            enforce_invertibility=False
        ).fit(disp=False)
    
    return model.forecast(steps=steps), model

def forecastAllRecipesnotAuto(steps: int = 7):
    """
    Forecasts all recipes using saved SARIMA parameters.
    """
    latest_date = db.session.query(func.max(dailyUsedMenuItem.date)).scalar()
    if not latest_date:
        print("No historical data available")
        return

    for recipe in db.session.query(Recipe.recipeName).distinct():
        recipe_name = recipe[0]
        try:
            df = getData(recipe_name)
            if len(df) < 10:
                continue
                
            params = get_sarima_orders(recipe_name)
            
            forecast, model = forecastSarima(
                data=df,
                date_col='date',
                value_col='quantity',
                steps=steps,
                order=params['order'],
                seasonal_order=params['seasonal_order']
            )
            
            future_dates = pd.date_range(
                start=df['date'].max() + pd.Timedelta(days=1),
                periods=steps
            )
            
            for i, date in enumerate(future_dates):
                if not db.session.query(ForecastedValues).filter_by(
                    recipeItem=recipe_name,
                    date=date.date(),
                    dateToday=latest_date
                ).first():
                    
                    conf_int = model.get_forecast(steps).conf_int().iloc[i]
                    db.session.add(ForecastedValues(
                        recipeItem=recipe_name,
                        date=date.date(),
                        forecasted_quantity=float(forecast[i]),
                        mean_se=model.get_forecast(steps).se_mean[i],
                        ci_lower=float(conf_int[0]),
                        ci_upper=float(conf_int[1]),
                        actual_quantity=None,
                        dateToday=latest_date
                    ))
                    
        except Exception as e:
            print(f"Failed on {recipe_name}: {str(e)}")
            continue

    db.session.commit()
    print(f"Generated {steps}-day forecasts using saved parameters")

def getLastCalibrationDate():
    
    calib_file = Path("sarima_models/last_calibration.txt").absolute()
    
    if not calib_file.exists():
        print(f"❌ File not found at: {calib_file}")
        return None
        
    try:
        mtime = calib_file.stat().st_mtime
        return datetime.fromtimestamp(mtime).date()
    except Exception as e:
        print(f"🔥 Timestamp error: {str(e)}")
        return None
    
    
#not used
def forecast_worker(recipe_name, steps, seasonal_period, latest_date):  # 🆕 Added helper function
    with current_app.app_context():
        try:
            df = getData(recipe_name)
            if df.empty or len(df) <= 10:
                return f"Skipped '{recipe_name}' (not enough data)"

            forecast, model = forecastAutoSarima(
                data=df,
                date_col='date',
                value_col='quantity',
                steps=steps,
                seasonal_period=seasonal_period
            )

            last_date = df['date'].max()
            future_dates = pd.date_range(start=last_date + pd.Timedelta(days=1), periods=steps)

            for i in range(steps):
                forecast_date = future_dates[i].date()

                exists = db.session.query(ForecastedValues.id).filter(
                    ForecastedValues.recipeItem == recipe_name,
                    ForecastedValues.date == forecast_date,
                    ForecastedValues.dateToday == latest_date
                ).first()

                if exists:
                    continue

                entry = ForecastedValues(
                    recipeItem=recipe_name,
                    date=forecast_date,
                    forecasted_quantity=float(forecast[i]),
                    mean_se=0.0,
                    ci_lower=0.0,
                    ci_upper=0.0,
                    actual_quantity=None,
                    dateToday=latest_date
                )
                db.session.add(entry)

            db.session.commit()
            return f"✅ Forecasted: {recipe_name}"

        except Exception as e:
            return f"❌ Error on {recipe_name}: {e}"


def TestforecastAllRecipes(steps: int = 7, seasonal_period: int = 7):
    """
    Forecasts future usage for all distinct recipes and inserts into ForecastedValues table.
    """

    warnings.filterwarnings("ignore", category=FutureWarning)

    latest_date = db.session.query(func.max(dailyUsedMenuItem.date)).scalar()
    if latest_date is None:
        print("No data in dailyUsedMenuItem.")
        return

    distinctRecipe = db.session.query(Recipe.recipeName).distinct().all()
    recipe_names = [r[0] for r in distinctRecipe]  # 🔄 Changed for parallelism

    with ThreadPoolExecutor() as executor:  # 🆕 Added for parallel execution
        futures = [
            executor.submit(forecast_worker, recipe, steps, seasonal_period, latest_date)
            for recipe in recipe_names
        ]

        for future in futures:
            result = future.result()
            print(result)

    print("✅ Forecasting complete.")