from flask import Flask, render_template, request, jsonify, send_file
from flask_cors import CORS
import os
import logging
import traceback
import json
from dr_r_agent import DrRLAgent

# Initialize Flask
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'gastric-cancer-research-2026')

# Enable CORS for all routes (important for Google Colab frontend)
CORS(app, resources={
    r"/*": {
        "origins": "*",
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"]
    }
})

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/search', methods=['POST', 'OPTIONS'])
def search():
    # Handle preflight OPTIONS request
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200
    
    try:
        # Check if request has JSON content
        if not request.is_json:
            return jsonify({
                'success': False, 
                'error': 'Content-Type must be application/json'
            }), 400

        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False, 
                'error': 'No JSON data received'
            }), 400
            
        query = data.get('query', '').strip()
        
        if not query:
            return jsonify({
                'success': False, 
                'error': 'No query provided'
            }), 400

        # Optional parameters
        max_results = data.get('max_results', 20)
        year_range = data.get('year_range', None)
        
        logger.info(f"Search initiated for: {query} (max_results={max_results})")
        
        # Initialize AI Agent
        try:
            agent = DrRLAgent()
        except Exception as agent_error:
            logger.error(f"Failed to initialize agent: {str(agent_error)}")
            return jsonify({
                'success': False,
                'error': 'Failed to initialize search agent',
                'details': str(agent_error)
            }), 500
        
        # Perform the search
        try:
            results = agent.search(query, max_results=max_results, year_range=year_range)
        except Exception as search_error:
            logger.error(f"Search execution failed: {str(search_error)}")
            return jsonify({
                'success': False,
                'error': 'Search execution failed',
                'details': str(search_error)
            }), 500
        
        # Handle case where no results found
        if results is None:
            return jsonify({
                'success': True,
                'results': None,
                'message': 'No papers found for this query'
            })
        
        # Ensure results is JSON serializable
        try:
            # Test JSON serialization
            json.dumps(results)
        except (TypeError, ValueError) as json_error:
            logger.error(f"Results not JSON serializable: {str(json_error)}")
            return jsonify({
                'success': False,
                'error': 'Internal error: invalid result format'
            }), 500
        
        logger.info(f"Search completed successfully. Found {results.get('total_papers', 0)} papers")
        
        return jsonify({
            'success': True,
            'results': results
        })
        
    except Exception as e:
        logger.error(f"Unexpected error in search route: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': 'Internal server error',
            'details': str(e),
            'traceback': traceback.format_exc() if app.debug else None
        }), 500


@app.route('/download/<session_id>', methods=['GET'])
def download_results(session_id):
    """Download the ZIP file for a search session"""
    try:
        import glob
        
        # Find the zip file
        zip_pattern = f"downloads/Search_{session_id}/*.zip"
        zip_files = glob.glob(zip_pattern)
        
        if not zip_files:
            return jsonify({
                'success': False,
                'error': 'File not found'
            }), 404
            
        zip_path = zip_files[0]
        
        return send_file(
            zip_path,
            mimetype='application/zip',
            as_attachment=True,
            download_name=f"DrR_Results_{session_id}.zip"
        )
        
    except Exception as e:
        logger.error(f"Download failed: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Download failed',
            'details': str(e)
        }), 500


@app.route('/health')
def health():
    return jsonify({
        "status": "healthy",
        "agent": "Dr.R L - Literature Search AI",
        "version": "2.0"
    }), 200


@app.errorhandler(404)
def not_found(error):
    return jsonify({
        'success': False,
        'error': 'Endpoint not found'
    }), 404


@app.errorhandler(500)
def internal_error(error):
    return jsonify({
        'success': False,
        'error': 'Internal server error'
    }), 500


if __name__ == '__main__':
    # Render provides a PORT environment variable
    port = int(os.environ.get('PORT', 5000))
    # Set debug to False in production
    debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    app.run(host='0.0.0.0', port=port, debug=debug_mode)
