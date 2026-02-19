from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import os
from dr_r_agent import DrRLAgent

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'research-agent-2026')

# This is the "Security Guard" that allows data to flow to your browser
CORS(app)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/search', methods=['POST'])
def search():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data received'}), 400
            
        query = data.get('query', '').strip()
        max_results = data.get('max_results', 20)
        
        # Start the Agent
        agent = DrRLAgent()
        results = agent.search(query, max_results=max_results)
        
        # Return valid JSON
        return jsonify({
            'success': True,
            'results': results
        })
        
    except Exception as e:
        # If the server crashes, it sends this JSON instead of an HTML error page
        return jsonify({
            'success': False, 
            'error': 'Internal Server Error',
            'details': str(e)
        }), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
