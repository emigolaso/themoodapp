import pandas as pd
from datetime import datetime
import pytz
import os
import sys
from supabase_storage_utils import upload_mood_summary_to_supabase
from openai_utils import mood_summary
from supabase_utils import mood_data

def run_mood_summary(period):
    # Get current date and time, convert to EDT
    current_datetime = pd.to_datetime(datetime.utcnow()).tz_localize(pytz.utc).tz_convert(pytz.timezone('US/Eastern'))
    day_of_week = current_datetime.weekday()

    if period == 'weekly':
        # Check if it's Monday and between 12:00 AM and 12:21 AM ... adding 1 hour just in case... cause heroku is sketch 
        if day_of_week == 0 and current_datetime.time() >= pd.Timestamp('00:00:00').time() and current_datetime.time() <= pd.Timestamp('01:21:00').time():
            # Step 1: Collect the weekly mood data from Supabase
            mood_data_csv = mood_data('weekly')

            # Step 2: Summarize the weekly mood data using OpenAI
            mood_summary_text = mood_summary(mood_data_csv, 'weekly')

            # Step 3: Get the last week's Monday as a string
            current_date = pd.to_datetime(datetime.today().date())
            last_monday = current_date - pd.Timedelta(days=current_date.weekday() + 7)
            last_monday_str = last_monday.strftime('%Y-%m-%d')

            # Step 4: Save the summary to a temporary file
            temp_filename = f'weeklysummary_{last_monday_str}.txt'
            with open(temp_filename, 'w') as file:
                file.write(mood_summary_text)

            # Step 5: Upload the file to Supabase storage
            upload_mood_summary_to_supabase(temp_filename)

            # Optionally, clean up the local file if you don't need to keep it
            if os.path.exists(temp_filename):
                os.remove(temp_filename)

    elif period == 'daily':
        # Check if it's Monday and between 12:00 AM and 12:21 AM ...adding 1 hour just in case... cause heroku is sketch
        if current_datetime.time() >= pd.Timestamp('00:00:00').time() and current_datetime.time() <= pd.Timestamp('01:21:00').time():

            # Step 1: Collect the daily mood data from Supabase
            mood_data_csv = mood_data('daily')
    
            # Step 2: Summarize the daily mood data using OpenAI
            mood_summary_text = mood_summary(mood_data_csv, 'daily')
    
            # Step 3: Get the date for yesterday
            start_of_last_day = (current_datetime - pd.Timedelta(days=1)).strftime('%Y-%m-%d')
    
            # Step 4: Save the summary to a temporary file
            temp_filename = f'dailysummary_{start_of_last_day}.txt'
            with open(temp_filename, 'w') as file:
                file.write(mood_summary_text)
    
            # Step 5: Upload the file to Supabase storage
            upload_mood_summary_to_supabase(temp_filename)
    
            # Optionally, clean up the local file if you don't need to keep it
            if os.path.exists(temp_filename):
                os.remove(temp_filename)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        summary_type = sys.argv[1]
        if summary_type in ["daily", "weekly"]:
            run_mood_summary(summary_type)
        else:
            print("Invalid argument. Use 'daily' or 'weekly'.")
    else:
        print("Please provide 'daily' or 'weekly' as an argument.")