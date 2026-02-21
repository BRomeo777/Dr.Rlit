import os
import sys
import traceback
import logging

# CRITICAL: Add current directory to path BEFORE any other imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Configure logging IMMEDIATELY
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Wrap ALL imports in try-except to catch startup errors
try:
    from flask import Flask, render_template, request, jsonify, make_response
    from flask_cors import CORS
    logger.info("✅ Flask imports successful")
except ImportError as e:
    logger.error(f"❌ Failed to import Flask: {e}")
    # Create minimal app to show error
    class MinimalApp:
        def __call__(self, environ, start_response):
            status = '500 Internal Server Error'
            headers = [('Content-type', 'application/json')]
            start_response(status, headers)
            return [b'{"success": false, "error": "Flask not installed"}']
    app = MinimalApp()
    raise

# Try to import DrRLAgent with fallback
try:
    from dr_r_agent import DrRLAgent
    logger.info("✅ DrRLAgent imported successfully")
except ImportError as e:
    logger.error(f"❌ Failed to import DrRLAgent: {e}")
    DrRLAgent = None

# Initialize Flask app
app = Flask(__name__)

# Configuration with validation
app.secret_key = os.environ.get('SECRET_KEY', 'research-agent-2026-fallback')

# CRITICAL: Disable Flask default HTML error pages
app.config['PROPAGATE_EXCEPTIONS'] = True
app.config['TRAP_HTTP_EXCEPTIONS'] = True

# CORS configuration - MUST be before routes
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
}, supports_credentials=True)

def is_api_request():
    """Check if current request expects JSON response"""
    return request.path.startswith('/search') or request.path.startswith('/api/')

def create_json_response(data, status_code=200):
    """Ensure ALL responses are valid JSON with proper headers"""
    response = make_response(jsonify(data), status_code)
    response.headers['Content-Type'] = 'application/json'
    response.headers['Access-Control-Allow-Origin'] = '*'
    return response

# Health check endpoint - CRITICAL for Render
@app.route('/health')
def health_check():
    """Health check for Render monitoring"""
    return create_json_response({
        'success': True,
        'status': 'healthy',
        'agent_available': DrRLAgent is not None,
        'groq_key_set': bool(os.environ.get('GROQ_API_KEY'))
    })

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/search', methods=['POST', 'OPTIONS'])
def search():
    # Handle preflight OPTIONS request
    if request.method == 'OPTIONS':
        response = create_json_response({'success': True})
        return response, 200
    
    # Check if agent is available
    if DrRLAgent is None:
        logger.error("DrRLAgent not available - import failed")
        return create_json_response({
            'success': False,
            'error': 'Search agent not available',
            'details': 'Failed to import DrRLAgent module'
        }), 500
    
    try:
        # Ensure we have JSON content type
        if not request.is_json:
            logger.error(f"Content-Type is {request.content_type}, expected application/json")
            return create_json_response({
                'success': False, 
                'error': 'Content-Type must be application/json',
                'received_content_type': request.content_type
            }), 400
        
        data = request.get_json(silent=True)
        if data is None:
            logger.error("Failed to parse JSON data")
            return create_json_response({
                'success': False, 
                'error': 'Invalid JSON data'
            }), 400
            
        query = data.get('query', '').strip()
        max_results = data.get('max_results', 20)
        
        if not query:
            return create_json_response({
                'success': False, 
                'error': 'Query cannot be empty'
            }), 400
        
        logger.info(f"Searching for: {query}")
        
        # Initialize agent with error handling
        try:
            agent = DrRLAgent()
        except Exception as agent_error:
            logger.error(f"Failed to initialize agent: {str(agent_error)}")
            return create_json_response({
                'success': False,
                'error': 'Failed to initialize search agent',
                'details': str(agent_error)
            }), 500
        
        # Perform search
        results = agent.search(query, max_results=max_results)
        
        logger.info(f"Search completed, found {len(results)} results")
        
        return create_json_response({
            'success': True,
            'results': results
        })
        
    except Exception as e:
        logger.error(f"Search error: {str(e)}")
        logger.error(traceback.format_exc())
        
        return create_json_response({
            'success': False, 
            'error': 'Internal Server Error',
            'details': str(e),
            'traceback': traceback.format_exc() if app.debug else None
        }), 500

# Global error handlers - MUST return JSON for API routes
@app.errorhandler(404)
def not_found(error):
    if is_api_request():
        return create_json_response({
            'success': False,
            'error': 'Endpoint not found',
            'path': request.path,
            'method': request.method
        }), 404
    return render_template('index.html'), 404

@app.errorhandler(405)
def method_not_allowed(error):
    if is_api_request():
        return create_json_response({
            'success': False,
            'error': 'Method not allowed',
            'your_method': request.method,
            'path': request.path
        }), 405
    return render_template('index.html'), 405

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"500 error: {str(error)}")
    if is_api_request():
        return create_json_response({
            'success': False,
            'error': 'Internal server error',
            'details': str(error)
        }), 500
    return render_template('index.html'), 500

@app.errorhandler(Exception)
def handle_exception(error):
    logger.error(f"Unhandled exception: {str(error)}")
    logger.error(traceback.format_exc())
    if is_api_request():
        return create_json_response({
            'success': False,
            'error': 'Unexpected error',
            'details': str(error)
        }), 500
    return render_template('index.html'), 500

# Startup logging
logger.info(f"🚀 App initialized successfully")
logger.info(f"   - Debug mode: {app.debug}")
logger.info(f"   - Agent available: {DrRLAgent is not None}")
logger.info(f"   - Groq API Key set: {bool(os.environ.get('GROQ_API_KEY'))}")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    # NEVER enable debug in production - it shows HTML stack traces
    debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    app.run(host='0.0.0.0', port=port, debug=debug_mode)
