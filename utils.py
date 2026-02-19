import json
import logging

logger = logging.getLogger(__name__)

def safe_json_response(data, status_code=200):
    """
    Ensure we always return valid JSON, never HTML
    """
    try:
        response = json.dumps(data)
        return response, status_code, {'Content-Type': 'application/json'}
    except Exception as e:
        logger.error(f"JSON serialization error: {e}")
        return json.dumps({
            'success': False,
            'error': 'JSON serialization failed',
            'details': str(e)
        }), 500, {'Content-Type': 'application/json'}

def validate_search_query(query):
    """
    Validate search query input
    """
    if not query:
        return False, "Query is required"
    if not isinstance(query, str):
        return False, "Query must be a string"
    if len(query.strip()) == 0:
        return False, "Query cannot be empty"
    if len(query) > 1000:
        return False, "Query too long (max 1000 characters)"
    return True, None

def format_search_results(results):
    """
    Ensure results are JSON serializable
    """
    if not isinstance(results, list):
        results = [results] if results else []
    
    formatted = []
    for item in results:
        if isinstance(item, dict):
            # Ensure all values are serializable
            clean_item = {}
            for key, value in item.items():
                if isinstance(value, (str, int, float, bool, type(None))):
                    clean_item[key] = value
                elif isinstance(value, (list, dict)):
                    try:
                        json.dumps(value)  # Test serialization
                        clean_item[key] = value
                    except:
                        clean_item[key] = str(value)
                else:
                    clean_item[key] = str(value)
            formatted.append(clean_item)
        else:
            formatted.append({'data': str(item)})
    
    return formatted
