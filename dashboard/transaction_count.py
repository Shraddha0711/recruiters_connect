# transaction_api.py
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import firebase_admin
from firebase_admin import credentials, firestore
from dateutil.relativedelta import relativedelta
import pandas as pd
from enum import Enum
import os
from dotenv import load_dotenv  
load_dotenv()

# Initialize FastAPI
app = FastAPI(title="Transaction Dashboard API", description="API for transaction time series data")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Firebase
# Replace with your Firebase service account credentials path
cred = credentials.Certificate(os.getenv("CRED_PATH"))
firebase_admin.initialize_app(cred)
db = firestore.client()

class TimeRange(str, Enum):
    one_day = "1d"
    seven_days = "7d"
    one_month = "1m"
    three_months = "3m"
    six_months = "6m"
    one_year = "1y"
    two_years = "2y"
    five_years = "5y"
    custom = "custom"

class Frequency(str, Enum):
    hourly = "hourly"
    daily = "daily"
    weekly = "weekly"
    monthly = "monthly"
    quarterly = "quarterly"
    yearly = "yearly"

def get_date_range(time_range: str, start_date: Optional[str] = None, end_date: Optional[str] = None):
    """Generate start and end dates based on selected time range or custom range."""
    today = datetime.now()
    
    if time_range == TimeRange.custom and start_date and end_date:
        try:
            start = datetime.strptime(start_date, "%Y-%m-%d")
            end = datetime.strptime(end_date, "%Y-%m-%d")
            return start, end
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    
    if time_range == TimeRange.one_day:
        return today - timedelta(days=1), today
    elif time_range == TimeRange.seven_days:
        return today - timedelta(days=7), today
    elif time_range == TimeRange.one_month:
        return today - relativedelta(months=1), today
    elif time_range == TimeRange.three_months:
        return today - relativedelta(months=3), today
    elif time_range == TimeRange.six_months:
        return today - relativedelta(months=6), today
    elif time_range == TimeRange.one_year:
        return today - relativedelta(years=1), today
    elif time_range == TimeRange.two_years:
        return today - relativedelta(years=2), today
    elif time_range == TimeRange.five_years:
        return today - relativedelta(years=5), today
    else:
        raise HTTPException(status_code=400, detail="Invalid time range")

def determine_frequency(start_date: datetime, end_date: datetime, frequency: Optional[str] = None):
    """Determine appropriate frequency based on date range if not specified."""
    if frequency:
        return frequency
    
    delta = (end_date - start_date).days
    
    if delta <= 1:
        return Frequency.hourly
    elif delta <= 14:
        return Frequency.daily
    elif delta <= 90:
        return Frequency.weekly
    elif delta <= 730:
        return Frequency.monthly
    elif delta <= 1825:
        return Frequency.quarterly
    else:
        return Frequency.yearly

def fetch_transactions_data(
    start_date: datetime, 
    end_date: datetime
):
    """Fetch transaction data from Firebase Firestore within a date range."""
    # Using 'transactions' collection with a 'timestamp' field
    transactions_ref = db.collection('transactions')
    
    # Query with date range
    query = transactions_ref.where('timestamp', '>=', start_date).where('timestamp', '<=', end_date)
    
    # Execute query
    docs = query.stream()
    
    # Convert to DataFrame for easier aggregation
    records = []
    for doc in docs:
        data = doc.to_dict()
        records.append({
            'id': doc.id,
            'timestamp': data.get('timestamp').timestamp() if isinstance(data.get('timestamp'), datetime) else data.get('timestamp'),
            # Add any other fields you might want to use later
        })
    
    df = pd.DataFrame(records)
    return df

