import pandas as pd
import plotly.express as px
from dash import html
from flask import g, session
from flask_caching import Cache
import os

# Initialize Cache with Redis directly in this file
cache = Cache()

def init_cache(app):
    """Initialize Redis cache for the given Flask app."""
    app.config['CACHE_TYPE'] = 'RedisCache'
    app.config['CACHE_REDIS_URL'] = os.getenv('REDISCLOUD_URL')
    cache.init_app(app)

# Load data from Supabase with cache
@cache.cached(timeout=86400, key_prefix=lambda: f'supabase_data_cache_{g.user_uuid}')  # Cache for 24 hours per user
def load_data(supabase, SUPABASE_DB):
    """Function to load data from Supabase for a specific user."""
    if not g.user_uuid:
        raise ValueError("User not authenticated")
        
    response = supabase.table(f'{SUPABASE_DB}').select('id, date, mood, description').eq('user_uuid', g.user_uuid).execute()
    data = response.data
    df = pd.DataFrame(data)
    df['date'] = pd.to_datetime(df['date'])
    return df

# Generate all graphs and stats with cache
@cache.cached(timeout=86400, key_prefix=lambda: f'graphs_cache_{g.user_uuid}')  # Cache for 24 hours per user
def generate_all_graphs(df):
    """Generate all graphs and summary statistics."""
    summary_stats = generate_summary_statistics(df)
    fig_monthly_moods = generate_monthly_mood_plot(df)
    fig_weekly_moods = generate_weekly_mood_plot(df)
    fig_day_moods = generate_day_of_week_plot(df)
    fig_time_moods = generate_time_of_day_plot(df)

    return summary_stats, fig_monthly_moods, fig_weekly_moods, fig_day_moods, fig_time_moods


def generate_summary_statistics(df):
    """Generate summary statistics for the mood data."""
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
    return summary_stats

def generate_monthly_mood_plot(df, alpha=0.3):
    """Generate the monthly mood plot with EMA line."""
    df['Month Start'] = df['date'].dt.to_period('M').dt.to_timestamp()
    monthly_mood_avg = df.groupby('Month Start')['mood'].mean().reset_index()
    
    # Calculate the EMA
    monthly_mood_avg['EMA'] = monthly_mood_avg['mood'].ewm(alpha=alpha).mean()
    
    # Create the bar plot for monthly average mood
    fig_monthly_moods = px.bar(monthly_mood_avg, x='Month Start', y='mood', title='Average Mood by Month Start Date')

    # Add the EMA line with formatted label
    fig_monthly_moods.add_scatter(x=monthly_mood_avg['Month Start'], y=monthly_mood_avg['EMA'],
                                  mode='lines', name=f'Baseline Mood<br>(ema α={alpha})', line=dict(color='orange')
    )

    # Prepare tick values and labels for months
    tick_vals = monthly_mood_avg['Month Start']
    tick_text = monthly_mood_avg['Month Start'].dt.strftime('%Y-%m')

    fig_monthly_moods.update_xaxes(
        tickmode='array',
        tickvals=tick_vals,
        ticktext=tick_text
    )
    
    return fig_monthly_moods


import pandas as pd
import plotly.express as px

def generate_weekly_mood_plot(df):
    """Generate the weekly mood plot with EMA overlay."""
    # Define the start of each week
    df['Week Start'] = (df['date'] - pd.to_timedelta(df['date'].dt.weekday, unit='d')).dt.date
    weekly_mood_avg = df.groupby('Week Start')['mood'].mean().reset_index()
    
    # Calculate EMA on the weekly mood average
    alpha = 0.3  # Controls the decay rate; adjust as needed
    weekly_mood_avg['EMA'] = weekly_mood_avg['mood'].ewm(alpha=alpha).mean()
    
    # Create the bar chart for weekly mood averages
    fig_weekly_moods = px.bar(weekly_mood_avg, x='Week Start', y='mood', title='Average Mood by Week')
    
    # Add the EMA line
    fig_weekly_moods.add_scatter(x=weekly_mood_avg['Week Start'], y=weekly_mood_avg['EMA'],
                                 mode='lines', name=f'Baseline Mood<br> (ema α={alpha})', line=dict(color='orange'))
    
    # Customize tick values and labels
    tick_vals = weekly_mood_avg['Week Start']
    tick_text = weekly_mood_avg['Week Start']
    
    fig_weekly_moods.update_xaxes(
        tickmode='array',
        tickvals=tick_vals,
        ticktext=tick_text,
        rangeslider=dict(
            visible=True,  # Enable the rangeslider
            thickness=0.05,  # Make the slider minimal in thickness
            bgcolor="white",  # Set the background color to blend with the graph
            bordercolor="gray",  # Add a border for better visibility
            borderwidth=1  # Keep the border thin for subtle design
        ),
        range=[
            weekly_mood_avg['Week Start'].iloc[-8] - pd.Timedelta(days=3),  # Add padding to the start
            weekly_mood_avg['Week Start'].iloc[-1] + pd.Timedelta(days=3)   # Add padding to the end
        ]
    )
    
    # Update layout for better visualization
    fig_weekly_moods.update_layout(
        xaxis=dict(
            title='Week Start',
            rangeselector=dict(visible=False),  # Remove the range selector
            showgrid=False  # Keep gridlines off for cleaner visuals
        ),
        yaxis=dict(title='Mood'),
        margin=dict(l=50, r=50, t=50, b=50),
        dragmode=False,  # Disable dragging to simplify interaction
        height=500  # Set height to keep it proportional
    )


    return fig_weekly_moods


