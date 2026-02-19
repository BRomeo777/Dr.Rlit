"""
Dr.R L - Literature Search AI Agent
Converted from Google Colab to Flask
Searches 17+ open-access databases and downloads papers
"""

import requests
import json
import os
import re
import time
import hashlib
import shutil
import sys
import traceback
import logging
import warnings
from datetime import datetime
from urllib.parse import quote, unquote, urljoin
from typing import List, Dict, Optional, Tuple

try:
    import arxiv
except ImportError:
    arxiv = None

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None

import pandas as pd
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET

# FIX: Removed the dot (.) from the import to prevent "no known parent package" error
try:
    from utils import log_error, log_warning, log_search
except ImportError:
    # Fallback in case utils.py is missing or structure differs
    def log_error(*args, **kwargs): pass
    def log_warning(*args, **kwargs): pass
    def log_search(*args, **kwargs): pass

class DrRLAgent:
    """
    Dr.R L - Literature Search AI Agent
    Searches 17+ open-access databases and downloads papers
    """
    
    def __init__(self, base_folder: str = "downloads", api_keys: Dict = None):
        self.base_folder = base_folder
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json, text/plain, */*, application/xml, text/xml',
            'Accept-Language': 'en-US,en;q=0.9',
        })
        self.results = []
        self.query = ""
        self.session_id = ""
        self.api_keys = api_keys or {}
        self.last_request_time = 0
        self.min_request_interval = 1.0
        self.error_logs = []
        self.warning_logs = []
        self.search_logs = []
        self._setup_folders()
    
    def _setup_folders(self):
        """Create organized folder structure"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_id = f"Search_{timestamp}"
        self.session_folder = os.path.join(self.base_folder, self.session_id)
        self.full_pdf_folder = os.path.join(self.session_folder, "Full_PDFs")
        self.abstracts_folder = os.path.join(self.session_folder, "Abstracts")
        self.errors_folder = os.path.join(self.session_folder, "Errors")
        
        for folder in [self.full_pdf_folder, self.abstracts_folder, self.errors_folder]:
            os.makedirs(folder, exist_ok=True)
    
    def _rate_limit(self):
        """Ensure we don't hit rate limits"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        if time_since_last < self.min_request_interval:
            time.sleep(self.min_request_interval - time_since_last)
        self.last_request_time = time.time()
    
    def search(self, query: str, max_results: int = 20, year_range: Tuple[int, int] = None) -> Dict:
        """Main search function - searches all open-access databases"""
        self.query = query
        self.year_range = year_range
        self.results = []
        
        all_papers = []
        
        search_methods = [
            ("PubMed Central", self._search_pubmed_central),
            ("Europe PMC", self._search_europe_pmc),
            ("arXiv", self._search_arxiv),
            ("bioRxiv", self._search_biorxiv),
            ("medRxiv", self._search_medrxiv),
            ("ChemRxiv", self._search_chemrxiv),
            ("OpenAlex", self._search_openalex),
            ("Semantic Scholar", self._search_semantic_scholar),
            ("CORE", self._search_core),
            ("Zenodo", self._search_zenodo),
            ("DOAJ", self._search_doaj),
            ("OpenAIRE", self._search_openaire),
            ("Figshare", self._search_figshare),
            ("SSRN", self._search_ssrn),
            ("MDPI", self._search_mdpi),
            ("SciELO", self._search_scielo),
            ("Redalyc", self._search_redalyc),
        ]
        
        for source_name, search_func in search_methods:
            try:
                papers = search_func(query, max_results)
                
                if year_range and papers:
                    papers = self._filter_by_year(papers, year_range)
                
                valid_papers = self._validate_papers(papers, query)
                log_search(self.search_logs, source_name, query, len(valid_papers), "SUCCESS")
                
                all_papers.extend(valid_papers)
                self._rate_limit()
                
            except Exception as e:
                log_error(self.error_logs, source_name, e, f"query={query}")
                log_search(self.search_logs, source_name, query, 0, "FAILED")
        
        unique_papers = self._deduplicate_papers(all_papers)
        
        if not unique_papers:
            self._save_all_logs()
            return None
        
        self._process_papers(unique_papers)
        self._generate_csv_log()
        self._save_all_logs()
        
        return self._create_download_package()

    # ... (rest of the methods continue as per your original script)
