import pandas as pd
import pytz
from datetime import datetime
from supabase_utils import weekly_mood_data
from openai_utils import weekly_mood_summary
from supabase_storage_utils import upload_mood_summary_to_supabase
import os

def run_weekly_mood_summary():

    # Get current date and time -- modified to convert to EDT 
    current_datetime = pd.to_datetime(datetime.utcnow()).tz_localize(pytz.utc).tz_convert(pytz.timezone('US/Eastern'))
    # Get current day of the week (0 = Monday)
    day_of_week = current_datetime.weekday()
    # Check if it's Monday and the time is between 12:00 AM and 12:10 AM
    if day_of_week == 1 and current_datetime.time() >= pd.Timestamp('07:19:00').time()  and current_datetime.time()  <= pd.Timestamp('07:31:00').time():
        # Step 1: Collect the weekly mood data from Supabase
        mood_data = weekly_mood_data()
    
        # Step 2: Summarize the weekly mood data using OpenAI
        mood_summary = weekly_mood_summary(mood_data)
    
        # Step 3: Get the last week's Monday as a string
        current_date = pd.to_datetime(datetime.today().date())
        last_monday = current_date - pd.Timedelta(days=current_date.weekday() + 7)
        last_monday_str = last_monday.strftime('%Y-%m-%d')
    
        # Step 4: Save the summary to a temporary file
        temp_filename = f'weeklysummary_{last_monday_str}.txt'
        with open(temp_filename, 'w') as file:
            file.write(mood_summary)
    
        # Step 5: Upload the file to Supabase storage
        upload_mood_summary_to_supabase(last_monday_str)
    
        # Optionally, clean up the local file if you don't need to keep it
        if os.path.exists(temp_filename):
            os.remove(temp_filename)

if __name__ == "__main__":
    run_weekly_mood_summary()