from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import os
import sys
import traceback
import logging

# Add the current directory to Python path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Use relative import for the package
from dr_r_agent import DrRLAgent

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'research-agent-2026')

# CORS configuration - more permissive for debugging
CORS(app, resources={
    r"/api/*": {
        "origins": "*",
        "methods": ["POST", "OPTIONS", "GET"],
        "allow_headers": ["Content-Type", "Authorization"]
    },
    r"/search": {
        "origins": "*",
        "methods": ["POST", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"]
    }
})

def is_api_request():
    """Check if current request expects JSON response"""
    return request.path.startswith('/search') or request.path.startswith('/api/')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/search', methods=['POST', 'OPTIONS'])
def search():
    # Handle preflight OPTIONS request
    if request.method == 'OPTIONS':
        response = jsonify({'success': True})
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
        response.headers.add('Access-Control-Allow-Methods', 'POST,OPTIONS')
        return response, 200
    
    try:
        # Ensure we have JSON content type
        if not request.is_json:
            logger.error(f"Content-Type is {request.content_type}, expected application/json")
            return jsonify({
                'success': False, 
                'error': 'Content-Type must be application/json',
                'received_content_type': request.content_type
            }), 400
        
        data = request.get_json(silent=True)
        if data is None:
            logger.error("Failed to parse JSON data")
            return jsonify({
                'success': False, 
                'error': 'Invalid JSON data'
            }), 400
            
        query = data.get('query', '').strip()
        max_results = data.get('max_results', 20)
        
        if not query:
            return jsonify({
                'success': False, 
                'error': 'Query cannot be empty'
            }), 400
        
        logger.info(f"Searching for: {query}")
        
        # Initialize agent with error handling
        try:
            agent = DrRLAgent()
        except Exception as agent_error:
            logger.error(f"Failed to initialize agent: {str(agent_error)}")
            return jsonify({
                'success': False,
                'error': 'Failed to initialize search agent',
                'details': str(agent_error)
            }), 500
        
        # Perform search
        results = agent.search(query, max_results=max_results)
        
        logger.info(f"Search completed, found {len(results)} results")
        
        # Return valid JSON
        response = jsonify({
            'success': True,
            'results': results
        })
        response.headers.add('Access-Control-Allow-Origin', '*')
        return response
        
    except Exception as e:
        logger.error(f"Search error: {str(e)}")
        logger.error(traceback.format_exc())
        
        # Always return JSON, never HTML
        return jsonify({
            'success': False, 
            'error': 'Internal Server Error',
            'details': str(e),
            'traceback': traceback.format_exc() if app.debug else None
        }), 500

# Global error handlers - ensure JSON responses for API routes
@app.errorhandler(404)
def not_found(error):
    if is_api_request():
        return jsonify({
            'success': False,
            'error': 'Endpoint not found',
            'path': request.path,
            'method': request.method
        }), 404
    return render_template('index.html'), 404

@app.errorhandler(405)
def method_not_allowed(error):
    """Handle wrong HTTP methods (e.g., GET instead of POST)"""
    if is_api_request():
        return jsonify({
            'success': False,
            'error': 'Method not allowed',
            'allowed_methods': error.description if hasattr(error, 'description') else 'Check API documentation',
            'your_method': request.method,
            'path': request.path
        }), 405
    return render_template('index.html'), 405

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"500 error: {str(error)}")
    if is_api_request():
        return jsonify({
            'success': False,
            'error': 'Internal server error',
            'details': str(error)
        }), 500
    return render_template('index.html'), 500

@app.errorhandler(Exception)
def handle_exception(error):
    logger.error(f"Unhandled exception: {str(error)}")
    if is_api_request():
        return jsonify({
            'success': False,
            'error': 'Unexpected error',
            'details': str(error)
        }), 500
    return render_template('index.html'), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    # NEVER enable debug mode in production - it returns HTML error pages with stack traces
    debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    app.run(host='0.0.0.0', port=port, debug=debug_mode)
