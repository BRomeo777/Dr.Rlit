import os
import logging
import requests
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

class DrRLAgent:
    def __init__(self):
        self.groq_api_key = os.environ.get('GROQ_API_KEY')
        if not self.groq_api_key:
            logger.warning("GROQ_API_KEY not set - some features may be limited")
        
        self.databases = [
            'pubmed', 'europe_pmc', 'arxiv', 'biorxiv', 
            'medrxiv', 'chemrxiv', 'openalex'
        ]
    
    def search(self, query: str, max_results: int = 20) -> List[Dict[str, Any]]:
        """
        Main search function - returns list of results
        """
        try:
            if not query or not query.strip():
                return []
            
            logger.info(f"Starting search for: {query}")
            
            # Initialize results
            all_results = []
            
            # Search each database (implement your actual search logic here)
            for db in self.databases[:3]:  # Limit for demo
                try:
                    db_results = self._search_database(db, query, max_results // 3)
                    all_results.extend(db_results)
                except Exception as e:
                    logger.error(f"Error searching {db}: {e}")
                    continue
            
            # Sort by relevance (newest first for now)
            all_results.sort(key=lambda x: x.get('year', 0), reverse=True)
            
            return all_results[:max_results]
            
        except Exception as e:
            logger.error(f"Search failed: {e}")
            # Return empty list instead of crashing
            return []
    
    def _search_database(self, db_name: str, query: str, limit: int) -> List[Dict]:
        """
        Search individual database - placeholder implementation
        Replace with your actual API calls
        """
        try:
            # Placeholder: return mock data structure
            # Replace this with your actual database search logic
            mock_results = [
                {
                    'title': f'Sample result from {db_name}',
                    'authors': ['Author Name'],
                    'year': 2024,
                    'source': db_name,
                    'url': f'https://example.com/{db_name}/123',
                    'abstract': f'Sample abstract for query: {query[:50]}...'
                }
            ]
            return mock_results[:limit]
            
        except Exception as e:
            logger.error(f"Database {db_name} search error: {e}")
            return []
    
    def _make_api_request(self, url: str, params: Dict = None, headers: Dict = None) -> Dict:
        """
        Safe API request with error handling
        """
        try:
            response = requests.get(
                url, 
                params=params, 
                headers=headers, 
                timeout=30
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.Timeout:
            logger.error(f"Timeout requesting {url}")
            return {}
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed for {url}: {e}")
            return {}
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON response from {url}")
            return {}
