import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from pmdarima import auto_arima
from .models import Recipe, dailyUsedMenuItem, ForecastedValues
from sqlalchemy import func, and_
from . import db
from concurrent.futures import ThreadPoolExecutor
import warnings
from flask import current_app
from datetime import timedelta


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

                for i in range(steps):
                    forecast_date = future_dates[i].date()

                    # ✅ Check if forecast already exists for this recipe, date, and dateToday
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