import os
import sys
import json
import logging
import traceback
from flask import Flask, render_template, request, jsonify, make_response, after_this_request

# Configure logging immediately
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Try to import your agent
try:
    from dr_r_agent import DrRLAgent
    logger.info("✅ DrRLAgent imported successfully")
    AGENT_AVAILABLE = True
except Exception as e:
    logger.error(f"❌ Failed to import DrRLAgent: {e}")
    DrRLAgent = None
    AGENT_AVAILABLE = False

# Initialize Flask
app = Flask(__name__, template_folder='templates')
app.secret_key = os.environ.get('SECRET_KEY', 'research-agent-2026')

# CRITICAL: Disable Flask HTML error pages
app.config['PROPAGATE_EXCEPTIONS'] = True

# CORS - Add headers to all responses
@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/health')
def health():
    return jsonify({
        'success': True,
        'status': 'healthy',
        'agent_available': AGENT_AVAILABLE,
        'groq_key_set': bool(os.environ.get('GROQ_API_KEY'))
    })

@app.route('/search', methods=['POST', 'OPTIONS'])
def search():
    # Handle CORS preflight
    if request.method == 'OPTIONS':
        response = make_response(jsonify({'success': True}))
        return response
    
    # Check if agent is available
    if not AGENT_AVAILABLE:
        return jsonify({
            'success': False,
            'error': 'Search agent not available. Check server logs.'
        }), 500
    
    try:
        # Get JSON data
        if not request.is_json:
            return jsonify({
                'success': False,
                'error': 'Content-Type must be application/json'
            }), 400
        
        data = request.get_json()
        query = data.get('query', '').strip()
        max_results = data.get('max_results', 20)
        
        if not query:
            return jsonify({
                'success': False,
                'error': 'Query cannot be empty'
            }), 400
        
        logger.info(f"Searching for: {query}")
        
        # Initialize agent and search
        try:
            agent = DrRLAgent()
            results = agent.search(query, max_results=max_results)
        except Exception as e:
            logger.error(f"Agent error: {e}")
            return jsonify({
                'success': False,
                'error': 'Search failed',
                'details': str(e)
            }), 500
        
        return jsonify({
            'success': True,
            'results_count': len(results),
            'results': results
        })
        
    except Exception as e:
        logger.error(f"Search endpoint error: {e}")
        logger.error(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': 'Internal server error',
            'details': str(e)
        }), 500

# CRITICAL: Global error handler - ensures JSON response
@app.errorhandler(Exception)
def handle_exception(e):
    logger.error(f"Unhandled error: {e}")
    logger.error(traceback.format_exc())
    return jsonify({
        'success': False,
        'error': 'Server error',
        'details': str(e)
    }), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
