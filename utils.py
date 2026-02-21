import json
import time
import logging
import functools
from typing import Any, Dict, List, Tuple, Optional

logger = logging.getLogger(__name__)

# Rate limiting storage (simple in-memory, resets on restart)
_rate_limit_storage = {}

def safe_json_response(data: Dict[str, Any], status_code: int = 200) -> Tuple[str, int, Dict[str, str]]:
    """
    Ensure we always return valid JSON, never HTML.
    Returns tuple: (json_string, status_code, headers)
    """
    try:
        # Ensure data is dict
        if not isinstance(data, dict):
            data = {'data': data}
        
        # Add timestamp
        data['timestamp'] = time.time()
        
        json_string = json.dumps(data, ensure_ascii=False, default=str)
        headers = {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Content-Type,Authorization',
            'X-Content-Type-Options': 'nosniff'
        }
        return json_string, status_code, headers
        
    except Exception as e:
        logger.error(f"JSON serialization error: {e}")
        error_response = json.dumps({
            'success': False,
            'error': 'JSON serialization failed',
            'details': str(e),
            'timestamp': time.time()
        }, ensure_ascii=False)
        return error_response, 500, {'Content-Type': 'application/json'}

def validate_search_query(query: Any) -> Tuple[bool, Optional[str]]:
    """
    Validate search query input.
    Returns: (is_valid, error_message)
    """
    if query is None:
        return False, "Query is required"
    
    if not isinstance(query, str):
        return False, "Query must be a string"
    
    stripped = query.strip()
    if len(stripped) == 0:
        return False, "Query cannot be empty"
    
    if len(query) > 1000:
        return False, "Query too long (max 1000 characters)"
    
    # Check for potentially dangerous characters (basic SQL injection prevention)
    dangerous = [';', '--', '/*', '*/', 'DROP', 'DELETE', 'INSERT', 'UPDATE']
    upper_query = query.upper()
    for char in dangerous:
        if char in upper_query:
            logger.warning(f"Potentially dangerous query detected: {query[:50]}...")
            return False, "Query contains invalid characters"
    
    return True, None

def format_search_results(results: Any) -> List[Dict[str, Any]]:
    """
    Ensure results are JSON serializable.
    Handles datetime, custom objects, nested structures.
    """
    if results is None:
        return []
    
    if not isinstance(results, list):
        results = [results]
    
    formatted = []
    
    for item in results:
        if not isinstance(item, dict):
            # Convert non-dict items
            formatted.append({
                'data': str(item),
                'type': type(item).__name__
            })
            continue
        
        # Clean dict item
        clean_item = {}
        for key, value in item.items():
            # Skip None keys
            if key is None:
                continue
            
            key_str = str(key)
            
            # Handle different value types
            if isinstance(value, (str, int, float, bool, type(None))):
                clean_item[key_str] = value
            
            elif isinstance(value, (list, tuple)):
                # Recursively clean lists
                clean_list = []
                for v in value:
                    if isinstance(v, dict):
                        clean_list.append(format_search_results([v])[0])
                    elif isinstance(v, (str, int, float, bool, type(None))):
                        clean_list.append(v)
                    else:
                        clean_list.append(str(v))
                clean_item[key_str] = clean_list
            
            elif isinstance(value, dict):
                # Recursively clean nested dicts
                nested = format_search_results([value])
                clean_item[key_str] = nested[0] if nested else {}
            
            elif hasattr(value, 'isoformat'):  # datetime objects
                clean_item[key_str] = value.isoformat()
            
            else:
                # Convert anything else to string
                try:
                    # Test if JSON serializable
                    json.dumps(value, default=str)
                    clean_item[key_str] = value
                except (TypeError, ValueError):
                    clean_item[key_str] = str(value)
        
        formatted.append(clean_item)
    
    return formatted

def rate_limit_request(key: str, max_requests: int = 10, window_seconds: int = 60) -> Tuple[bool, Optional[str]]:
    """
    Simple rate limiting per key (IP address or user ID).
    Returns: (is_allowed, error_message)
    """
    current_time = time.time()
    
    if key not in _rate_limit_storage:
        _rate_limit_storage[key] = []
    
    # Clean old entries outside window
    _rate_limit_storage[key] = [
        ts for ts in _rate_limit_storage[key] 
        if current_time - ts < window_seconds
    ]
    
    # Check limit
    if len(_rate_limit_storage[key]) >= max_requests:
        logger.warning(f"Rate limit exceeded for key: {key}")
        return False, f"Rate limit exceeded. Max {max_requests} requests per {window_seconds} seconds."
    
    # Add current request
    _rate_limit_storage[key].append(current_time)
    return True, None

def log_search(query: str, results_count: int, source: str = 'unknown', error: Optional[str] = None):
    """
    Log search activity for monitoring.
    """
    log_data = {
        'event': 'search',
        'query': query[:100],  # Truncate for privacy
        'results_count': results_count,
        'source': source,
        'timestamp': time.time()
    }
    
    if error:
        log_data['error'] = error
        logger.error(f"Search failed: {json.dumps(log_data)}")
    else:
        logger.info(f"Search completed: {json.dumps(log_data)}")

def log_error(error: Exception, context: str = '', extra_data: Optional[Dict] = None):
    """
    Structured error logging.
    """
    error_data = {
        'event': 'error',
        'error_type': type(error).__name__,
        'error_message': str(error),
        'context': context,
        'timestamp': time.time()
    }
    
    if extra_data:
        error_data.update(extra_data)
    
    logger.error(f"Application error: {json.dumps(error_data, default=str)}")

def log_warning(message: str, extra_data: Optional[Dict] = None):
    """
    Structured warning logging.
    """
    warning_data = {
        'event': 'warning',
        'message': message,
        'timestamp': time.time()
    }
    
    if extra_data:
        warning_data.update(extra_data)
    
    logger.warning(f"Application warning: {json.dumps(warning_data, default=str)}")

def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename for safe storage.
    """
    import re
    # Remove or replace dangerous characters
    sanitized = re.sub(r'[^\w\s.-]', '_', filename)
    # Limit length
    return sanitized[:255]

def truncate_string(text: str, max_length: int = 500, suffix: str = '...') -> str:
    """
    Safely truncate string with ellipsis.
    """
    if not text:
        return ''
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix

def retry_on_error(max_retries: int = 3, delay: float = 1.0):
    """
    Decorator for retrying functions on failure.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    logger.warning(f"Attempt {attempt + 1}/{max_retries} failed for {func.__name__}: {e}")
                    if attempt < max_retries - 1:
                        time.sleep(delay * (attempt + 1))  # Exponential backoff
            
            logger.error(f"All {max_retries} retries failed for {func.__name__}")
            raise last_exception
        
        return wrapper
    return decorator

# Export all functions
__all__ = [
    'safe_json_response',
    'validate_search_query',
    'format_search_results',
    'rate_limit_request',
    'log_search',
    'log_error',
    'log_warning',
    'sanitize_filename',
    'truncate_string',
    'retry_on_error'
]
