import requests
import pandas as pd
from datetime import datetime, timezone
import json
import re
import pytz
from dotenv import load_dotenv
from supabase import create_client, Client
from langsmith import traceable
import os

# Load environment variables from .env file
load_dotenv()

# Your Supabase API URL and key
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_API_KEY = os.getenv('SUPABASE_API_KEY')
SUPABASE_DB = os.getenv('SUPABASE_DB')
SUPABASE_DB_MANALYSIS = os.getenv('SUPABASE_DB_MANALYSIS')

#Function to insert data into Supabase mood logs table
@traceable
def insert_data_to_supabase(data):
    url = f"{SUPABASE_URL}/rest/v1/{SUPABASE_DB}"
    
    headers = {
        "apikey": SUPABASE_API_KEY,
        "Authorization": f"Bearer {SUPABASE_API_KEY}",
        "Content-Type": "application/json"
    }

    # Use the user's timezone to get the current time
    user_timezone = data.get('timezone')
    try:
        user_tz = pytz.timezone(user_timezone)
        current_time = datetime.now(timezone.utc).astimezone(user_tz).strftime('%m/%d/%Y %H:%M')
    except Exception as e:
        # Log the error for debugging
        print(f"An error occurred: {e}")
        # Fallback to just set timezone as UTC 
        user_tz = pytz.timezone('UTC')
        current_time = datetime.now(timezone.utc).astimezone(user_tz).strftime('%m/%d/%Y %H:%M')

    # Prepare data for insertion
    data_to_insert = {
        "date": current_time,
        "mood": data['mood'],
        "description": data['description'],
        "timezone": data['timezone'],
        "user_uuid": data['user_uuid']
    }

    # Insert into Supabase
    response = requests.post(url, headers=headers, data=json.dumps(data_to_insert))

    if response.status_code == 201:
        print("Data inserted successfully!")
        return True
    else:
        print(f"Failed to insert data: {response.status_code}, {response.text}")
        return False

#Function to insert the mood analysis data into Supabase memory table
@traceable
def insert_manalysis_to_supabase(data, user_uuid):
    
    url = f"{SUPABASE_URL}/rest/v1/{SUPABASE_DB_MANALYSIS}"
    
    headers = {
        "apikey": SUPABASE_API_KEY,
        "Authorization": f"Bearer {SUPABASE_API_KEY}",
        "Content-Type": "application/json"
    }
    
    for category, records in data.items():
        record_date = data["date"]
        if category == "date": continue  # Skip the date field
        for record in records:
            try:
                data_to_insert = {
                    "date": record_date,
                    "category": category,
                    "sub_category": record["sub_category"],
                    "impact": record["impact"],
                    "description": record["description"],
                    "user_uuid": user_uuid
                }
                
                #Insert into the database
                response = requests.post(url, headers=headers, data=json.dumps(data_to_insert))
                if response.status_code == 201:
                    print(f"Inserted: {data_to_insert}")
                else:
                    print(f"Failed to insert: {response.status_code}, {response.text}")
            except KeyError as  e:
                print(f"Missing key {e} in record: {record}. Skipping.")



#Function to extract mood entries from database
@traceable
def mood_data(period, user_uuid):
    # Initialize the Supabase client
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_API_KEY)
    
    # Fetch data from the "mood_entries" table for the specific user
    response = supabase.table(SUPABASE_DB).select('id, date, mood, description').eq('user_uuid', user_uuid).execute()
    
    # Extract the data
    data = response.data
    
    # Convert the data to a pandas DataFrame
    df = pd.DataFrame(data)
    
    # Turn the date column to the pandas Timestamp 
    df['date'] = pd.to_datetime(df['date'])

    # Convert the current date to a pandas Timestamp
    current_date = pd.to_datetime(datetime.today().date())
    
    if period == 'weekly':
        # Find the most recent Monday before or on the current date
        last_monday = current_date - pd.Timedelta(days=current_date.weekday())
        
        # Find the start of the last full week (7 days before last_monday)
        start_of_last_full_week = last_monday - pd.Timedelta(weeks=1)
        
        # End of the last full week at 23:59:59
        end_of_last_full_week = (start_of_last_full_week + pd.Timedelta(days=6)).replace(hour=23, minute=59, second=59)
        
        # Filter the dataframe to get the dates within the last full week
        mood_data = df[(df['date'] >= pd.to_datetime(start_of_last_full_week)) & (df['date'] <= pd.to_datetime(end_of_last_full_week))].iloc[:,1:]

    elif period == 'daily':
        # Find the most recent full day (yesterday)
        start_of_last_day = current_date - pd.Timedelta(days=1)
        
        # End of the last day at 23:59:59
        end_of_last_day = start_of_last_day.replace(hour=23, minute=59, second=59)
        
        # Filter the dataframe to get the dates within the last full day
        mood_data = df[(df['date'] >= pd.to_datetime(start_of_last_day)) & (df['date'] <= pd.to_datetime(end_of_last_day))].iloc[:,1:]

    # Convert the DataFrame to a CSV string
    csv_string = mood_data.to_csv(index=False)
    
    return csv_string


