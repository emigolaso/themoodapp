# Standard library imports
import os
import re
import pandas as pd
import json
from io import StringIO
from datetime import datetime, timezone

# Third-party library imports
import pytz
import requests
from dotenv import load_dotenv
import openai
from langsmith import traceable
from langsmith.wrappers import wrap_openai

# Local module imports
from utils.supabase_utils import (
    mood_data,
    fetch_mood_analysis_historical,
    delete_manalysis_rows_from_supabase,
    insert_manalysis_to_supabase
)

#Load environment variables from .env file
load_dotenv()

#Your OpenAI API key
OPENAI_API_KEY =  os.getenv('OPENAI_API_KEY')

#Prompt Loading, for Daily Mood Analysis
with open('utils/prompts/instruction_drivers.txt', 'r', encoding='utf-8') as file:
    instruction_drivers = file.read()
# Load the instructions into the variable
with open('utils/prompts/instruction_drivers_consolidate.txt', 'r', encoding='utf-8') as file:
    instruction_drivers_consolidate = file.read()
# Load the instructions into the variable
with open('utils/prompts/instruction_drivers_refine.txt', 'r', encoding='utf-8') as file:
    instruction_drivers_refine = file.read()

#Prompt Loading, for Weekly Mood Trimming
with open('utils/prompts/instruction_weeklytrim5_rt.txt', 'r', encoding='utf-8') as file:
    instruction_weeklytrim5_rt = file.read()
with open('utils/prompts/instruction_weeklytrim5_mibc.txt', 'r', encoding='utf-8') as file:
    instruction_weeklytrim5_mibc = file.read()
with open('utils/prompts/instruction_weeklytrim5_se.txt', 'r', encoding='utf-8') as file:
    instruction_weeklytrim5_se = file.read()
with open('utils/prompts/instruction_weeklytrim5_consolidate.txt', 'r', encoding='utf-8') as file:
    instruction_weeklytrim5_consolidate = file.read()

#Prompt Loading, for daily and weekly summaries
with open('utils/prompts/instruction_daily.txt', 'r', encoding='utf-8') as file:
    instruction_daily = file.read()
with open('utils/prompts/instruction_weekly.txt', 'r', encoding='utf-8') as file:
    instruction_weekly = file.read()


#The Wrapper to Monitor LLM Calls on LangSmith
openai_client = wrap_openai(openai.Client(api_key=OPENAI_API_KEY))


@traceable
def mood_analysis_pipeline(mood_data_csv,user_uuid):
    ## Check if 'mood_data_csv' is empty
    if pd.read_csv(StringIO(mood_data_csv)).empty:
        print("No data in mood_data_csv. Skipping analysis.")
        return  # End the function early if no data

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

@traceable
def mood_summary(user_uuid, period):
    # Fetch mood logs and analysis historical data
    df = mood_data(period, user_uuid)
    df_md = fetch_mood_analysis_historical(user_uuid, period=period)

    # Determine instruction based on the period
    instruction = instruction_daily if period == 'daily' else instruction_weekly

    # Check if 'df' is empty, and set appropriate content
    df_content = "no records" if pd.read_csv(StringIO(df)).empty else df

    # Check if 'df_md' is empty, and set appropriate content
    df_md_content = "no records" if df_md.empty else df_md.to_csv(index=False)

    # Replace placeholders in the instruction
    messages = [
        {
            "role": "user",
            "content": instruction
            .replace("%0%", df_content)
            .replace("%1%", df_md_content)
        }
    ]

    # Call the OpenAI API
    response = openai_client.chat.completions.create(
        model='gpt-4o-mini',  # Or whichever model you're using
        messages=messages,
        max_tokens=4095,
        temperature=0.4,
        top_p=1,
        frequency_penalty=0,
        presence_penalty=0.2
    )

    processed_content = response.choices[0].message.content

    return processed_content


