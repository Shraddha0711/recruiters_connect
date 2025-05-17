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
app = FastAPI(title="Admin Dashboard API", description="API for admin dashboard time series data")

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

def build_firestore_query(
    candidates_ref,
    start_date: datetime, 
    end_date: datetime,
    roles: Optional[List[str]] = None,
    city: Optional[List[str]] = None,
    min_experience: Optional[float] = None,
    max_experience: Optional[float] = None,
    min_ctc: Optional[float] = None,
    max_ctc: Optional[float] = None,
    sold: Optional[bool] = None
):
    """Build a Firestore query with all the filters applied."""
    # Start with date range filter
    query = candidates_ref.where('created_at', '>=', start_date).where('created_at', '<=', end_date)
    
    # Due to Firestore limitations, we can't apply multiple range queries on different fields
    # So we'll fetch the date-filtered data and then filter further in memory
    
    return query

def apply_additional_filters(
    df: pd.DataFrame,
    roles: Optional[List[str]] = None,
    city: Optional[List[str]] = None,
    min_experience: Optional[float] = None,
    max_experience: Optional[float] = None,
    min_ctc: Optional[float] = None,
    max_ctc: Optional[float] = None,
    sold: Optional[bool] = None
):
    """Apply additional filters to the DataFrame after fetching from Firestore."""
    if df.empty:
        return df
    
    # Filter by roles if specified
    if roles and len(roles) > 0:
        df = df[df['role'].isin(roles)]
    
    # Filter by city if specified
    if city and len(city) > 0:
        df = df[df['city'].isin(city)]
    
    # Filter by experience range if specified
    if min_experience is not None:
        df = df[df['experience'] >= min_experience]
    if max_experience is not None:
        df = df[df['experience'] <= max_experience]
    
    # Filter by CTC range if specified
    if min_ctc is not None:
        df = df[df['ctc'] >= min_ctc]
    if max_ctc is not None:
        df = df[df['ctc'] <= max_ctc]
    
    # Filter by sold status if specified
    if sold is not None:
        df = df[df['sold'] == sold]
    
    return df

def fetch_candidates_data(
    start_date: datetime, 
    end_date: datetime,
    roles: Optional[List[str]] = None,
    city: Optional[List[str]] = None,
    min_experience: Optional[float] = None,
    max_experience: Optional[float] = None,
    min_ctc: Optional[float] = None,
    max_ctc: Optional[float] = None,
    sold: Optional[bool] = None
):
    """Fetch candidate registration data from Firebase Firestore with filters."""
    # Assuming 'candidates' is your collection and it has a 'created_at' timestamp field
    candidates_ref = db.collection('candidates')
    
    # Build the initial query with date range
    query = build_firestore_query(
        candidates_ref, 
        start_date, 
        end_date,
        roles,
        city,
        min_experience,
        max_experience,
        min_ctc,
        max_ctc,
        sold
    )
    
    # Execute query
    docs = query.stream()
    
    # Convert to DataFrame for easier filtering and aggregation
    records = []
    for doc in docs:
        data = doc.to_dict()
        records.append({
            'id': doc.id,
            'created_at': data.get('created_at').timestamp() if isinstance(data.get('created_at'), datetime) else data.get('created_at'),
            'role': data.get('role', ''),
            'city': data.get('city', ''),
            'experience': data.get('experience', 0),
            'ctc': data.get('ctc', 0),
            'sold': data.get('sold', False),  # Add sold field with default value
            # Add any other relevant fields
        })
    
    df = pd.DataFrame(records)
    
    # Apply additional filters in memory
    filtered_df = apply_additional_filters(
        df,
        roles,
        city,
        min_experience,
        max_experience,
        min_ctc,
        max_ctc,
        sold
    )
    
    return filtered_df

def aggregate_data(df: pd.DataFrame, start_date: datetime, end_date: datetime, frequency: str):
    """Aggregate data based on the specified frequency."""
    if df.empty:
        return []
    
    # Convert timestamp to datetime
    df['created_at'] = pd.to_datetime(df['created_at'], unit='s')
    
    # Set up time bins based on frequency
    if frequency == Frequency.hourly:
        df['time_bin'] = df['created_at'].dt.floor('H')
        date_range = pd.date_range(start=start_date.replace(minute=0, second=0, microsecond=0), 
                                  end=end_date.replace(minute=0, second=0, microsecond=0), 
                                  freq='H')
        format_str = '%Y-%m-%d %H:00'
        
    elif frequency == Frequency.daily:
        df['time_bin'] = df['created_at'].dt.floor('D')
        date_range = pd.date_range(start=start_date.replace(hour=0, minute=0, second=0, microsecond=0), 
                                  end=end_date.replace(hour=0, minute=0, second=0, microsecond=0), 
                                  freq='D')
        format_str = '%Y-%m-%d'
        
    elif frequency == Frequency.weekly:
        df['time_bin'] = df['created_at'].dt.to_period('W').dt.start_time
        date_range = pd.date_range(start=start_date.replace(hour=0, minute=0, second=0, microsecond=0), 
                                  end=end_date.replace(hour=0, minute=0, second=0, microsecond=0), 
                                  freq='W-MON')
        format_str = '%Y-%m-%d'
        
    elif frequency == Frequency.monthly:
        df['time_bin'] = df['created_at'].dt.to_period('M').dt.start_time
        date_range = pd.date_range(start=start_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0), 
                                  end=end_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0), 
                                  freq='MS')
        format_str = '%Y-%m'
        
    elif frequency == Frequency.quarterly:
        df['time_bin'] = df['created_at'].dt.to_period('Q').dt.start_time
        date_range = pd.date_range(start=start_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0), 
                                  end=end_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0), 
                                  freq='QS')
        format_str = '%Y-Q%q'
        
    else:  # yearly
        df['time_bin'] = df['created_at'].dt.to_period('Y').dt.start_time
        date_range = pd.date_range(start=start_date.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0), 
                                  end=end_date.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0), 
                                  freq='YS')
        format_str = '%Y'

    # Count candidates per time bin
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