# Function to extract mood analysis historical data from the database
@traceable
def fetch_mood_analysis_historical(user_uuid, period='all'):
    # Initialize the Supabase client
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_API_KEY)
    
    # Query the "mood_analysis" table for the user's historical data
    response = supabase.table(SUPABASE_DB_MANALYSIS)\
        .select('id','date, category, sub_category, impact, description')\
        .eq('user_uuid', user_uuid)\
        .execute()
    
    # Extract the data
    data = response.data
    
    # Convert the data to a pandas DataFrame
    df = pd.DataFrame(data)
    
    if df.empty:
        print("No data found.")
        return df

    # Convert the 'date' column to datetime
    df['date'] = pd.to_datetime(df['date']).dt.normalize()

    if period == 'daily':
        # Filter the DataFrame for the previous day
        yesterday = pd.Timestamp.now().normalize() - pd.Timedelta(days=1)
        df = df[df['date'] == yesterday]
    
    elif period == 'weekly':
        # Find the start and end dates for the most recent full week (Monday to Sunday)
        current_date = pd.Timestamp.now().normalize()
        last_monday = current_date - pd.Timedelta(days=current_date.weekday())
        start_of_last_full_week = last_monday - pd.Timedelta(weeks=1)
        end_of_last_full_week = start_of_last_full_week + pd.Timedelta(days=6)
        
        # Filter the DataFrame for the last full week
        df = df[(df['date'] >= start_of_last_full_week) & (df['date'] <= end_of_last_full_week)]
    
    # Sort the DataFrame by the 'date' column
    df = df.sort_values(by='date').reset_index(drop=True)
    
    print(f"Number of historical rows fetched: {len(df)}")
    return df

# Delete mood analysis data from supabase
@traceable
def delete_manalysis_rows_from_supabase(user_uuid, ids_to_delete=None, trim=False):
    # Initialize the Supabase client
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_API_KEY)
    
    # Delete rows by ID if provided
    if ids_to_delete:
        for id_to_delete in ids_to_delete:
            response = supabase.table(SUPABASE_DB_MANALYSIS) \
                .delete() \
                .eq("id", id_to_delete) \
                .eq("user_uuid", user_uuid) \
                .execute()
            
            print(f"Deleted row ID: {id_to_delete}")


    # Trim rows if requested
    if trim:
        # Fetch all rows for the user
        response = supabase.table(SUPABASE_DB_MANALYSIS) \
            .select("id, date, category, sub_category, impact, description") \
            .eq('user_uuid', user_uuid) \
            .execute()

        df_md = pd.DataFrame(response.data)

        # If there are no rows, nothing to trim
        if df_md.empty:
            print("No rows to trim.")
            return

        # Normalize and sort rows by date
        df_md['date'] = pd.to_datetime(df_md['date']).dt.normalize()
        df_md = df_md.sort_values(by='date').reset_index(drop=True)

        # Check row count
        row_count = len(df_md)
        print(f"Current number of rows: {row_count}")

        # If rows exceed 100, trim the earliest rows
        if row_count > 100:
            rows_to_delete = row_count - 100
            ids_to_trim = df_md.head(rows_to_delete)['id'].tolist()

            for id_to_trim in ids_to_trim:
                response = supabase.table(SUPABASE_DB_MANALYSIS) \
                    .delete() \
                    .eq("id", id_to_trim) \
                    .eq("user_uuid", user_uuid) \
                    .execute()
                
                print(f"Trimmed row ID: {id_to_trim}")


            print(f"Deleted {rows_to_delete} oldest rows to maintain 100 rows.")
        else:
            print("No trimming required. Row count is within limit.")


# Example usage:
# weekly_data = mood_data('weekly')
# daily_data = mood_data('daily')