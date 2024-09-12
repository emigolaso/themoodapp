import requests
import json
import re
from dotenv import load_dotenv
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