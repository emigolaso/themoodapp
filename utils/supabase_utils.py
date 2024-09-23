import requests
import pandas as pd
from datetime import datetime, timezone
import json
import re
from dotenv import load_dotenv
from supabase import create_client, Client
import os

# Load environment variables from .env file
load_dotenv()

# Your Supabase API URL and key
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_API_KEY = os.getenv('SUPABASE_API_KEY')
SUPABASE_DB = os.getenv('SUPABASE_DB')

# Function to insert data into Supabase
def insert_data_to_supabase(data_string):
    dsl = re.split(",",data_string)
    url = f"{SUPABASE_URL}/rest/v1/{SUPABASE_DB}"
    
    headers = {
        "apikey": SUPABASE_API_KEY,
        "Authorization": f"Bearer {SUPABASE_API_KEY}",
        "Content-Type": "application/json"
    }

    data = {
        "date": re.findall("^[^,]+",data_string)[0],
        "mood": re.findall(",([^,]+),",data_string)[0],
        "description": re.findall('[^,]+,[^,]+,"(.*)"',data_string)[0]
    }

    response = requests.post(url, headers=headers, data=json.dumps(data))

    if response.status_code == 201:
        print("Data inserted successfully!")
        return True
    else:
        print(f"Failed to insert data: {response.status_code}, {response.text}")
        return False

#Returns the last full week of data (starting monday)
def weekly_mood_data():
    # Define the API endpoint for OpenAI
    url = 'https://api.openai.com/v1/chat/completions'
    
    # Initialize the Supabase client
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_API_KEY)
    
    
    # Fetch data from the "mood_entries" table
    response = supabase.table('moodcheck-emi').select("*").execute()
    
    # Extract the data
    data = response.data
    
    # Convert the data to a pandas DataFrame
    df = pd.DataFrame(data)
    
    #Turn date column to the pandas Timestamp 
    df['date'] = pd.to_datetime(df['date'])

    # Convert the current date to a pandas Timestamp
    current_date = pd.to_datetime(datetime.today().date())
    
    # Find the most recent Monday before or on the current date
    last_monday = current_date - pd.Timedelta(days=current_date.weekday())
    
    # Find the start of the last full week (7 days before last_monday)
    start_of_last_full_week = last_monday - pd.Timedelta(weeks=1)
    end_of_last_full_week = (start_of_last_full_week + pd.Timedelta(days=6)).replace(hour=23, minute=59, second=59)
    
    # Filter the dataframe to get the dates within the last full week
    last_full_week_data = df[(df['date'] >= pd.to_datetime(start_of_last_full_week)) & (df['date'] <= pd.to_datetime(end_of_last_full_week))].iloc[:,:3]
        

    # Convert the DataFrame to a CSV string
    csv_string = last_full_week_data.to_csv(index=False)
    
    return csv_string