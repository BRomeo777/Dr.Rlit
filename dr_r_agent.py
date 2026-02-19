import requests
import os
import time
from datetime import datetime

# This class handles your Gastric Cancer literature searches
class DrRLAgent:
    def __init__(self, base_folder: str = "downloads", api_keys: dict = None):
        # We use lowercase 'dict' here to avoid the NameError
        self.base_folder = base_folder
        self.session = requests.Session()
        self.api_keys = api_keys or {}
        
        if not os.path.exists(self.base_folder):
            os.makedirs(self.base_folder)

    def search(self, query: str, max_results: int = 10, year_range=None):
        """Main search function for your website"""
        try:
            results = self._search_pubmed_central(query, max_results)
            return results
        except Exception as e:
            print(f"Search error: {e}")
            return []

    def _search_pubmed_central(self, query, max_results=10):
        """Specifically pulls papers for Gastric Cancer"""
        base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
        
        # This keeps the search focused on your PhD topic
        search_term = f"({query}) AND (gastric cancer OR stomach neoplasm)"
        
        params = {
            "db": "pmc",
            "term": search_term,
            "retmax": max_results,
            "retmode": "json"
        }
        
        try:
            response = self.session.get(base_url, params=params)
            data = response.json()
            ids = data.get("esearchresult", {}).get("idlist", [])
            
            papers = []
            for i in ids:
                papers.append({
                    "title": f"Gastric Cancer Research Paper (PMC{i})",
                    "source": "PubMed Central",
                    "url": f"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC{i}/",
                    "id": i
                })
            return papers
        except Exception:
            return []

    # These 'dummy' functions prevent your app.py from crashing 
    # if it tries to run extra steps like filtering or logging.
    def _filter_by_year(self, papers, yr): return papers
    def _validate_papers(self, papers, q): return papers
    def _deduplicate_papers(self, papers): return papers
    def _process_papers(self, papers): pass
    def _generate_csv_log(self): pass
    def _save_all_logs(self): pass
    def _create_download_package(self): return {"status": "success"}
