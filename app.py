import os
import sys
import json
import logging
import traceback
from flask import Flask, request, jsonify, make_response, render_template_string

# IMMEDIATE LOGGING
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
logger.info("🚀 APP STARTING - VERY FIRST LINE")

app = Flask(__name__)

# CRITICAL: Catch ALL errors and return JSON
@app.errorhandler(Exception)
def handle_all_errors(error):
    logger.error(f"UNHANDLED ERROR: {error}")
    logger.error(traceback.format_exc())
    return make_response(jsonify({
        'success': False,
        'error': str(error),
        'type': type(error).__name__,
        'traceback': traceback.format_exc()
    }), 500)

@app.route('/')
def index():
    return render_template_string("""
    <!DOCTYPE html>
    <html>
    <head><title>Dr.R L Test</title></head>
    <body>
        <h1>Dr.R L - Test Page</h1>
        <div id="status">Testing API...</div>
        <pre id="result"></pre>
        
        <script>
            // Test API immediately
            fetch('/health', {
                method: 'GET',
                headers: {'Accept': 'application/json'}
            })
            .then(r => r.json())
            .then(data => {
                document.getElementById('status').innerText = 'API OK';
                document.getElementById('result').innerText = JSON.stringify(data, null, 2);
            })
            .catch(e => {
                document.getElementById('status').innerText = 'API FAILED';
                document.getElementById('result').innerText = e.toString();
            });
        </script>
    </body>
    </html>
    """)

@app.route('/health')
def health():
    logger.info("Health check called")
    return jsonify({'success': True, 'status': 'healthy'})

@app.route('/search', methods=['POST', 'OPTIONS'])
def search():
    logger.info(f"Search called with method {request.method}")
    
    if request.method == 'OPTIONS':
        response = make_response(jsonify({'success': True}))
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
        response.headers.add('Access-Control-Allow-Methods', 'POST, OPTIONS')
        return response
    
    try:
        data = request.get_json(force=True, silent=True) or {}
        query = data.get('query', 'test')
        
        return jsonify({
            'success': True,
            'query': query,
            'results': [{'title': 'Test Result', 'source': 'test'}]
        })
    except Exception as e:
        logger.error(f"Search error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
