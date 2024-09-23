import requests
import json
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


def upload_mood_summary_to_supabase(date):
    # Initialize boto3 S3 client with Supabase settings
    s3 = boto3.client(
        's3',
        region_name=S3_REGION,
        endpoint_url=S3_ENDPOINT,
        aws_access_key_id=ACCESS_KEY_ID,
        aws_secret_access_key=SECRET_ACCESS_KEY,
        # No session token needed for full access with S3 access keys
    )
    
    # File path to upload (adjust as needed)
    file_path = f'weeklysummary_{date}.txt'
    
    # Upload file to the S3 bucket
    bucket_name = S3_BUCKET  # Your Supabase bucket name
    object_name = f'weeklysummary_{date}.txt'  # The path inside the bucket where the file will go
    
    try:
        # Open the file and upload it to Supabase Storage
        with open(file_path, 'rb') as file_data:
            s3.upload_fileobj(file_data, bucket_name, object_name)
        print(f"File {file_path} uploaded successfully to {bucket_name}/{object_name}")
    except Exception as e:
        print(f"Error uploading file: {e}")


def download_weekly_summary_from_supabase(week_of):
    """
    Download the weekly summary file from Supabase Storage.
    
    Args:
    - week_of: The week identifier for the file (e.g., '2024-09-18').
    
    Returns:
    - The content of the file as a string.
    """
    try:
        response = supabase.storage.from_(S3_BUCKET).download(f'weeklysummary_{week_of}.txt')
        
        # Check if the response is successful and return the file content
        if response:
            return response.decode('utf-8')  # Assuming response is in bytes, decode it to string
        else:
            print("No content found in the file.")
            return None
    except Exception as e:
        print(f"Error downloading the file: {e}")
        return None