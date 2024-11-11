import requests
import json
import pandas as pd
from datetime import datetime, timezone
import re
from dotenv import load_dotenv
import boto3
import os
from supabase import create_client, Client  # Importing from supabase-py

# Load environment variables from .env file
load_dotenv()

# Your Supabase API URL and key
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_API_KEY = os.getenv('SUPABASE_API_KEY')

#Supabase Storage (s3) credentials
S3_BUCKET = os.getenv('S3_BUCKET')
S3_ENDPOINT = os.getenv('S3_ENDPOINT')
S3_REGION = os.getenv('S3_REGION')
ACCESS_KEY_ID = os.getenv('ACCESS_KEY_ID')
SECRET_ACCESS_KEY = os.getenv('SECRET_ACCESS_KEY')

#Instantiating client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_API_KEY)


def upload_mood_summary_to_supabase(fname, user_uuid):
    s3 = boto3.client(
        's3',
        region_name=S3_REGION,
        endpoint_url=S3_ENDPOINT,
        aws_access_key_id=ACCESS_KEY_ID,
        aws_secret_access_key=SECRET_ACCESS_KEY,
    )

    bucket_name = S3_BUCKET
    object_name = f'{user_uuid}/{fname}'  # Store files in a user-specific directory or with user-specific prefix

    try:
        with open(fname, 'rb') as file_data:
            s3.upload_fileobj(file_data, bucket_name, object_name)
        print(f"File {fname} uploaded successfully to {bucket_name}/{object_name}")
    except Exception as e:
        print(f"Error uploading file: {e}")



def download_summary_from_supabase(period, user_uuid):
    try:
        if period == 'weekly':
            # Calculate the last Monday
            current_date = pd.to_datetime(datetime.today().date())
            last_monday = current_date - pd.Timedelta(days=current_date.weekday() + 7)
            date_str = last_monday.strftime('%Y-%m-%d')
            filename = f'{user_uuid}/weeklysummary_{user_uuid}_{date_str}.txt'
        
        elif period == 'daily':
            # Calculate yesterday's date
            current_date = pd.to_datetime(datetime.today().date())
            start_of_last_day = (current_date - pd.Timedelta(days=1)).strftime('%Y-%m-%d')
            filename = f'{user_uuid}/dailysummary_{user_uuid}_{start_of_last_day}.txt'
        
        else:
            print("Invalid period. Please use 'daily' or 'weekly'.")
            return None
        
        # Download the file from Supabase storage
        response = supabase.storage.from_(S3_BUCKET).download(filename)
        
        # Check if the response is successful and return the file content
        if response:
            return response.decode('utf-8')  # Assuming response is in bytes, decode it to string
        else:
            print("No content found in the file.")
            return None

    except Exception as e:
        print(f"Error downloading the file: {e}")
        return None