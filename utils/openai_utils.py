import requests
import json
from datetime import datetime, timezone
import pytz
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

# Your OpenAI API key
API_KEY =  os.getenv('OPENAI_API_KEY')

def process_data(entry, user_timezone):
    # Define the API endpoint for OpenAI
    url = 'https://api.openai.com/v1/chat/completions'
    
    # Prepare the headers with your API key
    headers = {
        'Authorization': f'Bearer {API_KEY}',
        'Content-Type': 'application/json'
    }


    instruction = """You are a helpful assistant that processes data. I will give you a mood and a description, you will return 
    1. mood score
    2. mood description
    the output will be in a manner where I can simply copy what you give me and paste it into an excel table. The entries will be seperated by commas.
    Do not round any of the scores I give you.
    Add double quotes " to the description.
    something like this: 
    User Input: 5.5 deff feeling better. A little tired still, but it feel good waking up earlier for sure 100. Let's get the day moving
    Output: 5.5,"deff feeling better. A little tired still, but it feels good waking up earlier for sure 100. Let's get the day moving"
    """
    
    # Define the data payload with the user's entry
    data = {
        'model': 'gpt-4',  # Or whichever model you're using
        'messages': [
            {'role': 'system', 'content': instruction},
            {'role': 'user', 'content': f'Process this entry: "{entry}"'}
        ],
        'max_tokens': 200  # Adjust based on your needs
    }
    
    # Make the POST request to the OpenAI API
    response = requests.post(url, headers=headers, data=json.dumps(data))
    
    # Check if the request was successful
    if response.status_code == 200:
        # Parse the response JSON
        result = response.json()
        processed_content = result['choices'][0]['message']['content']

        # Use the user's timezone to get the current time
        try:
            user_tz = pytz.timezone(user_timezone)
            current_time = datetime.now(timezone.utc).astimezone(user_tz).strftime('%m/%d/%Y %H:%M')
        except Exception as e:
            # Log the error for debugging
            print(f"An error occurred: {e}")
            #Fallback is to just set it timezone as UTC 
            user_tz = pytz.timezone('UTC')
            current_time = datetime.now(timezone.utc).astimezone(user_tz).strftime('%m/%d/%Y %H:%M')
            
        return "{0},{1},{2}".format(current_time,processed_content,user_tz)
        
    else:
        # Handle errors
        print(f"Error: {response.status_code} - {response.text}")
        return None

def mood_summary(mood_string, period):
    # Define the API endpoint for OpenAI
    url = 'https://api.openai.com/v1/chat/completions'
    
    # Prepare the headers with your API key
    headers = {
        'Authorization': f'Bearer {API_KEY}',
        'Content-Type': 'application/json'
    }
    
    # Set the token limit based on the period (weekly or daily)
    max_tokens = 4095 if period == 'weekly' else 1000
    
    # Instruction changes based on the period
    instruction = f"""These are my moods for a given {period} time period in CSV format: 
    {mood_string}
    
    What trends do you see? I'm interested in a deep, reflective, analysis.
    """
    
    # Define the data payload with the user's mood
    data = {
        'model': 'gpt-4',  # Or whichever model you're using
        'messages': [
            {'role': 'system', 'content': 'You are an assistant that analyzes mood data and provides deep, reflective insights.'},
            {'role': 'user', 'content': instruction}
        ],
        'max_tokens': max_tokens,  # Adjust tokens based on period
        'temperature': 1,
        'top_p': 1  # Adjust based on your needs
    }
    
    # Make the POST request to the OpenAI API
    response = requests.post(url, headers=headers, data=json.dumps(data))
    
    # Check if the request was successful
    if response.status_code == 200:
        # Parse the response JSON
        result = response.json()
        processed_content = result['choices'][0]['message']['content']
        return processed_content
    else:
        # Handle errors
        print(f"Error: {response.status_code} - {response.text}")
        return None

# Example usage
# weekly_summary = mood_summary(weekly_mood_string, 'weekly')
# daily_summary = mood_summary(daily_mood_string, 'daily')