@app.get("/candidates/time-series")
async def get_candidates_time_series(
    time_range: TimeRange = TimeRange.seven_days,
    frequency: Optional[Frequency] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    roles: Optional[List[str]] = Query(None),
    city: Optional[List[str]] = Query(None),
    min_experience: Optional[float] = None,
    max_experience: Optional[float] = None,
    min_ctc: Optional[float] = None,
    max_ctc: Optional[float] = None,
    sold: Optional[bool] = None
):
    """
    Get time series data for candidate registrations with filtering options.
    
    - **time_range**: Predefined time range (1d, 7d, 1m, 3m, 6m, 1y, 2y, 5y, or custom)
    - **frequency**: Data aggregation frequency (hourly, daily, weekly, monthly, quarterly, yearly)
    - **start_date**: Required for custom time range (format: YYYY-MM-DD)
    - **end_date**: Required for custom time range (format: YYYY-MM-DD)
    - **roles**: Filter by one or more job roles
    - **city**: Filter by one or more city
    - **min_experience**: Filter by minimum years of experience
    - **max_experience**: Filter by maximum years of experience
    - **min_ctc**: Filter by minimum CTC (in whatever currency unit you use)
    - **max_ctc**: Filter by maximum CTC
    - **sold**: Filter by sold status (true/false)
    """
    try:
        # Get date range
        start, end = get_date_range(time_range, start_date, end_date)
        
        # Determine appropriate frequency if not specified
        freq = determine_frequency(start, end, frequency)
        
        # Fetch and filter data from Firebase
        df = fetch_candidates_data(
            start, 
            end,
            roles,
            city,
            min_experience,
            max_experience,
            min_ctc,
            max_ctc,
            sold
        )
        
        # Aggregate data
        time_series_data = aggregate_data(df, start, end, freq)
        
        # Get active filters for response metadata
        active_filters = {
            "time_range": time_range,
            "frequency": freq,
            "start_date": start.strftime("%Y-%m-%d"),
            "end_date": end.strftime("%Y-%m-%d")
        }
        
        if roles:
            active_filters["roles"] = roles
        if city:
            active_filters["city"] = city
        if min_experience is not None:
            active_filters["min_experience"] = min_experience
        if max_experience is not None:
            active_filters["max_experience"] = max_experience
        if min_ctc is not None:
            active_filters["min_ctc"] = min_ctc
        if max_ctc is not None:
            active_filters["max_ctc"] = max_ctc
        if sold is not None:
            active_filters["sold"] = sold
        
        return {
            "filters": active_filters,
            "data_points": len(time_series_data),
            "total_candidates": int(df['id'].count()) if not df.empty else 0,
            "data": time_series_data
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Add endpoint to get available filter options
@app.get("/candidates/filter-options")
async def get_filter_options():
    """Get all available options for filtering candidates."""
    try:
        candidates_ref = db.collection('candidates')
        docs = candidates_ref.stream()
        
        # Extract unique values for each filter
        roles = set()
        city = set()
        experience_values = []
        ctc_values = []
        
        for doc in docs:
            data = doc.to_dict()
            if 'role' in data and data['role']:
                roles.add(data['role'])
            if 'city' in data and data['city']:
                city.add(data['city'])
            if 'experience' in data and data['experience'] is not None:
                experience_values.append(data['experience'])
            if 'ctc' in data and data['ctc'] is not None:
                ctc_values.append(data['ctc'])
        
        # Calculate min/max ranges for numeric fields
        experience_range = {
            "min": min(experience_values) if experience_values else 0,
            "max": max(experience_values) if experience_values else 0
        }
        
        ctc_range = {
            "min": min(ctc_values) if ctc_values else 0,
            "max": max(ctc_values) if ctc_values else 0
        }
        
        return {
            "roles": sorted(list(roles)),
            "city": sorted(list(city)),
            "experience_range": experience_range,
            "ctc_range": ctc_range
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)