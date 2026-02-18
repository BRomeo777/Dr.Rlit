"""
Dr.R L - Configuration Settings
Environment variables and app configuration
"""

import os
from datetime import timedelta


class Config:
    """Base configuration"""
    
    # Flask settings
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    DEBUG = False
    TESTING = False
    
    # File paths
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    DOWNLOAD_FOLDER = os.path.join(BASE_DIR, 'downloads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max upload
    
    # Search settings
    DEFAULT_MAX_RESULTS = 20
    MAX_MAX_RESULTS = 50
    MIN_REQUEST_INTERVAL = 1.0  # seconds between API calls
    SEARCH_TIMEOUT = 300  # 5 minutes max search time
    
    # Rate limiting
    RATE_LIMIT_REQUESTS = 5
    RATE_LIMIT_WINDOW = 60  # seconds
    
    # API Keys (load from environment)
    API_KEYS = {
        'core': os.environ.get('CORE_API_KEY', ''),
        'semantic_scholar': os.environ.get('SEMANTIC_SCHOLAR_API_KEY', ''),
        'lens': os.environ.get('LENS_API_KEY', ''),
        'email': os.environ.get('CONTACT_EMAIL', 'researcher@example.com')
    }
    
    # Logging
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'


class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    LOG_LEVEL = 'DEBUG'


class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    
    # Stricter rate limiting in production
    RATE_LIMIT_REQUESTS = 3
    RATE_LIMIT_WINDOW = 60


class TestingConfig(Config):
    """Testing configuration"""
    TESTING = True
    DEBUG = True
    DOWNLOAD_FOLDER = '/tmp/dr_r_test_downloads'


# Config dictionary
config_by_name = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}


def get_config():
    """Get configuration based on environment"""
    env = os.environ.get('FLASK_ENV', 'development')
    return config_by_name.get(env, DevelopmentConfig)


# Create download folder if not exists
def init_app(app):
    """Initialize app with configuration"""
    config = get_config()
    
    # Ensure download folder exists
    os.makedirs(config.DOWNLOAD_FOLDER, exist_ok=True)
    
    # Set log level
    import logging
    logging.basicConfig(
        level=getattr(logging, config.LOG_LEVEL),
        format=config.LOG_FORMAT
    )
    
    return config
