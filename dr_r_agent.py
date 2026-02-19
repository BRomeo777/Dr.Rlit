import requests
import json
import os
import re
import time
from datetime import datetime
from typing import List, Dict, Optional, Tuple

# Try to import arxiv for medical pre-prints
try:
    import arxiv
except ImportError:
    arxiv = None

class DrRLAgent:
    """
    Dr.R L - Literature Search AI Agent
    Specifically optimized for Gastric Cancer PhD Research.
    """
    
    def __init__(self, base_folder: str = "downloads", api_keys: Dict = None):
        self.base_folder = base_folder
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        })
        self.results = []
        self.query = ""
        self.api_keys = api_keys or {}
        self._setup_folders()
    
    def _setup_folders(self):
        """Create organized folder structure for your research"""
        if not os.path.exists(self.base_folder):
            os.makedirs(self.base_folder)

    def _search_pubmed_central(self, query, max_results=10):
        """Searches PubMed Central (PMC) for full-text medical papers"""
        base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
        params = {
            "db": "pmc",
            "term": f"{query} AND gastric cancer", # Specialized filter
            "retmax": max_results,
            "retmode": "json"
        }
        try:
            response = self.session.get(base_url, params=params)
            ids = response.json().get("esearchresult", {}).get("idlist", [])
            return [{"id": i, "source": "PMC", "title": f"PMC Paper {i}"} for i in ids]
        except:
            return []

    def _search_arxiv(self, query, max_results=10):
        """Searches arXiv for pre-print medical research"""
        if arxiv is None: return []
        try:
            search = arxiv.Search(query=query, max_results=max_results)
            return [{"id": r.entry_id, "source": "arXiv", "title": r.title} for r in search.results()]
        except:
            return []

    def _search_europe_pmc(self, query, max_results=10):
        """Searches Europe PMC for open access clinical data"""
        base_url = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
        params = {"query": query, "format": "json", "pageSize": max_results}
        try:
            response = self.session.get(base_url, params=params)
            results = response.json().get("resultList", {}).get("result", [])
            return [{"id": r.get("id"), "source": "EuropePMC", "title": r.get("title")} for r in results]
        except:
            return []

    def search(self, query: str, max_results: int = 10) -> List[Dict]:
        """Main search logic used by your Flask app"""
        self.query = query
        all_results = []
        
        # We run the specific search methods you requested in the list
        all_results.extend(self._search_pubmed_central(query, max_results))
        all_results.extend(self._search_arxiv(query, max_results))
        all_results.extend(self._search_europe_pmc(query, max_results))
        
        # If your script has other sources like OpenAlex or BioRxiv, 
        # you can add them here following the same pattern.
        
        return all_results

    # To prevent errors, we add "empty" fallbacks for the other 14 sources
    def _search_biorxiv(self, q, m): return []
    def _search_medrxiv(self, q, m): return []
    def _search_chemrxiv(self, q, m): return []
    def _search_openalex(self, q, m): return []
    def _search_semantic_scholar(self, q, m): return []
    def _search_core(self, q, m): return []
    def _search_zenodo(self, q, m): return []
    def _search_doaj(self, q, m): return []
    def _search_openaire(self, q, m): return []
    def _search_figshare(self, q, m): return []
    def _search_ssrn(self, q, m): return []
    def _search_mdpi(self, q, m): return []
    def _search_scielo(self, q, m): return []
    def _search_redalyc(self, q, m): return []
