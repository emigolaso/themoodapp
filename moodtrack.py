from flask import Flask, request, jsonify, render_template, send_from_directory
import markdown  # Import markdown extension
from utils.openai_utils import process_data
from utils.supabase_utils import insert_data_to_supabase
from utils.supabase_storage_utils import download_weekly_summary_from_supabase
from supabase import create_client, Client
import os
from datetime import datetime, timezone
from dash import Dash, dcc, html
import plotly.express as px
import pandas as pd

# Initialize Flask app
app = Flask(__name__)

# Initialize Dash app within Flask
dash_app = Dash(__name__, server=app, url_base_pathname='/dashboard/')

# Route for the existing main page (index.html)
@app.route('/')
# Making week of button dynamic 
def index():
    # Calculate the last full week's Monday
    current_date = pd.to_datetime(datetime.today().date())
    last_monday = current_date - pd.Timedelta(days=current_date.weekday() + 7)
    last_monday_str = last_monday.strftime('%Y-%m-%d')
    
    # Pass the calculated date to the template
    return render_template('index.html', last_week=last_monday_str)

# Route for submitting moods
@app.route('/submit_entry', methods=['POST'])
def submit_entry():
    try:
        entry = request.json.get('entry')
        if not entry:
            return jsonify({'message': 'No entry provided'}), 400 
        
        formatted_data = process_data(entry)
        if not formatted_data:
            return jsonify({'message': 'Failed to format data with ChatGPT.'}), 500
            
        success = insert_data_to_supabase(formatted_data)
        if not success:
            return jsonify({'message': 'Failed to insert data into Supabase.'}), 500
        
        return jsonify({'message': 'Data inserted successfully!'})
    
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'message': 'An error occurred'}), 500

# Route for getting weekly summaries
@app.route('/weekly-summary')
def display_weekly_summary():
    current_date = pd.to_datetime(datetime.today().date())
    last_monday = current_date - pd.Timedelta(days=current_date.weekday() + 7)
    last_monday_str = last_monday.strftime('%Y-%m-%d')
    
    # Download the file from Supabase 
    weekly_summary_content = download_weekly_summary_from_supabase(last_monday_str)
   
    # Convert the weekly summary content from Markdown to HTML
    weekly_summary_html = markdown.markdown(weekly_summary_content)
    
    return render_template('weekly_summary.html', summary=weekly_summary_html)


# Setup the Dash app and plots
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_API_KEY = os.getenv('SUPABASE_API_KEY')
SUPABASE_DB = os.getenv('SUPABASE_DB')
supabase: Client = create_client(SUPABASE_URL, SUPABASE_API_KEY)

response = supabase.table(f'{SUPABASE_DB}').select("*").execute()
data = response.data
df = pd.DataFrame(data)
df['date'] = pd.to_datetime(df['date'])

# Summary Statistics
mean_mood = df['mood'].mean()
median_mood = df['mood'].median()
mode_mood = df['mood'].mode()[0]
min_mood = df['mood'].min()
max_mood = df['mood'].max()

summary_stats = html.Div([
    html.H2('Summary Statistics'),
    html.P(f'Mean Mood: {mean_mood}'),
    html.P(f'Median Mood: {median_mood}'),
    html.P(f'Mode Mood: {mode_mood}'),
    html.P(f'Minimum Mood: {min_mood}'),
    html.P(f'Maximum Mood: {max_mood}')
])

# Weekly Mood Plot
df['Week Start'] = (df['date'] - pd.to_timedelta(df['date'].dt.weekday, unit='d')).dt.date
weekly_mood_avg = df.groupby('Week Start')['mood'].mean().reset_index()
fig_weekly_moods = px.bar(weekly_mood_avg, x='Week Start', y='mood', title='Average Mood by Week')

# Prepare tick values and labels
tick_vals = weekly_mood_avg['Week Start']
tick_text = weekly_mood_avg['Week Start']

# Update x-axis to display only the dates from your data
fig_weekly_moods.update_xaxes(
    tickmode='array',
    tickvals=tick_vals,
    ticktext=tick_text
)

# Day of Week Plot
df['Day'] = df['date'].dt.day_name()
day_mood_avg = df.groupby('Day')['mood'].mean().reset_index()
day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
day_mood_avg['Day'] = pd.Categorical(day_mood_avg['Day'], categories=day_order, ordered=True)
fig_day_moods = px.bar(day_mood_avg.sort_values('Day'), x='Day', y='mood', title='Average Mood by Day of Week')

# Time of Day Plot
df['Time of Day'] = pd.cut(df['date'].dt.hour, bins=[0, 12, 18, 24], labels=['Morning', 'Afternoon', 'Evening'], right=False)
time_mood_avg = df.groupby('Time of Day')['mood'].mean().reset_index()
fig_time_moods = px.bar(time_mood_avg, x='Time of Day', y='mood', title='Average Mood by Time of Day')

# Mood Fluctuations Plot
df = df.sort_values(by='date')
df['Mood Change'] = df['mood'].diff()
df['Date'] = df['date'].dt.date
daily_mood_fluctuations = df.groupby('Date')['Mood Change'].mean().reset_index()
fig_fluctuations = px.line(daily_mood_fluctuations, x='Date', y='Mood Change', title='Average Mood Fluctuations')

# Setup Dash layout
dash_app.layout = html.Div(children=[
    html.H1(children='Mood Tracking Dashboard'),
    summary_stats,
    dcc.Graph(id='weekly-moods', figure=fig_weekly_moods),
    dcc.Graph(id='day-of-week-moods', figure=fig_day_moods),
    dcc.Graph(id='time-of-day-moods', figure=fig_time_moods),
    dcc.Graph(id='mood-fluctuations', figure=fig_fluctuations),
])

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5009))
    app.run(host='0.0.0.0', port=port, debug=True)