app_code = '''
from flask import Flask, render_template, request, jsonify, send_file
import os
import logging
from datetime import datetime
# Import the agent from your other file
from dr_r_agent import DrRLAgent

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'gastric-cancer-research-key')

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Ensure a download folder exists
DOWNLOAD_FOLDER = "downloads"
if not os.path.exists(DOWNLOAD_FOLDER):
    os.makedirs(DOWNLOAD_FOLDER)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/search', methods=['POST'])
def search():
    try:
        data = request.get_json()
        query = data.get('query', '').strip()
        max_results = int(data.get('max_results', 10))
        
        # Capture year range for clinical specificity
        year_start = data.get('year_start')
        year_end = data.get('year_end')
        year_range = (int(year_start), int(year_end)) if year_start and year_end else None

        if not query:
            return jsonify({'error': 'Please enter a search term'}), 400

        logger.info(f"Starting Gastric Cancer Search: {query}")

        # Initialize the actual Agent you wrote
        agent = DrRLAgent(base_folder=DOWNLOAD_FOLDER)
        
        # This triggers the search across 17+ databases
        download_link = agent.search(query, max_results=max_results, year_range=year_range)

        if download_link:
            return jsonify({
                'success': True,
                'message': 'Search complete!',
                'download_url': download_link
            })
        else:
            return jsonify({'error': 'No papers found for this query.'}), 404

    except Exception as e:
        logger.error(f"Critical Error: {str(e)}")
        return jsonify({'error': 'Server error during search'}), 500

@app.route('/health')
def health_check():
    return jsonify({'status': 'healthy', 'service': 'Dr.R L Agent'})

if __name__ == '__main__':
    app.run(debug=True)
'''