def aggregate_transaction_data(df: pd.DataFrame, start_date: datetime, end_date: datetime, frequency: str):
    """Aggregate transaction data based on the specified frequency."""
    if df.empty:
        return []
    
    # Convert timestamp to datetime
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
    
    # Set up time bins based on frequency
    if frequency == Frequency.hourly:
        df['time_bin'] = df['timestamp'].dt.floor('H')
        date_range = pd.date_range(start=start_date.replace(minute=0, second=0, microsecond=0), 
                                  end=end_date.replace(minute=0, second=0, microsecond=0), 
                                  freq='H')
        format_str = '%Y-%m-%d %H:00'
        
    elif frequency == Frequency.daily:
        df['time_bin'] = df['timestamp'].dt.floor('D')
        date_range = pd.date_range(start=start_date.replace(hour=0, minute=0, second=0, microsecond=0), 
                                  end=end_date.replace(hour=0, minute=0, second=0, microsecond=0), 
                                  freq='D')
        format_str = '%Y-%m-%d'
        
    elif frequency == Frequency.weekly:
        df['time_bin'] = df['timestamp'].dt.to_period('W').dt.start_time
        date_range = pd.date_range(start=start_date.replace(hour=0, minute=0, second=0, microsecond=0), 
                                  end=end_date.replace(hour=0, minute=0, second=0, microsecond=0), 
                                  freq='W-MON')
        format_str = '%Y-%m-%d'
        
    elif frequency == Frequency.monthly:
        df['time_bin'] = df['timestamp'].dt.to_period('M').dt.start_time
        date_range = pd.date_range(start=start_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0), 
                                  end=end_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0), 
                                  freq='MS')
        format_str = '%Y-%m'
        
    elif frequency == Frequency.quarterly:
        df['time_bin'] = df['timestamp'].dt.to_period('Q').dt.start_time
        date_range = pd.date_range(start=start_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0), 
                                  end=end_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0), 
                                  freq='QS')
        format_str = '%Y-Q%q'
        
    else:  # yearly
        df['time_bin'] = df['timestamp'].dt.to_period('Y').dt.start_time
        date_range = pd.date_range(start=start_date.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0), 
                                  end=end_date.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0), 
                                  freq='YS')
        format_str = '%Y'

    # Count transactions per time bin
    counts = df.groupby('time_bin').size().reset_index(name='count')
    counts_dict = dict(zip(counts['time_bin'], counts['count']))
    
    # Create full date range with zeros for missing dates
    result = []
    for date in date_range:
        period_start = date
        
        # For weekly, we want the week ending date too
        if frequency == Frequency.weekly:
            period_end = date + timedelta(days=6)
            label = f"{period_start.strftime('%Y-%m-%d')} to {period_end.strftime('%Y-%m-%d')}"
        elif frequency == Frequency.monthly:
            label = period_start.strftime('%b %Y')
        elif frequency == Frequency.quarterly:
            quarter = (period_start.month - 1) // 3 + 1
            label = f"Q{quarter} {period_start.year}"
        elif frequency == Frequency.yearly:
            label = str(period_start.year)
        else:
            label = period_start.strftime(format_str)
            
        result.append({
            'period': label,
            'count': counts_dict.get(period_start, 0),
            'timestamp': period_start.timestamp()
        })
    
    return result

@app.get("/transactions/time-series")
async def get_transactions_time_series(
    time_range: TimeRange = TimeRange.seven_days,
    frequency: Optional[Frequency] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
):
    """
    Get time series data for transactions with customizable time range.
    
    - **time_range**: Predefined time range (1d, 7d, 1m, 3m, 6m, 1y, 2y, 5y, or custom)
    - **frequency**: Data aggregation frequency (hourly, daily, weekly, monthly, quarterly, yearly)
    - **start_date**: Required for custom time range (format: YYYY-MM-DD)
    - **end_date**: Required for custom time range (format: YYYY-MM-DD)
    """
    try:
        # Get date range
        start, end = get_date_range(time_range, start_date, end_date)
        
        # Determine appropriate frequency if not specified
        freq = determine_frequency(start, end, frequency)
        
        # Fetch transaction data from Firebase
        df = fetch_transactions_data(start, end)
        
        # Aggregate data
        time_series_data = aggregate_transaction_data(df, start, end, freq)
        
        # Prepare response metadata
        active_filters = {
            "time_range": time_range,
            "frequency": freq,
            "start_date": start.strftime("%Y-%m-%d"),
            "end_date": end.strftime("%Y-%m-%d")
        }
        
        return {
            "filters": active_filters,
            "data_points": len(time_series_data),
            "total_transactions": int(df['id'].count()) if not df.empty else 0,
            "data": time_series_data
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)