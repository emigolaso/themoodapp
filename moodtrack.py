# Standard library imports
import os
import time
from datetime import datetime, timezone
from functools import wraps

# Third-party library imports
import pandas as pd
import pytz
import plotly.express as px
import markdown
from flask import (
    Flask, request, jsonify, render_template,
    send_from_directory, g, session, redirect, url_for, flash
)
from flask_caching import Cache
from dash import Dash, dcc, html
from supabase import create_client, Client

# Local imports
from utils.supabase_utils import insert_data_to_supabase
from utils.supabase_storage_utils import download_summary_from_supabase
from graphs import load_data, generate_all_graphs, init_cache


# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.urandom(24)  # This generates a random secret key

# Initialize Redis cache
init_cache(app)

# Initialize SUPABASE for Auth and Setup the Dash app and plots
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_API_KEY = os.getenv('SUPABASE_API_KEY')
SUPABASE_DB = os.getenv('SUPABASE_DB')
supabase: Client = create_client(SUPABASE_URL, SUPABASE_API_KEY)


# Create a login-required decorator
def login_required(f):
    @wraps(f)
    def check_login(*args, **kwargs):
        if 'user_email' not in session:  # Check if the user is logged in
            flash('Please log in to access this page', 'error')
            return redirect(url_for('login_page'))  # Redirect to login page if not logged in
        return f(*args, **kwargs)
    return check_login

# Route to serve the login form
@app.route('/login_page', methods=['GET'])
def login_page():
    # Check if signup was successful by checking the session variable
    if session.pop('signup_success', None):  # Clear session after checking
        flash('Signup successful, please login', 'success')  # Flash success message after signup

    return render_template('login.html')  # Render the login page

@app.route('/login', methods=['POST'])
def login():
    # Check if the request is JSON or form data
    if request.content_type == 'application/json':
        data = request.json
        email = data.get('email')
        password = data.get('password')
    else:
        email = request.form.get('email')
        password = request.form.get('password')

    if not email or not password:
        flash('Email and password are required', 'error')  # Flash error message
        return redirect(url_for('login_page'))

    try:
        # Perform authentication with the provided email and password
        response = supabase.auth.sign_in_with_password({
            'email': email,
            'password': password,
        })
        # On successful login, Capture UUID and store user info in session
        session['user_email'] = email
        session['user_uuid'] = response.user.id  # Store the UUID
        return redirect(url_for('index'))  # Redirect to the index page
    
    except Exception as e:
        flash('Invalid login credentials, try again', 'error')  # Flash error message
        return redirect(url_for('login_page'))  # Redirect back to login page


# Before each request, set g.user_uuid (global variable for user_uuid)
@app.before_request
def before_request():
    g.user_uuid = session.get("user_uuid")

@app.route('/logout')
def logout():
    session.pop('user_email', None)  # Remove user data from the session
    session.pop('user_uuid', None)
    return redirect(url_for('login_page'))  # Redirect to the login page after logging out


# Route to serve the signup form
@app.route('/signup_page', methods=['GET'])
def signup_page():
    return render_template('signup.html')  # This will serve the signup form page


# Sign up route
@app.route('/signup', methods=['POST'])
def signup():
    # Check if the request is JSON or form data
    if request.content_type == 'application/json':
        data = request.json
        email = data.get('email')
        password = data.get('password')
    else:
        email = request.form.get('email')
        password = request.form.get('password')

    if not email or not password:
        flash('Email and password are required', 'error')
        return redirect(url_for('signup_page'))

    try:
        response = supabase.auth.sign_up({
            'email': email,
            'password': password,
        })
        
        # Check if the user already exists by analyzing the response from Supabase
        if 'error' in response:
            flash(response['error']['message'], 'error')
            return redirect(url_for('signup_page'))

        # If signup is successful,set sucess session flag
        session['signup_success'] = True  # Set session variable for success

        # Simulate a delay for 3 seconds (you could also use time.sleep here)
        return redirect(url_for('login_page'))

    except Exception as e:
        flash(str(e), 'error')  # Flash the error message
        return redirect(url_for('signup_page'))

# Setting timezone
@app.route('/set_timezone', methods=['POST'])
def set_timezone():
    try:
        data = request.json
        timezone = data.get('timezone', 'UTC')  # Default to UTC if not provided
        session['timezone'] = timezone  # Store in session
        print(f"Timezone stored in session: {session.get('timezone')}")
        return jsonify({"message": "Timezone set successfully"}), 200
    except Exception as e:
        return jsonify({"message": "Failed to set timezone", "error": str(e)}), 400


