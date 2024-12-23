# Standard library imports
import os
import sys
from datetime import datetime

# Third-party library imports
import pandas as pd
import pytz
import json
import re
from dotenv import load_dotenv
from supabase import create_client, Client

# Local imports
from supabase_storage_utils import upload_mood_summary_to_supabase
from openai_utils import mood_summary, mood_analysis_pipeline, weekly_manalysis_trimming
from supabase_utils import mood_data, insert_manalysis_to_supabase, delete_manalysis_rows_from_supabase


# Load environment variables from .env file
load_dotenv()

# Your Supabase API URL and key
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_API_KEY = os.getenv('SUPABASE_API_KEY')
SUPABASE_DB = os.getenv('SUPABASE_DB')
SUPABASE_DB_MANALYSIS = os.getenv('SUPABASE_DB_MANALYSIS')
supabase: Client = create_client(SUPABASE_URL, SUPABASE_API_KEY)

def run_mood_summary(period):
    # Get list of all unique user UUIDs
    user_uuids = get_all_user_uuids()  # You'll need to implement this function
    # Get current date and time, convert to EDT
    current_datetime = pd.to_datetime(datetime.utcnow()).tz_localize(pytz.utc).tz_convert(pytz.timezone('US/Eastern'))
    day_of_week = current_datetime.weekday()

    for user_uuid in user_uuids:
        if period == 'weekly':
            # Check if it's Monday and between 12:00 AM and 12:21 AM ... adding 1 hour just in case... cause heroku is sketch 
            if day_of_week == 0 and current_datetime.time() >= pd.Timestamp('00:00:00').time() and current_datetime.time() <= pd.Timestamp('01:21:00').time():
                # Step 1: Collect the weekly mood data from Supabase
                mood_data_csv = mood_data('weekly', user_uuid=user_uuid)
    
                # Step 2: Summarize the weekly mood data using OpenAI
                mood_summary_text = mood_summary(user_uuid, 'weekly')
    
                # Step 3: Get the last week's Monday as a string
                last_monday_str = (current_datetime - pd.Timedelta(days=current_datetime.weekday() + 7)).strftime('%Y-%m-%d')
    
                # Step 4: Save the summary to a temporary file, Upload the file to Supabase storage
                temp_filename = f'weeklysummary_{user_uuid}_{last_monday_str}.txt'
                save_and_upload_summary(temp_filename, mood_summary_text, user_uuid)

                # Step 5: Perform weekly trimming for mood analysis table
                weekly_manalysis_trimming(user_uuid)
                

        elif period == 'daily':
            # Check if it's between 12:00 AM and 12:21 AM
            if current_datetime.time() >= pd.Timestamp('00:00:00').time() and current_datetime.time() <= pd.Timestamp('01:21:00').time():
                # Step 1: Collect the daily mood data from Supabase
                mood_data_csv = mood_data('daily', user_uuid=user_uuid)
        
                # Step 2: Summarize the daily mood data using OpenAI
                mood_summary_text = mood_summary(user_uuid, 'daily')
        
                # Step 3: Get the date for yesterday
                start_of_last_day = (current_datetime - pd.Timedelta(days=1)).strftime('%Y-%m-%d')
        
                # Step 4: Save the summary to a temporary file, Upload the file to Supabase storage
                temp_filename = f'dailysummary_{user_uuid}_{start_of_last_day}.txt'
                save_and_upload_summary(temp_filename, mood_summary_text, user_uuid)

                # Step 5: Run mood analysis pipeline and insert analysis results
                run_mood_analysis_and_insert(user_uuid)


def run_mood_analysis_and_insert(user_uuid):
    # Collect daily mood data
    mood_data_csv = mood_data('daily', user_uuid)

    # Run mood analysis pipeline
    mood_analysis_json = mood_analysis_pipeline(mood_data_csv, user_uuid)

    # Insert mood analysis results into Supabase
    if mood_analysis_json:
        insert_manalysis_to_supabase(mood_analysis_json, user_uuid)


def get_all_user_uuids():
    # Query the database to get all unique user UUIDs
    response = supabase.table(SUPABASE_DB).select('user_uuid').execute()
    user_uuids = {record['user_uuid'] for record in response.data}
    return user_uuids


def save_and_upload_summary(filename, content, user_uuid):
    with open(filename, 'w') as file:
        file.write(content)
    upload_mood_summary_to_supabase(filename, user_uuid)
    os.remove(filename)  # Clean up local file after upload


if __name__ == "__main__":
    if len(sys.argv) > 1:
        summary_type = sys.argv[1]
        if summary_type in ["daily", "weekly"]:
            run_mood_summary(summary_type)
        else:
            print("Invalid argument. Use 'daily' or 'weekly'.")
    else:
        print("Please provide 'daily' or 'weekly' as an argument.")