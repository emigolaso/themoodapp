import pandas as pd
from datetime import datetime
from supabase_utils import weekly_mood_data
from openai_utils import weekly_mood_summary
from supabase_storage_utils import upload_mood_summary_to_supabase
import os

def run_weekly_mood_summary():
    # Step 1: Collect the weekly mood data from Supabase
    mood_data = weekly_mood_data()

    # Step 2: Summarize the weekly mood data using OpenAI
    mood_summary = weekly_mood_summary(mood_data)

    # Step 3: Get the current week's Monday as a string
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