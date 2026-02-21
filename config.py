import os
import logging

# Configure logging immediately
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class Config:
    """Dr.R L - Configuration Management"""
    
    # Flask Core Settings
    SECRET_KEY = os.environ.get('SECRET_KEY')
    if not SECRET_KEY:
        logger.warning("SECRET_KEY not set! Using fallback (not secure for production)")
        SECRET_KEY = 'research-agent-2026-fallback-key-change-in-production'
    
    # Groq API Configuration - CRITICAL for the app to work
    GROQ_API_KEY = os.environ.get('GROQ_API_KEY')
    if not GROQ_API_KEY:
        logger.error("❌ GROQ_API_KEY is not set! The search agent will fail.")
        # Don't raise error here - let the app start so we can see the error in logs
        # The DrRLAgent will handle the missing key gracefully
    
    # Application Settings
    MAX_RESULTS_DEFAULT = int(os.environ.get('MAX_RESULTS_DEFAULT', 20))
    REQUEST_TIMEOUT = int(os.environ.get('REQUEST_TIMEOUT', 30))
    
    # Render Deployment Settings
    PORT = int(os.environ.get('PORT', 5000))
    DEBUG = os.environ.get('FLASK_DEBUG', 'False').lower() in ['true', '1', 'yes']
    
    # Security Headers for Production
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # CORS Settings
    CORS_ORIGINS = os.environ.get('CORS_ORIGINS', '*').split(',')
    
    @classmethod
    def validate(cls):
        """Validate critical configuration on startup"""
        errors = []
        
        if not cls.GROQ_API_KEY:
            errors.append("GROQ_API_KEY is missing - set it in Render Environment Variables")
        
        if not cls.SECRET_KEY or 'fallback' in cls.SECRET_KEY:
            errors.append("SECRET_KEY should be changed from default for production")
        
        if errors:
            logger.error("⚠️  Configuration Errors:")
            for error in errors:
                logger.error(f"   - {error}")
            return False
        return True
    
    @classmethod
    def init_app(cls, app):
        """Initialize app with configuration"""
        # Apply configuration to Flask app
        app.config.from_object(cls)
        
        # Validate configuration
        if not cls.validate():
            logger.warning("App starting with configuration errors - expect failures")
        else:
            logger.info("✅ Configuration validated successfully")
        
        return app

# Create config instance for easy importing
config = Config()
