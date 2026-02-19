import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'research-agent-2026')
    GROQ_API_KEY = os.environ.get('GROQ_API_KEY', '')
    
    # Add any other configuration variables here
    MAX_RESULTS_DEFAULT = 20
    REQUEST_TIMEOUT = 30
