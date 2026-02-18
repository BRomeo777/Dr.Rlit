"""
Dr.R L - Literature Search AI Agent
Flask Web Application
"""

from flask import Flask, render_template, request, jsonify, send_file, session
import os
import json
import time
import hashlib
import logging
from datetime import datetime
from functools import wraps

# Import your Dr.R L search agent (we'll create this next)
# from src.dr_r_agent import DrRLAgent

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Rate limiting storage
request_history = {}

def rate_limit(max_requests=10, window=60):
    """Simple rate limiter decorator"""
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            client_ip = request.remote_addr
            now = time.time()
            
            # Clean old entries
            if client_ip in request_history:
                request_history[client_ip] = [
                    req_time for req_time in request_history[client_ip] 
                    if now - req_time < window
                ]
            else:
                request_history[client_ip] = []
            
            # Check limit
            if len(request_history.get(client_ip, [])) >= max_requests:
                return jsonify({
                    'error': 'Rate limit exceeded. Please wait a minute.'
                }), 429
            
            request_history[client_ip].append(now)
            return f(*args, **kwargs)
        return wrapped
    return decorator

@app.route('/')
def index():
    """Main page - Literature search interface"""
    return render_template('index.html')

@app.route('/search', methods=['POST'])
@rate_limit(max_requests=5, window=60)
def search():
    """Handle literature search requests"""
    try:
        data = request.get_json()
        query = data.get('query', '').strip()
        max_results = min(int(data.get('max_results', 10)), 50)  # Cap at 50
        year_start = data.get('year_start')
        year_end = data.get('year_end')
        
        if not query or len(query) < 3:
            return jsonify({
                'error': 'Please enter a valid search query (min 3 characters)'
            }), 400
        
        # Build year range
        year_range = None
        if year_start and year_end:
            year_range = (int(year_start), int(year_end))
        
        logger.info(f"Search query: {query} | Year range: {year_range}")
        
        # TODO: Initialize DrRLAgent and run search
        # agent = DrRLAgent(base_folder="downloads")
        # results = agent.search(query, max_results=max_results, year_range=year_range)
        
        # Placeholder response for now
        return jsonify({
            'success': True,
            'message': 'Search initiated',
            'query': query,
            'year_range': year_range,
            'max_results': max_results,
            'status': 'processing'
        })
        
    except Exception as e:
        logger.error(f"Search error: {str(e)}")
        return jsonify({
            'error': 'Search failed. Please try again.'
        }), 500

@app.route('/status/<search_id>')
def check_status(search_id):
    """Check search status"""
    # TODO: Implement status checking
    return jsonify({
        'search_id': search_id,
        'status': 'completed',
        'progress': 100
    })

@app.route('/download/<search_id>')
def download_results(search_id):
    """Download search results as ZIP"""
    # TODO: Implement file download
    # zip_path = f"downloads/Search_{search_id}.zip"
    # if os.path.exists(zip_path):
    #     return send_file(zip_path, as_attachment=True)
    return jsonify({'error': 'File not found'}), 404

@app.route('/health')
def health_check():
    """Health check endpoint for Render"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'service': 'Dr.R L - Literature Search'
    })

# Error handlers
@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500

# For local development
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
