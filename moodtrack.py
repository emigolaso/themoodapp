from flask import Flask, request, jsonify, render_template, send_from_directory
from utils.data_processing import process_data
from utils.db_operations import insert_data_to_supabase
import os

app = Flask(__name__)

@app.route('/')
def home():
    # Render the main HTML page
    return render_template('index.html')

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


# # Serve static files manually if needed
# @app.route('/<path:filename>')
# def serve_static(filename):
#     return send_from_directory(os.path.abspath('.'), filename)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5009)