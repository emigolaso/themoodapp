import requests
import json
from datetime import datetime, timezone
import pytz
from dotenv import load_dotenv
import os
import re
import openai
from langsmith import traceable
from langsmith.wrappers import wrap_openai
from utils.supabase_utils import fetch_mood_analysis_historical

#Load environment variables from .env file
load_dotenv()

#Your OpenAI API key
OPENAI_API_KEY =  os.getenv('OPENAI_API_KEY')

#Prompt Loading
with open('utils/prompts/instruction_drivers.txt', 'r', encoding='utf-8') as file:
    instruction_drivers = file.read()
# Load the instructions into the variable
with open('utils/prompts/instruction_drivers_consolidate.txt', 'r', encoding='utf-8') as file:
    instruction_drivers_consolidate = file.read()
# Load the instructions into the variable
with open('utils/prompts/instruction_drivers_refine.txt', 'r', encoding='utf-8') as file:
    instruction_drivers_refine = file.read()


#The Wrapper to Monitor LLM Calls on LangSmith
openai_client = wrap_openai(openai.Client(api_key=OPENAI_API_KEY))

def process_data(entry, user_timezone):
    # Define the API endpoint for OpenAI
    url = 'https://api.openai.com/v1/chat/completions'
    
    # Prepare the headers with your API key
    headers = {
        'Authorization': f'Bearer {OPENAI_API_KEY}',
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

@traceable
def mood_analysis_pipeline(mood_data_csv,user_uuid):
    ## CHAIN 1: Run Analysis X Times Based on Observations
    ## Dynamically determine the number of runs: 3 * number of rows, capped at 10
    num_runs = min(3 * mood_data_csv.strip().count('\n') , 10)
    analysis_runs = ""
    for i in range(num_runs):
        messages = [
            {"role": "user", "content": instruction_drivers.replace("%0%", mood_data_csv)}
        ]
        response = openai_client.chat.completions.create(
            model='gpt-4o-mini',
            messages=messages,
            max_tokens=4095,
            temperature=0.4,
            top_p=1,
            frequency_penalty=0,
            presence_penalty=0.2
        )
        # Append each processed response
        analysis_runs += response.choices[0].message.content + "\n"

    ## CHAIN 2: Consolidate Runs
    consolidated_messages = [
        {"role": "user", "content": instruction_drivers_consolidate.replace("%0%", analysis_runs)}
    ]

    response = openai_client.chat.completions.create(
        model='gpt-4o-mini',
        messages=consolidated_messages,
        max_tokens=4095,
        temperature=0.4,
        top_p=1,
        frequency_penalty=0,
        presence_penalty=0.2
    )

    consolidated_content = response.choices[0].message.content

    #Extracting historicals 
    manalysis_historical = fetch_mood_analysis_historical(user_uuid, period='all')
   
    # Convert to CSV string
    manalysis_historical = manalysis_historical.to_csv(index=False)
    
    ## CHAIN 3: Refine and Incorporate Into Results
    refined_messages = [
        {"role": "user", "content": instruction_drivers_refine
            .replace("%0%", consolidated_content)
            .replace("%1%", manalysis_historical)}
    ]

    response = openai_client.chat.completions.create(
        model='gpt-4o-mini',
        messages=refined_messages,
        max_tokens=4095,
        temperature=0.4,
        top_p=1,
        frequency_penalty=0,
        presence_penalty=0.2
    )

    refined_content = response.choices[0].message.content

    ## RESULTS POST-PROCESSING
    match = re.search(r"```json\s*(\{[\s\S]*?\})\s*```", refined_content, re.DOTALL)

    if match:
        json_str = match.group(1).strip()
        try:
            # Parse the JSON string
            parsed_json = json.loads(json_str)
            return parsed_json
            
        except json.JSONDecodeError: pass


def mood_summary(mood_string, period):
    # Define the API endpoint for OpenAI
    url = 'https://api.openai.com/v1/chat/completions'
    
    # Prepare the headers with your API key
    headers = {
        'Authorization': f'Bearer {OPENAI_API_KEY}',
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