def generate_day_of_week_plot(df):
    """Generate the day of the week mood plot with conditional color-coding."""
    df['day_only'] = df['date'].dt.date
    df['Day'] = df['day_only'].apply(lambda x: x.strftime('%A'))

    # Calculate long-run average mood by day
    day_mood_avg = df.groupby('Day')['mood'].mean().reset_index()
    day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    day_mood_avg['Day'] = pd.Categorical(day_mood_avg['Day'], categories=day_order, ordered=True)

    # Calculate the most recent mood average by day
    df_sorted = df.sort_values('date', ascending=False)
    latest_mood_per_day = df_sorted.groupby('Day').head(1)
    daily_mood_avg_recent = df[df['day_only'].isin(latest_mood_per_day['day_only'])].groupby(['Day'])['mood'].mean().reset_index()

    # Merge the long-run and recent averages
    merged_data = pd.merge(day_mood_avg, daily_mood_avg_recent, on='Day', how='left', suffixes=('_weekly_avg', '_latest_avg'))
    merged_data['Day'] = pd.Categorical(merged_data['Day'], categories=day_order, ordered=True)
    merged_data = merged_data.sort_values('Day')
    merged_data = pd.merge(merged_data, latest_mood_per_day[['Day', 'day_only']], on='Day', how='left')

    # Define colors based on mood comparison
    colors = ['#40cf8b' if latest >= weekly else '#ef553b' for weekly, latest in zip(merged_data['mood_weekly_avg'], merged_data['mood_latest_avg'])]

    # Plot the bars
    fig_day_moods = px.bar(
        merged_data, 
        x='Day', 
        y=['mood_weekly_avg', 'mood_latest_avg'], 
        barmode='group',
        title='All-Time Daily Mood Average vs Most Recent Daily Mood by Day of Week',
        color_discrete_sequence=['#636efa', colors]  # Purple tone for long-run, green/red for recent
    )

    # Rename the legend items for clarity
    fig_day_moods.update_traces(
        name="All-Time Average", 
        selector=dict(name="mood_weekly_avg")
    )
    fig_day_moods.update_traces(
        name="Recent Average", 
        selector=dict(name="mood_latest_avg")
    )

    # Update the hover data and layout
    fig_day_moods.update_traces(
        hovertemplate='<b>%{x}</b><br>All-Time Avg: %{customdata[0]:.2f}<br>Recent Avg: %{customdata[1]:.2f} (on %{customdata[2]})',
        customdata=merged_data[['mood_weekly_avg', 'mood_latest_avg', 'day_only']],
    )
    
    return fig_day_moods

def generate_time_of_day_plot(df):
    """Generate the time of day mood plot with conditional color-coding."""
    df['date_only'] = df['date'].dt.date
    
    # Define time-of-day bins with labels showing times
    bins = [0, 9, 12, 16, 20, 24]
    labels = [
        'Early Morning (4 AM - 9 AM)', 
        'Late Morning (9 AM - 12 PM)', 
        'Afternoon (12 PM - 4 PM)', 
        'Evening (4 PM - 8 PM)', 
        'Night (8 PM - 4 AM)'
    ]
    
    # Categorize 'Time of Day' based on bins
    df['Time of Day'] = pd.cut(df['date'].dt.hour, bins=bins, labels=labels, right=False)
    
    # Calculate all-time average mood per time of day
    time_mood_avg = df.groupby('Time of Day', observed=True)['mood'].mean().reset_index()
    
    # Get the latest dates for each 'Time of Day'
    latest_dates = df.groupby('Time of Day', observed=True)['date_only'].max().reset_index()
    
    # Filter to get the most recent mood entries for each time of day
    latest_mood_per_time = pd.merge(df, latest_dates, left_on=['Time of Day', 'date_only'], right_on=['Time of Day', 'date_only'], how='inner')
    latest_mood_avg_per_time = latest_mood_per_time.groupby('Time of Day', observed=True).agg({'mood': 'mean', 'date_only': 'max'}).reset_index()

    # Merge all-time averages with the latest averages
    merged_data = pd.merge(time_mood_avg, latest_mood_avg_per_time, on='Time of Day', how='left', suffixes=('_all_time_avg', '_latest_avg'))
    merged_data['Time of Day'] = pd.Categorical(merged_data['Time of Day'], categories=labels, ordered=True)
    merged_data = merged_data.sort_values('Time of Day')
    
    # Define colors based on mood comparison
    colors = ['#40cf8b' if latest >= all_time else '#ef553b' for all_time, latest in zip(merged_data['mood_all_time_avg'], merged_data['mood_latest_avg'])]

    # Create the bar plot with conditional coloring
    fig_time_moods = px.bar(
        merged_data, 
        x='Time of Day', 
        y=['mood_all_time_avg', 'mood_latest_avg'], 
        barmode='group',
        title='All-Time vs Latest Mood by Time of Day',
        color_discrete_sequence=['#636efa', colors]  # Purple for long-run, green/red for recent
    )

    # Rename the legend items for clarity
    fig_time_moods.update_traces(
        name="All-Time Average", 
        selector=dict(name="mood_all_time_avg")
    )
    fig_time_moods.update_traces(
        name="Recent Average", 
        selector=dict(name="mood_latest_avg")
    )

    # Update hover info to show detailed data including entry date
    fig_time_moods.update_traces(
        hovertemplate='<b>%{x}</b><br>All-Time Avg: %{customdata[0]:.2f}<br>Recent Avg: %{customdata[1]:.2f} (on %{customdata[2]})',
        customdata=merged_data[['mood_all_time_avg', 'mood_latest_avg', 'date_only']]
    )
    
    return fig_time_moods