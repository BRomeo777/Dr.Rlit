# Dr.R L - Render Deployment Configuration
# This tells Render how to run your Flask app

web: gunicorn app:app --bind 0.0.0.0:${PORT:-10000} --workers 4 --timeout 120