# Route for the existing main page (index.html)
@app.route('/')
@login_required
def index():
    # Check if the user is in the session
    if 'user_email' not in session:
        return redirect(url_for('login_page'))  # Redirect to login page if not logged in

    # Get the user's timezone from the session, default to UTC
    user_timezone = session.get('timezone', 'UTC')

    # Convert the current date to the user's timezone
    try:
        current_date = datetime.now(pytz.timezone(user_timezone)).date()
    except Exception as e:
        print(f"Error with timezone conversion: {e}")
        current_date = datetime.utcnow().date()  # Fallback to UTC

    # Calculate the last full week's Monday
    current_date = pd.to_datetime(current_date)
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
        data = request.json
        mood = data.get('mood')  # Capturing the mood from the slider
        description = data.get('description')  # Capturing the description
        tzone = data.get('timezone')
        
        if not mood or not description:
            return jsonify({'message': 'Mood and description must be provided'}), 400 

        print(f"Received Timezone: {tzone}")

        # Get user UUID from session
        user_uuid = session.get('user_uuid')
        if not user_uuid: return jsonify({'message': 'User not authenticated'}), 403


        # Combine the mood and description into a formatted structure (if necessary for DB storage)
        formatted_data = {
            'mood': mood,
            'description': description,
            'timezone': tzone,
            'user_uuid': user_uuid
        }

        success = insert_data_to_supabase(formatted_data)
        if not success:
            return jsonify({'message': 'Failed to insert data into Supabase.'}), 500

         # Clear cache specifically for this user's data
        from graphs import cache  # Import cache
        cache.delete(f'supabase_data_cache_{user_uuid}')
        cache.delete(f'graphs_cache_{user_uuid}')
        
        return jsonify({'message': 'Data inserted successfully!'})
    
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'message': 'An error occurred'}), 500


    
# Route for getting weekly summaries
@app.route('/weekly-summary')
@login_required
def display_weekly_summary():
    # Download the file from Supabase 
    user_uuid = session.get('user_uuid')
    weekly_summary_content = download_summary_from_supabase('weekly', user_uuid)
    # Convert the weekly summary content from Markdown to HTML
    weekly_summary_html = markdown.markdown(weekly_summary_content)
    
    return render_template('weekly_summary.html', summary=weekly_summary_html)


@app.route('/daily-summary')
@login_required
def display_daily_summary():
    # Download the daily summary file from Supabase
    user_uuid = session.get('user_uuid')
    daily_summary_content = download_summary_from_supabase('daily', user_uuid)

    # Convert the daily summary content from Markdown to HTML
    daily_summary_html = markdown.markdown(daily_summary_content)

    return render_template('daily_summary.html', summary=daily_summary_html)


# Dashboard routes
@app.route('/dashboard/')
@login_required
def render_dashboard():
    print("Inside render_dashboard")  # Debug line
    user_uuid = session.get('user_uuid')
    print(f"User UUID in session: {user_uuid}")  # Debug line
    if not g.user_uuid:
        return redirect(url_for('login_page'))  # Redirect to login if UUID is missing

     # Call generate_dashboard_layout to get the actual layout and assign it to dash_app.layout
    dash_app.layout = generate_dashboard_layout()
    
    # Directly return the layout rendered by Dash, without a redirect
    return dash_app.index()  # Render the Dash app's layout directly


# Initialize Dash app within Flask
dash_app = Dash(__name__, server=app, url_base_pathname='/dashboard/')

def generate_dashboard_layout():
    print(f"Generating dashboard for user UUID: {g.user_uuid}")
    # Load the data for graph generation and generate cached graphs
    df = load_data(supabase, SUPABASE_DB)
    summary_stats, fig_monthly_moods, fig_weekly_moods, fig_day_moods, fig_time_moods = generate_all_graphs(df)
    
    # Return the updated layout with the latest figures
    return html.Div(children=[
        html.H1(children='Mood Tracking Dashboard'),
        summary_stats,
        dcc.Graph(id='monthly-moods', figure=fig_monthly_moods),
        dcc.Graph(id='weekly-moods', figure=fig_weekly_moods),
        dcc.Graph(id='day-of-week-moods', figure=fig_day_moods),
        dcc.Graph(id='time-of-day-moods', figure=fig_time_moods),
    ])

dash_app.layout =  html.Div("Loading...") 

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5009))
    app.run(host='0.0.0.0', port=port, debug=True)