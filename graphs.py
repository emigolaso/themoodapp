import pandas as pd
import plotly.express as px
from dash import html
from flask_caching import Cache
import os

# Initialize Cache with Redis directly in this file
cache = Cache()

def init_cache(app):
    """Initialize Redis cache for the given Flask app."""
    app.config['CACHE_TYPE'] = 'RedisCache'
    app.config['CACHE_REDIS_URL'] = os.getenv('REDIS_URL')
    cache.init_app(app)

# Load data from Supabase with cache
@cache.cached(timeout=86400, key_prefix='supabase_data_cache')  # Cache for 24 hours
def load_data(supabase, SUPABASE_DB):
    """Function to load data from Supabase."""
    response = supabase.table(f'{SUPABASE_DB}').select('id, date, mood, description').execute()
    data = response.data
    df = pd.DataFrame(data)
    df['date'] = pd.to_datetime(df['date'])
    return df

# Generate all graphs and stats with cache
@cache.cached(timeout=86400, key_prefix='graphs_cache')  # Cache for 24 hours
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

def generate_monthly_mood_plot(df):
    """Generate the monthly mood plot."""
    df['Month Start'] = df['date'].dt.to_period('M').dt.to_timestamp()
    monthly_mood_avg = df.groupby('Month Start')['mood'].mean().reset_index()
    fig_monthly_moods = px.bar(monthly_mood_avg, x='Month Start', y='mood', title='Average Mood by Month Start Date')

    # Prepare tick values and labels for months
    tick_vals = monthly_mood_avg['Month Start']
    tick_text = monthly_mood_avg['Month Start'].dt.strftime('%Y-%m')

    fig_monthly_moods.update_xaxes(
        tickmode='array',
        tickvals=tick_vals,
        ticktext=tick_text
    )
    return fig_monthly_moods

def generate_weekly_mood_plot(df):
    """Generate the weekly mood plot."""
    df['Week Start'] = (df['date'] - pd.to_timedelta(df['date'].dt.weekday, unit='d')).dt.date
    weekly_mood_avg = df.groupby('Week Start')['mood'].mean().reset_index()
    fig_weekly_moods = px.bar(weekly_mood_avg, x='Week Start', y='mood', title='Average Mood by Week')

    # Prepare tick values and labels
    tick_vals = weekly_mood_avg['Week Start']
    tick_text = weekly_mood_avg['Week Start']

    fig_weekly_moods.update_xaxes(
        tickmode='array',
        tickvals=tick_vals,
        ticktext=tick_text
    )
    return fig_weekly_moods

def generate_day_of_week_plot(df):
    """Generate the day of the week mood plot."""
    df['day_only'] = df['date'].dt.date
    df['Day'] = df['day_only'].apply(lambda x: x.strftime('%A'))

    day_mood_avg = df.groupby('Day')['mood'].mean().reset_index()
    day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    day_mood_avg['Day'] = pd.Categorical(day_mood_avg['Day'], categories=day_order, ordered=True)

    df_sorted = df.sort_values('date', ascending=False)
    latest_mood_per_day = df_sorted.groupby('Day').head(1)
    daily_mood_avg_recent = df[df['day_only'].isin(latest_mood_per_day['day_only'])].groupby(['Day'])['mood'].mean().reset_index()

    merged_data = pd.merge(day_mood_avg, daily_mood_avg_recent, on='Day', how='left', suffixes=('_weekly_avg', '_latest_avg'))
    merged_data['Day'] = pd.Categorical(merged_data['Day'], categories=day_order, ordered=True)
    merged_data = merged_data.sort_values('Day')
    merged_data = pd.merge(merged_data, latest_mood_per_day[['Day', 'day_only']], on='Day', how='left')

    fig_day_moods = px.bar(merged_data, 
                 x='Day', 
                 y=['mood_weekly_avg', 'mood_latest_avg'], 
                 barmode='group',
                 title='All-Time Daily Mood Average vs Most Recent Daily Mood by Day of Week')

    fig_day_moods.update_traces(
        hovertemplate='<b>%{x}</b><br>All-Time Avg: %{customdata[0]:.2f}<br>Recent Avg: %{customdata[1]:.2f} (on %{customdata[2]})',
        customdata=merged_data[['mood_weekly_avg', 'mood_latest_avg', 'day_only']]
    )
    return fig_day_moods

def generate_time_of_day_plot(df):
    """Generate the time of day mood plot."""
    df['date_only'] = df['date'].dt.date
    df['Time of Day'] = pd.cut(df['date'].dt.hour, bins=[0, 12, 18, 24], labels=['Morning', 'Afternoon', 'Evening'], right=False)

    time_mood_avg = df.groupby('Time of Day', observed=True)['mood'].mean().reset_index()
    latest_dates = df.groupby('Time of Day', observed=True)['date_only'].max().reset_index()

    latest_mood_per_time = pd.merge(df, latest_dates, left_on=['Time of Day', 'date_only'], right_on=['Time of Day', 'date_only'], how='inner')
    latest_mood_avg_per_time = latest_mood_per_time.groupby('Time of Day', observed=True).agg({'mood': 'mean', 'date_only': 'max'}).reset_index()

    merged_data = pd.merge(time_mood_avg, latest_mood_avg_per_time, on='Time of Day', how='left', suffixes=('_all_time_avg', '_latest_avg'))
    merged_data['latest_avg_with_date'] = merged_data.apply(lambda row: f"{row['mood_latest_avg']:.2f} (on {row['date_only']})", axis=1)

    fig_time_moods = px.bar(
        merged_data, 
        x='Time of Day', 
        y=['mood_all_time_avg', 'mood_latest_avg'], 
        barmode='group',
        title='All-Time vs Latest Mood by Time of Day'
    )

    fig_time_moods.update_traces(
        hovertemplate='<b>%{x}</b><br>All-Time Avg: %{customdata[0]:.2f}<br>Latest Avg: %{customdata[1]}',
        customdata=merged_data[['mood_all_time_avg', 'latest_avg_with_date']]
    )
    return fig_time_moods