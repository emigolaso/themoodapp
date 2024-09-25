from flask import Flask, request, jsonify, render_template, send_from_directory
import markdown  # Import markdown extension
from utils.openai_utils import process_data
from utils.supabase_utils import insert_data_to_supabase
from utils.supabase_storage_utils import download_summary_from_supabase
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
    
    # Calculate the last full day's date (yesterday)
    last_day = current_date - pd.Timedelta(days=1)
    last_day_str = last_day.strftime('%Y-%m-%d')
    
    # Pass the calculated date to the template
    return render_template('index.html', last_week=last_monday_str, last_day=last_day_str)

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
    # Download the file from Supabase 
    weekly_summary_content = download_summary_from_supabase('weekly')
   
    # Convert the weekly summary content from Markdown to HTML
    weekly_summary_html = markdown.markdown(weekly_summary_content)
    
    return render_template('weekly_summary.html', summary=weekly_summary_html)


@app.route('/daily-summary')
def display_daily_summary():
    # Download the daily summary file from Supabase
    daily_summary_content = download_summary_from_supabase('daily')

    # Convert the daily summary content from Markdown to HTML
    daily_summary_html = markdown.markdown(daily_summary_content)

    return render_template('daily_summary.html', summary=daily_summary_html)


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
    html.P(f'Mean Mood: {mean_mood:.2f}'),
    html.P(f'Median Mood: {median_mood}'),
    html.P(f'Mode Mood: {mode_mood}'),
    html.P(f'Minimum Mood: {min_mood}'),
    html.P(f'Maximum Mood: {max_mood}')
])

### Monthly mood plot
df['Month Start'] = df['date'].dt.to_period('M').dt.to_timestamp()
monthly_mood_avg = df.groupby('Month Start')['mood'].mean().reset_index()
fig_monthly_moods = px.bar(monthly_mood_avg, x='Month Start', y='mood', title='Average Mood by Month Start Date')

# Prepare tick values and labels for months
tick_vals = monthly_mood_avg['Month Start']
tick_text = monthly_mood_avg['Month Start'].dt.strftime('%Y-%m')

# Update x-axis to display only the monthly start dates
fig_monthly_moods.update_xaxes(
    tickmode='array',
    tickvals=tick_vals,
    ticktext=tick_text
)

### Weekly Mood Plot
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

### Day of week plot
df['day_only'] = df['date'].dt.date

# Assuming df is your main DataFrame with 'date' and 'mood' columns
df['Day'] = df['day_only'].apply(lambda x: x.strftime('%A'))  # Get day names from 'day_only'

# 1. Calculate the long-run average mood by day of the week (averaging across all records for each day of the week)
day_mood_avg = df.groupby('Day')['mood'].mean().reset_index()

# Set the correct order for the days of the week
day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
day_mood_avg['Day'] = pd.Categorical(day_mood_avg['Day'], categories=day_order, ordered=True)

# 2. Extract the most recent unique calendar days
# Sort the DataFrame by date in descending order
df_sorted = df.sort_values('date', ascending=False)

# Group by day, then get the average mood for the most recent day for each day of the week
latest_mood_per_day = df_sorted.groupby('Day').head(1)  # Get the most recent date for each day
daily_mood_avg_recent = df[df['day_only'].isin(latest_mood_per_day['day_only'])].groupby(['Day'])['mood'].mean().reset_index()

# 3. Merge the long-run daily averages with the most recent daily averages
merged_data = pd.merge(day_mood_avg, daily_mood_avg_recent, on='Day', how='left', suffixes=('_weekly_avg', '_latest_avg'))

# Ensure that the 'Day' column in the merged_data is categorized correctly
merged_data['Day'] = pd.Categorical(merged_data['Day'], categories=day_order, ordered=True)
merged_data = merged_data.sort_values('Day')

# Add the date to the merged data for the latest mood (for hover info)
merged_data = pd.merge(merged_data, latest_mood_per_day[['Day', 'day_only']], on='Day', how='left')

# 4. Create the bar plot with both long-run daily average and recent mood averages
fig_day_moods = px.bar(merged_data, 
             x='Day', 
             y=['mood_weekly_avg', 'mood_latest_avg'], 
             barmode='group',
             title='All-Time Daily Mood Average vs Most Recent Daily Mood by Day of Week')

# Update the hover data to show both the mood and the date, capping the decimals at 2
fig_day_moods.update_traces(
    hovertemplate='<b>%{x}</b><br>All-Time Avg: %{customdata[0]:.2f}<br>Recent Avg: %{customdata[1]:.2f} (on %{customdata[2]})',
    customdata=merged_data[['mood_weekly_avg', 'mood_latest_avg', 'day_only']]
)

### Time of Day Plot
df['Time of Day'] = pd.cut(df['date'].dt.hour, bins=[0, 12, 18, 24], labels=['Morning', 'Afternoon', 'Evening'], right=False)

# 1. Calculate the long-run average mood for each time of day (all-time)
time_mood_avg = df.groupby('Time of Day', observed=True)['mood'].mean().reset_index()

# 2. Extract the most recent entries for each time of day
# Sort by date first, then group by 'Time of Day' to get the most recent entries
latest_mood_per_time = df.sort_values('date', ascending=False).groupby('Time of Day', observed=True).head(1).reset_index()

# Calculate the average mood for the most recent entries
latest_mood_avg_per_time = latest_mood_per_time.groupby('Time of Day', observed=True).agg({'mood': 'mean', 'date': 'max'}).reset_index()

# 3. Merge the long-run averages with the latest averages
merged_data = pd.merge(time_mood_avg, latest_mood_avg_per_time, on='Time of Day', how='left', suffixes=('_all_time_avg', '_latest_avg'))

# Add the date to the latest average labels
merged_data['latest_avg_with_date'] = merged_data.apply(lambda row: f"{row['mood_latest_avg']:.2f} (on {row['date'].strftime('%Y-%m-%d')})", axis=1)

# 4. Create the bar plot comparing all-time and latest averages
fig_time_moods = px.bar(
    merged_data, 
    x='Time of Day', 
    y=['mood_all_time_avg', 'mood_latest_avg'], 
    barmode='group',
    title='All-Time vs Latest Mood by Time of Day'
)

# Update the hover data to show both all-time and latest averages with the date
fig_time_moods.update_traces(
    hovertemplate='<b>%{x}</b><br>All-Time Avg: %{customdata[0]:.2f}<br>Latest Avg: %{customdata[1]}',
    customdata=merged_data[['mood_all_time_avg', 'latest_avg_with_date']]
)


# Setup Dash layout
dash_app.layout = html.Div(children=[
    html.H1(children='Mood Tracking Dashboard'),
    summary_stats,
    dcc.Graph(id='monthly-moods', figure=fig_monthly_moods),
    dcc.Graph(id='weekly-moods', figure=fig_weekly_moods),
    dcc.Graph(id='day-of-week-moods', figure=fig_day_moods),
    dcc.Graph(id='time-of-day-moods', figure=fig_time_moods),
])

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5009))
    app.run(host='0.0.0.0', port=port, debug=True)