@traceable
def weekly_manalysis_trimming(user_uuid):
    #This funciton is designed to be run on Monday Mornings.. Covering all prior analysis information from last monday - sunday 
    
    #Pull the weekly historical data
    df_md = fetch_mood_analysis_historical(user_uuid,'weekly')

    # Check if 'df_md' is empty, and skip processing if so
    if df_md.empty:
        print("No data in weekly historical mood analysis. Skipping trimming.")
        return  # End the function early if no data
        
    messages = [
        {
            "role": "user",
            "content": instruction_weeklytrim5_rt
            .replace("%0%",                      
                     ("no records found" 
                      if df_md[df_md.category == "recurring_triggers"].empty 
                      else df_md[df_md.category == "recurring_triggers"].to_csv(index=False)
                    )
                    )
        }
    ]
    
    # Call the OpenAI API
    response = openai_client.chat.completions.create(
        model='gpt-4o-mini',  # Or whichever model you're using
        messages=messages,
        max_tokens=4095,
        temperature=0.4,
        top_p=1,
        frequency_penalty=0,
        presence_penalty=0.2
    )
    
    processed_content_rt = response.choices[0].message.content

    messages = [
        {
            "role": "user",
            "content": instruction_weeklytrim5_mibc
            .replace("%0%",                      
                     ("no records found" 
                      if df_md[df_md.category == "mood_impact_by_category"].empty 
                      else df_md[df_md.category == "mood_impact_by_category"].to_csv(index=False)
                    )
                    )        }
    ]
    
    # Call the OpenAI API
    response = openai_client.chat.completions.create(
        model='gpt-4o-mini',  # Or whichever model you're using
        messages=messages,
        max_tokens=4095,
        temperature=0.4,
        top_p=1,
        frequency_penalty=0,
        presence_penalty=0.2
    )
    
    processed_content_mibc = response.choices[0].message.content

    messages = [
        {
            "role": "user",
            "content": instruction_weeklytrim5_se
            .replace("%0%",
                     ("no records found" 
                      if df_md[df_md.category == "significant_events"].empty 
                      else df_md[df_md.category == "significant_events"].to_csv(index=False)
                    )
                    )        
        }
    ]
    
    # Call the OpenAI API
    response = openai_client.chat.completions.create(
        model='gpt-4o-mini',  # Or whichever model you're using
        messages=messages,
        max_tokens=4095,
        temperature=0.4,
        top_p=1,
        frequency_penalty=0,
        presence_penalty=0.2
    )
    
    processed_content_se = response.choices[0].message.content


    messages = [
        {
            "role": "user",
            "content": instruction_weeklytrim5_consolidate
            .replace("%0%", processed_content_rt)
            .replace("%1%",processed_content_mibc)
            .replace("%2%",processed_content_se)
        }
    ]
    
    # Call the OpenAI API
    response = openai_client.chat.completions.create(
        model='gpt-4o-mini',  # Or whichever model you're using
        messages=messages,
        max_tokens=4095,
        temperature=0.4,
        top_p=1,
        frequency_penalty=0,
        presence_penalty=0.2
    )
    
    processed_content_consolidate = response.choices[0].message.content

    ##Deleting the input rows. Will switch out for consolidated rows 
    delete_manalysis_rows_from_supabase(user_uuid, ids_to_delete = df_md['id'].tolist(), trim=False)

    ##Insert output/consolidated descriptions 
    ## RESULTS POST-PROCESSING
    match = re.search(r"```json\s*(\{[\s\S]*?\})\s*```", processed_content_consolidate, re.DOTALL)
    
    if match:
        json_str = match.group(1).strip()
        try:
            # Parse the JSON string
            parsed_json = json.loads(json_str)
    
            #Insert mood analysis data to supabase 
            insert_manalysis_to_supabase(parsed_json,user_uuid)
    
        except json.JSONDecodeError:
            pass
            
    ##CHecking and tirmming if length > 100 
    delete_manalysis_rows_from_supabase(user_uuid, ids_to_delete = None, trim=True)


# Example usage
# weekly_summary = mood_summary(weekly_mood_string, 'weekly')
# daily_summary = mood_summary(daily_mood_string, 'daily')