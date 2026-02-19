import requests
import json
import os
from datetime import datetime
from urllib.parse import quote
from typing import List, Dict, Optional, Tuple

class DrRLAgent:
    def __init__(self, base_folder: str = "downloads", api_keys: dict = None):
        self.base_folder = base_folder
        self.session = requests.Session()
        self.api_keys = api_keys or {}
        
        # Setup session folder
        self.session_id = f"Search_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.session_folder = os.path.join(self.base_folder, self.session_id)
        os.makedirs(self.session_folder, exist_ok=True)

    def search(self, query: str, max_results: int = 20, year_range: Tuple[int, int] = None) -> Dict:
        """General Literature Search Agent"""
        all_papers = []
        
        try:
            # Connect to PubMed Central (PMC)
            url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pmc&term={quote(query)}&retmax={max_results}&retmode=json"
            res = self.session.get(url, timeout=10)
            data = res.json()
            ids = data.get('esearchresult', {}).get('idlist', [])
            
            for i in ids:
                all_papers.append({
                    'title': f"Research Paper (PMC{i})",
                    'authors': 'Scientific Authors',
                    'url': f"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC{i}/",
                    'source': 'PubMed Central',
                    'id': i,
                    'year': str(datetime.now().year)
                })

            # This structure prevents the "Unexpected end of JSON" error
            return {
                "status": "success",
                "total_papers": len(all_papers),
                "papers": all_papers,
                "session_id": self.session_id
            }
        except Exception as e:
            # Always return a valid JSON-ready dictionary even if search fails
            return {
                "status": "error", 
                "total_papers": 0, 
                "papers": [], 
                "message": str(e)
            }
