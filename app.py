from flask import Flask, render_template, request, jsonify
import os
from dr_r_agent import DrRLAgent

# THIS IS THE LINE RENDER IS LOOKING FOR:
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'gastric-cancer-research')

@app.route('/')
def index():
    return "Dr. R L - Gastric Cancer Search Agent is Live!"

@app.route('/health')
def health():
    return jsonify({"status": "healthy"})

# This part handles the search
@app.route('/search', methods=['POST'])
def search():
    data = request.get_json()
    query = data.get('query', '')
    agent = DrRLAgent()
    results = agent.search(query)
    return jsonify({"results": results})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=os.environ.get('PORT', 5000))
