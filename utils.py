"""
Dr.R L - Utility Functions
Logging, validation, and helper functions
"""

import time
import traceback
from datetime import datetime
from typing import List, Dict, Optional
import functools


def log_error(error_logs: List[Dict], source: str, error: Exception, details: str = ""):
    """Log error with full traceback"""
    tb = traceback.format_exc()
    entry = {
        'timestamp': datetime.now().isoformat(),
        'source': source,
        'error_type': type(error).__name__,
        'error_message': str(error),
        'details': details,
        'traceback': tb
    }
    error_logs.append(entry)


def log_warning(warning_logs: List[Dict], source: str, message: str):
    """Log warning"""
    entry = {
        'timestamp': datetime.now().isoformat(),
        'source': source,
        'message': message
    }
    warning_logs.append(entry)


def log_search(search_logs: List[Dict], source: str, query: str, results_count: int, status: str):
    """Log search attempt"""
    entry = {
        'timestamp': datetime.now().isoformat(),
        'source': source,
        'query': query,
        'results_count': results_count,
        'status': status
    }
    search_logs.append(entry)


def rate_limit_request(min_interval: float = 1.0):
    """Rate limiting decorator for requests"""
    last_request_time = [0.0]  # Use list for mutable closure
    
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            current_time = time.time()
            time_since_last = current_time - last_request_time[0]
            
            if time_since_last < min_interval:
                time.sleep(min_interval - time_since_last)
            
            last_request_time[0] = time.time()
            return func(*args, **kwargs)
        return wrapper
    return decorator


def validate_query(query: str) -> tuple[bool, str]:
    """Validate search query"""
    if not query or not isinstance(query, str):
        return False, "Query must be a non-empty string"
    
    query = query.strip()
    
    if len(query) < 3:
        return False, "Query must be at least 3 characters long"
    
    if len(query) > 500:
        return False, "Query too long (max 500 characters)"
    
    # Check for valid characters
    invalid_chars = ['<', '>', '{', '}', '|', '^', '`']
    for char in invalid_chars:
        if char in query:
            return False, f"Invalid character in query: {char}"
    
    return True, query


def sanitize_filename(filename: str, max_length: int = 100) -> str:
    """Sanitize filename for safe storage"""
    # Remove or replace invalid characters
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, '_')
    
    # Limit length
    if len(filename) > max_length:
        filename = filename[:max_length]
    
    # Remove leading/trailing spaces and dots
    filename = filename.strip(' .')
    
    # Ensure not empty
    if not filename:
        filename = "unnamed_file"
    
    return filename


def format_paper_for_display(paper: Dict) -> Dict:
    """Format paper data for web display"""
    return {
        'title': paper.get('title', 'No Title')[:200],
        'authors': paper.get('authors', 'Unknown')[:100],
        'year': paper.get('year', 'N/A'),
        'journal': paper.get('journal', 'N/A')[:100],
        'source': paper.get('source', 'Unknown'),
        'abstract': paper.get('abstract', 'No abstract available')[:500],
        'doi': paper.get('doi', ''),
        'pdf_url': paper.get('pdf_url', ''),
        'access_type': paper.get('access_type', 'Unknown'),
        'relevance_score': paper.get('relevance_score', 0)
    }


def calculate_search_progress(current: int, total: int) -> int:
    """Calculate search progress percentage"""
    if total == 0:
        return 0
    return min(int((current / total) * 100), 100)


def truncate_text(text: str, max_length: int = 200, suffix: str = "...") -> str:
    """Truncate text with ellipsis"""
    if not text or len(text) <= max_length:
        return text or ""
    return text[:max_length].rsplit(' ', 1)[0] + suffix


def parse_year_range(year_start: Optional[str], year_end: Optional[str]) -> Optional[tuple]:
    """Parse and validate year range"""
    try:
        start = int(year_start) if year_start else None
        end = int(year_end) if year_end else None
        
        current_year = datetime.now().year
        
        # Validate ranges
        if start and (start < 1900 or start > current_year + 1):
            return None
        if end and (end < 1900 or end > current_year + 1):
            return None
        
        # Ensure start <= end
        if start and end and start > end:
            start, end = end, start
        
        if start or end:
            return (start or 1900, end or current_year)
        
        return None
        
    except (ValueError, TypeError):
        return None


def estimate_search_time(max_results: int, database_count: int = 17) -> int:
    """Estimate search time in seconds"""
    # Base time + time per database + time per result
    base_time = 5
    db_time = database_count * 2  # ~2 seconds per database
    result_time = (max_results / 10) * 5  # ~5 seconds per 10 results
    
    return int(base_time + db_time + result_time)


def format_file_size(size_bytes: int) -> str:
    """Format file size for display"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"


def generate_search_id() -> str:
    """Generate unique search session ID"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    random_suffix = datetime.now().microsecond % 1000
    return f"search_{timestamp}_{random_suffix:03d}"


def merge_paper_data(existing: Dict, new_data: Dict) -> Dict:
    """Merge paper data, keeping non-empty values"""
    merged = existing.copy()
    
    for key, value in new_data.items():
        if value and value not in ['', 'N/A', 'Unknown', 'No abstract available']:
            merged[key] = value
    
    return merged


def deduplicate_by_doi(papers: List[Dict]) -> List[Dict]:
    """Simple deduplication by DOI"""
    seen_dois = set()
    unique = []
    
    for paper in papers:
        doi = paper.get('doi', '').lower().strip()
        
        if doi and doi in seen_dois:
            continue
        
        if doi:
            seen_dois.add(doi)
        
        unique.append(paper)
    
    return unique
