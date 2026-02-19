"""
Dr.R L - Literature Search AI Agent
Fixed version with proper JSON/HTML error handling
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


def log_error(error_logs, source, exception, details=""):
    """Log errors"""
    error_logs.append({
        'timestamp': datetime.now().isoformat(),
        'source': source,
        'error': str(exception),
        'details': details
    })


def log_warning(warning_logs, source, message):
    """Log warnings"""
    warning_logs.append({
        'timestamp': datetime.now().isoformat(),
        'source': source,
        'message': message
    })


def log_search(search_logs, source, query, count, status):
    """Log search attempts"""
    search_logs.append({
        'timestamp': datetime.now().isoformat(),
        'source': source,
        'query': query,
        'results_count': count,
        'status': status
    })


class DrRLAgent:
    """
    Dr.R L - Literature Search AI Agent
    Searches 17+ open-access databases and downloads papers
    """

    def __init__(self, base_folder: str = "downloads", api_keys: Dict = None):
        self.base_folder = base_folder
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
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

    def _safe_json_request(self, url, method='get', **kwargs):
        """
        Make request and safely parse JSON, handling HTML errors
        Returns: (success: bool, data: dict or error_msg: str)
        """
        try:
            self._rate_limit()
            
            if method == 'post':
                response = self.session.post(url, **kwargs)
            else:
                response = self.session.get(url, **kwargs)
            
            # Check status code first
            if response.status_code == 429:
                return False, "Rate limited (429)"
            elif response.status_code == 403:
                return False, "Forbidden (403) - blocked or requires auth"
            elif response.status_code == 401:
                return False, "Unauthorized (401) - check API key"
            elif response.status_code != 200:
                return False, f"HTTP {response.status_code}"
            
            # Check content type
            content_type = response.headers.get('content-type', '').lower()
            
            # If we got HTML instead of JSON, it's likely an error page
            if 'text/html' in content_type and 'application/json' not in content_type:
                # Try to extract title from HTML for debugging
                try:
                    soup = BeautifulSoup(response.text[:1000], 'html.parser')
                    title = soup.find('title')
                    title_text = title.get_text(strip=True) if title else "Unknown HTML page"
                    return False, f"HTML response: {title_text[:100]}"
                except:
                    return False, "HTML response (likely blocked or maintenance)"
            
            # Try to parse JSON
            try:
                data = response.json()
                return True, data
            except json.JSONDecodeError as e:
                # Check if response starts with HTML doctype
                if response.text.strip().startswith('<'):
                    return False, "Received HTML instead of JSON (API error or blocked)"
                return False, f"JSON parse error: {str(e)}"
                
        except requests.exceptions.Timeout:
            return False, "Request timeout"
        except requests.exceptions.ConnectionError:
            return False, "Connection error"
        except Exception as e:
            return False, str(e)

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

    def _filter_by_year(self, papers: List[Dict], year_range: Tuple[int, int]) -> List[Dict]:
        """Filter papers by publication year"""
        filtered = []
        start_year, end_year = year_range

        for paper in papers:
            year_str = str(paper.get('year', ''))
            if year_str.isdigit():
                year = int(year_str)
                if start_year <= year <= end_year:
                    filtered.append(paper)
            else:
                filtered.append(paper)
        return filtered

    def _validate_papers(self, papers: List[Dict], query: str) -> List[Dict]:
        """Validate that papers are real and relevant to the query"""
        validated = []
        query_terms = set(query.lower().split())

        for paper in papers:
            if not paper.get('title') or paper['title'] in ['No Title', '']:
                continue

            title_lower = paper['title'].lower()
            if len(title_lower) < 10:
                continue

            title_words = set(title_lower.split())
            abstract = paper.get('abstract', '').lower()

            has_relevance = bool(query_terms & title_words) or any(term in abstract for term in query_terms)

            if len(query_terms) > 2 and not has_relevance:
                continue

            relevance_score = len(query_terms & title_words) * 2
            if any(term in abstract for term in query_terms):
                relevance_score += 1

            paper['relevance_score'] = relevance_score
            validated.append(paper)

        validated.sort(key=lambda x: x.get('relevance_score', 0), reverse=True)
        return validated

    def _search_pubmed_central(self, query: str, max_results: int) -> List[Dict]:
        """Search PubMed Central Open Access subset"""
        papers = []
        try:
            search_url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pmc&term={quote(query)}+AND+free+fulltext[filter]&retmax={max_results}&retmode=json"
            
            success, data = self._safe_json_request(search_url, timeout=30)
            
            if not success:
                log_error(self.error_logs, "PubMed Central", Exception(data), f"query={query}")
                return papers

            if 'esearchresult' in data and 'idlist' in data['esearchresult']:
                pmids = data['esearchresult']['idlist']
                for i in range(0, len(pmids), 20):
                    batch = pmids[i:i+20]
                    fetch_url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pmc&id={','.join(batch)}&retmode=xml"
                    
                    try:
                        self._rate_limit()
                        fetch_response = self.session.get(fetch_url, timeout=30)
                        fetch_response.raise_for_status()
                        root = ET.fromstring(fetch_response.content)

                        for article in root.findall('.//article'):
                            paper = self._parse_pmc_article(article)
                            if paper:
                                papers.append(paper)
                    except Exception as e:
                        log_error(self.error_logs, "PubMed Central Fetch", e, f"batch={batch}")
                        
        except Exception as e:
            log_error(self.error_logs, "PubMed Central", e, f"query={query}")
        return papers

    def _parse_pmc_article(self, article) -> Optional[Dict]:
        """Parse PMC XML article"""
        try:
            title_elem = article.find('.//article-title')
            title = title_elem.text if title_elem is not None else "No Title"

            authors = []
            for author in article.findall('.//contrib[@contrib-type="author"]'):
                surname = author.find('name/surname')
                given = author.find('name/given-names')
                if surname is not None:
                    name = f"{given.text if given is not None else ''} {surname.text}".strip()
                    authors.append(name)

            abstract_elem = article.find('.//abstract')
            abstract = ""
            if abstract_elem is not None:
                abstract = ' '.join(abstract_elem.itertext())
                abstract = ' '.join(abstract.split())

            doi = ""
            pmid = ""
            pmcid = ""
            for article_id in article.findall('.//article-id'):
                id_type = article_id.get('pub-id-type')
                if id_type == 'doi':
                    doi = article_id.text or ""
                elif id_type == 'pmid':
                    pmid = article_id.text or ""
                elif id_type == 'pmcid':
                    pmcid = article_id.text or ""

            pdf_url = ""
            if pmcid:
                pmcid_clean = pmcid.replace('PMC', '').strip()
                pdf_url = f"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC{pmcid_clean}/pdf/main.pdf"

            year = ""
            pub_date = article.find('.//pub-date')
            if pub_date is not None:
                year_elem = pub_date.find('year')
                if year_elem is not None:
                    year = year_elem.text

            journal = ""
            journal_elem = article.find('.//journal-title')
            if journal_elem is not None:
                journal = journal_elem.text

            return {
                'title': title,
                'authors': ', '.join(authors) if authors else 'Unknown',
                'abstract': abstract[:2000] if abstract else "No abstract available",
                'doi': doi,
                'pmid': pmid,
                'pmcid': pmcid,
                'pdf_url': pdf_url,
                'year': year,
                'journal': journal or 'N/A',
                'source': 'PubMed Central'
            }
        except Exception as e:
            log_error(self.error_logs, "PMC Parser", e, "XML parsing failed")
            return None

    def _search_europe_pmc(self, query: str, max_results: int) -> List[Dict]:
        """Search Europe PMC Open Access"""
        papers = []
        try:
            url = f"https://www.ebi.ac.uk/europepmc/webservices/rest/search?query={quote(query)}&format=json&pageSize={max_results}&openAccess=true&sort=CITED+desc"
            
            success, data = self._safe_json_request(url, timeout=30)
            
            if not success:
                log_error(self.error_logs, "Europe PMC", Exception(data), f"query={query}")
                return papers

            for item in data.get('resultList', {}).get('result', []):
                if item.get('isOpenAccess') == 'Y':
                    pdf_url = ""
                    if item.get('pmcid'):
                        pdf_url = f"https://www.ebi.ac.uk/europepmc/backend/ptpmcrender.fcgi?accid={item['pmcid']}&blobtype=pdf"

                    papers.append({
                        'title': item.get('title', 'No Title'),
                        'authors': item.get('authorString', 'Unknown'),
                        'abstract': item.get('abstractText', 'No abstract')[:2000],
                        'doi': item.get('doi', ''),
                        'pmid': item.get('pmid', ''),
                        'pmcid': item.get('pmcid', ''),
                        'pdf_url': pdf_url,
                        'year': item.get('pubYear', ''),
                        'journal': item.get('journalTitle', ''),
                        'source': 'Europe PMC'
                    })
        except Exception as e:
            log_error(self.error_logs, "Europe PMC", e, f"query={query}")
        return papers

    def _search_arxiv(self, query: str, max_results: int) -> List[Dict]:
        """Search arXiv"""
        papers = []
        try:
            if arxiv is None:
                log_warning(self.warning_logs, "arXiv", "arxiv library not installed")
                return papers

            search = arxiv.Search(query=query, max_results=max_results, sort_by=arxiv.SortCriterion.Relevance)
            for result in search.results():
                papers.append({
                    'title': result.title,
                    'authors': ', '.join([str(a) for a in result.authors]),
                    'abstract': result.summary[:2000],
                    'doi': '',
                    'arxiv_id': result.entry_id.split('/')[-1],
                    'pdf_url': result.pdf_url,
                    'year': str(result.published.year),
                    'journal': 'arXiv',
                    'source': 'arXiv'
                })
        except Exception as e:
            log_error(self.error_logs, "arXiv", e, f"query={query}")
        return papers

    def _search_biorxiv(self, query: str, max_results: int) -> List[Dict]:
        """Search bioRxiv"""
        papers = []
        try:
            url = f"https://www.biorxiv.org/search/{quote(query)}%20numresults%3A{max_results}%20sort%3Arelevance-rank"
            
            try:
                self._rate_limit()
                response = self.session.get(url, timeout=30)
                response.raise_for_status()
            except Exception as e:
                log_error(self.error_logs, "bioRxiv", e, f"Connection failed: {query}")
                return papers
                
            soup = BeautifulSoup(response.content, 'html.parser')
            articles = soup.find_all('div', class_='highwire-cite')

            for article in articles[:max_results]:
                try:
                    title_elem = article.find('span', class_='highwire-cite-title')
                    title = title_elem.get_text(strip=True) if title_elem else "No Title"

                    authors_elem = article.find('span', class_='highwire-citation-authors')
                    authors = authors_elem.get_text(strip=True) if authors_elem else "Unknown"

                    doi_elem = article.find('span', class_='highwire-cite-metadata-doi')
                    doi = doi_elem.text.replace('doi:', '').strip() if doi_elem else ""

                    pdf_url = ""
                    link_elem = article.find('a', href=re.compile(r'/content/'))
                    if link_elem:
                        href = link_elem.get('href', '')
                        if href:
                            pdf_url = f"https://www.biorxiv.org{href}.full.pdf"

                    date_elem = article.find('span', class_='highwire-cite-metadata-date')
                    year = ""
                    if date_elem:
                        year_match = re.search(r'(\d{4})', date_elem.text)
                        if year_match:
                            year = year_match.group(1)

                    papers.append({
                        'title': title,
                        'authors': authors,
                        'abstract': 'Download PDF for full text',
                        'doi': doi,
                        'pdf_url': pdf_url,
                        'year': year,
                        'journal': 'bioRxiv',
                        'source': 'bioRxiv'
                    })
                except Exception as e:
                    log_error(self.error_logs, "bioRxiv Parser", e, "Article parsing failed")
        except Exception as e:
            log_error(self.error_logs, "bioRxiv", e, f"query={query}")
        return papers

    def _search_medrxiv(self, query: str, max_results: int) -> List[Dict]:
        """Search medRxiv"""
        papers = []
        try:
            url = f"https://www.medrxiv.org/search/{quote(query)}%20numresults%3A{max_results}%20sort%3Arelevance-rank"
            
            try:
                self._rate_limit()
                response = self.session.get(url, timeout=30)
                response.raise_for_status()
            except Exception as e:
                log_error(self.error_logs, "medRxiv", e, f"Connection failed: {query}")
                return papers
                
            soup = BeautifulSoup(response.content, 'html.parser')
            articles = soup.find_all('div', class_='highwire-cite')

            for article in articles[:max_results]:
                try:
                    title_elem = article.find('span', class_='highwire-cite-title')
                    title = title_elem.get_text(strip=True) if title_elem else "No Title"

                    authors_elem = article.find('span', class_='highwire-citation-authors')
                    authors = authors_elem.get_text(strip=True) if authors_elem else "Unknown"

                    doi_elem = article.find('span', class_='highwire-cite-metadata-doi')
                    doi = doi_elem.text.replace('doi:', '').strip() if doi_elem else ""

                    pdf_url = ""
                    link_elem = article.find('a', href=re.compile(r'/content/'))
                    if link_elem:
                        href = link_elem.get('href', '')
                        if href:
                            pdf_url = f"https://www.medrxiv.org{href}.full.pdf"

                    date_elem = article.find('span', class_='highwire-cite-metadata-date')
                    year = ""
                    if date_elem:
                        year_match = re.search(r'(\d{4})', date_elem.text)
                        if year_match:
                            year = year_match.group(1)

                    papers.append({
                        'title': title,
                        'authors': authors,
                        'abstract': 'Download PDF for full text',
                        'doi': doi,
                        'pdf_url': pdf_url,
                        'year': year,
                        'journal': 'medRxiv',
                        'source': 'medRxiv'
                    })
                except Exception as e:
                    log_error(self.error_logs, "medRxiv Parser", e, "Article parsing failed")
        except Exception as e:
            log_error(self.error_logs, "medRxiv", e, f"query={query}")
        return papers

    def _search_chemrxiv(self, query: str, max_results: int) -> List[Dict]:
        """Search ChemRxiv"""
        papers = []
        try:
            url = f"https://chemrxiv.org/engage/chemrxiv/public-api/search?term={quote(query)}&limit={max_results}"
            
            success, data = self._safe_json_request(url, timeout=30)
            
            if not success:
                log_error(self.error_logs, "ChemRxiv", Exception(data), f"query={query}")
                return papers

            for item in data.get('results', []):
                try:
                    papers.append({
                        'title': item.get('title', 'No Title'),
                        'authors': ', '.join([a.get('name', '') for a in item.get('authors', [])]),
                        'abstract': item.get('abstract', 'No abstract')[:2000],
                        'doi': item.get('doi', ''),
                        'pdf_url': item.get('downloadUrl', ''),
                        'year': str(item.get('publishedDate', '')[:4]) if item.get('publishedDate') else '',
                        'journal': 'ChemRxiv',
                        'source': 'ChemRxiv'
                    })
                except Exception as e:
                    log_error(self.error_logs, "ChemRxiv Parser", e, "Item parsing failed")
        except Exception as e:
            log_error(self.error_logs, "ChemRxiv", e, f"query={query}")
        return papers

    def _search_openalex(self, query: str, max_results: int) -> List[Dict]:
        """Search OpenAlex"""
        papers = []
        try:
            email = self.api_keys.get('email', 'researcher@example.com')
            url = f"https://api.openalex.org/works?search={quote(query)}&per-page={max_results}&filter=has_pdf:true&mailto={email}"
            
            success, data = self._safe_json_request(url, timeout=30)
            
            if not success:
                log_error(self.error_logs, "OpenAlex", Exception(data), f"query={query}")
                return papers

            for item in data.get('results', []):
                try:
                    pdf_url = ""
                    oa_info = item.get('open_access', {})
                    if oa_info.get('is_oa'):
                        pdf_url = oa_info.get('oa_url', '')

                    doi = item.get('doi', '').replace('https://doi.org/', '') if item.get('doi') else ''
                    authors_list = item.get('authorships', [])
                    authors = ', '.join([a.get('author', {}).get('display_name', '') for a in authors_list if a.get('author')])

                    abstract = item.get('abstract', '')
                    if not abstract and item.get('abstract_inverted_index'):
                        abstract = self._reconstruct_abstract(item['abstract_inverted_index'])

                    year = str(item.get('publication_year', ''))
                    host_venue = item.get('host_venue', {}) or item.get('primary_location', {}) or {}
                    journal = host_venue.get('display_name', '') if isinstance(host_venue, dict) else ''

                    papers.append({
                        'title': item.get('display_name', 'No Title'),
                        'authors': authors,
                        'abstract': (abstract or 'No abstract available')[:2000],
                        'doi': doi,
                        'pdf_url': pdf_url,
                        'year': year,
                        'journal': journal or 'OpenAlex',
                        'source': 'OpenAlex'
                    })
                except Exception as e:
                    log_error(self.error_logs, "OpenAlex Parser", e, "Item parsing failed")
        except Exception as e:
            log_error(self.error_logs, "OpenAlex", e, f"query={query}")
        return papers

    def _search_semantic_scholar(self, query: str, max_results: int) -> List[Dict]:
        """Search Semantic Scholar"""
        papers = []
        try:
            base_url = "https://api.semanticscholar.org/graph/v1/paper/search"
            params = {
                'query': query,
                'limit': max_results,
                'fields': 'title,authors,year,abstract,openAccessPdf,externalIds,venue,citationCount'
            }
            headers = {}
            if self.api_keys.get('semantic_scholar'):
                headers['x-api-key'] = self.api_keys['semantic_scholar']

            success, data = self._safe_json_request(base_url, params=params, headers=headers, timeout=30)
            
            if not success:
                log_error(self.error_logs, "Semantic Scholar", Exception(data), f"query={query}")
                return papers

            for item in data.get('data', []):
                try:
                    pdf_info = item.get('openAccessPdf', {})
                    pdf_url = pdf_info.get('url', '') if pdf_info else ''
                    authors = ', '.join([a.get('name', '') for a in item.get('authors', []) if a])

                    papers.append({
                        'title': item.get('title', 'No Title'),
                        'authors': authors,
                        'abstract': item.get('abstract', 'No abstract available')[:2000],
                        'doi': item.get('externalIds', {}).get('DOI', ''),
                        'pdf_url': pdf_url,
                        'year': str(item.get('year', '')),
                        'journal': item.get('venue', '') or 'Semantic Scholar',
                        'source': 'Semantic Scholar',
                        'citations': item.get('citationCount', 0)
                    })
                except Exception as e:
                    log_error(self.error_logs, "Semantic Scholar Parser", e, "Item parsing failed")
        except Exception as e:
            log_error(self.error_logs, "Semantic Scholar", e, f"query={query}")
        return papers

    def _search_core(self, query: str, max_results: int) -> List[Dict]:
        """Search CORE"""
        papers = []
        try:
            if not self.api_keys.get('core'):
                log_warning(self.warning_logs, "CORE", "No API key provided, skipping")
                return papers
                
            url = "https://api.core.ac.uk/v3/search/works"
            headers = {
                'Authorization': f"Bearer {self.api_keys['core']}",
                'Content-Type': 'application/json'
            }
            data = {
                'query': query,
                'limit': max_results,
                'filters': [{'field': 'language', 'value': 'en'}]
            }
            
            success, result_data = self._safe_json_request(url, method='post', headers=headers, json=data, timeout=30)
            
            if not success:
                log_error(self.error_logs, "CORE", Exception(result_data), f"query={query}")
                return papers

            results = result_data.get('results', [])

            for item in results:
                try:
                    papers.append({
                        'title': item.get('title', 'No Title'),
                        'authors': ', '.join(item.get('authors', [])),
                        'abstract': item.get('abstract', 'No abstract')[:2000],
                        'doi': item.get('doi', ''),
                        'pdf_url': item.get('downloadUrl', item.get('links', [{}])[0].get('url', '')),
                        'year': str(item.get('year', '')),
                        'journal': item.get('publisher', ''),
                        'source': 'CORE'
                    })
                except Exception as e:
                    log_error(self.error_logs, "CORE Parser", e, "Item parsing failed")
        except Exception as e:
            log_error(self.error_logs, "CORE", e, f"query={query}")
        return papers

    def _search_zenodo(self, query: str, max_results: int) -> List[Dict]:
        """Search Zenodo"""
        papers = []
        try:
            url = "https://zenodo.org/api/records"
            params = {
                'q': query,
                'size': max_results,
                'access_right': 'open',
                'sort': 'bestmatch'
            }
            
            success, data = self._safe_json_request(url, params=params, timeout=30)
            
            if not success:
                log_error(self.error_logs, "Zenodo", Exception(data), f"query={query}")
                return papers

            for item in data.get('hits', {}).get('hits', []):
                try:
                    metadata = item.get('metadata', {})
                    files = item.get('files', [])

                    pdf_url = ""
                    for f in files:
                        if f.get('type') == 'pdf' or f.get('key', '').endswith('.pdf'):
                            pdf_url = f.get('links', {}).get('self', '')
                            break

                    creators = metadata.get('creators', [])
                    authors = ', '.join([c.get('name', '') for c in creators])
                    pub_date = metadata.get('publication_date', '')
                    year = pub_date[:4] if pub_date else ''

                    papers.append({
                        'title': metadata.get('title', 'No Title'),
                        'authors': authors,
                        'abstract': metadata.get('description', 'No abstract')[:2000],
                        'doi': metadata.get('doi', ''),
                        'pdf_url': pdf_url,
                        'year': year,
                        'journal': metadata.get('journal', {}).get('title', 'Zenodo'),
                        'source': 'Zenodo'
                    })
                except Exception as e:
                    log_error(self.error_logs, "Zenodo Parser", e, "Item parsing failed")
        except Exception as e:
            log_error(self.error_logs, "Zenodo", e, f"query={query}")
        return papers

    def _search_doaj(self, query: str, max_results: int) -> List[Dict]:
        """Search DOAJ"""
        papers = []
        try:
            url = "https://doaj.org/api/v2/search/articles"
            params = {'query': query, 'pageSize': max_results}
            
            success, data = self._safe_json_request(url, params=params, timeout=30)
            
            if not success:
                log_error(self.error_logs, "DOAJ", Exception(data), f"query={query}")
                return papers

            for item in data.get('results', []):
                try:
                    bibjson = item.get('bibjson', {})
                    identifiers = bibjson.get('identifier', [])
                    doi = ''
                    for id_obj in identifiers:
                        if id_obj.get('type') == 'doi':
                            doi = id_obj.get('id', '')
                            break

                    links = bibjson.get('link', [])
                    pdf_url = ''
                    for link in links:
                        if link.get('type') == 'fulltext':
                            pdf_url = link.get('url', '')
                            break

                    authors = ', '.join([a.get('name', '') for a in bibjson.get('author', [])])

                    papers.append({
                        'title': bibjson.get('title', 'No Title'),
                        'authors': authors,
                        'abstract': bibjson.get('abstract', 'No abstract')[:2000],
                        'doi': doi,
                        'pdf_url': pdf_url,
                        'year': str(bibjson.get('year', '')),
                        'journal': bibjson.get('journal', {}).get('title', ''),
                        'source': 'DOAJ'
                    })
                except Exception as e:
                    log_error(self.error_logs, "DOAJ Parser", e, "Item parsing failed")
        except Exception as e:
            log_error(self.error_logs, "DOAJ", e, f"query={query}")
        return papers

    def _search_openaire(self, query: str, max_results: int) -> List[Dict]:
        """Search OpenAIRE"""
        papers = []
        try:
            url = "https://api.openaire.eu/search/publications"
            params = {
                'format': 'json',
                'query': query,
                'size': max_results,
                'openAccess': 'true'
            }
            
            success, data = self._safe_json_request(url, params=params, timeout=30)
            
            if not success:
                log_error(self.error_logs, "OpenAIRE", Exception(data), f"query={query}")
                return papers
                
            results = data.get('response', {}).get('results', {}).get('result', [])

            for item in results:
                try:
                    metadata = item.get('metadata', {}).get('oaf:entity', {}).get('oaf:result', {})
                    if not metadata:
                        continue

                    title = metadata.get('title', {}).get('$', 'No Title')
                    authors_list = metadata.get('creator', [])
                    if not isinstance(authors_list, list):
                        authors_list = [authors_list]
                    authors = ', '.join([a.get('$', '') for a in authors_list if a])

                    pid_list = metadata.get('pid', [])
                    if not isinstance(pid_list, list):
                        pid_list = [pid_list]
                    doi = ''
                    for pid in pid_list:
                        if pid.get('@classid') == 'doi':
                            doi = pid.get('$', '')
                            break

                    date = metadata.get('dateofacceptance', {}).get('$', '')
                    year = date[:4] if date else ''
                    pdf_url = metadata.get('bestaccessroute', {}).get('$', '')

                    papers.append({
                        'title': title,
                        'authors': authors or 'Unknown',
                        'abstract': 'Abstract at source',
                        'doi': doi,
                        'pdf_url': pdf_url,
                        'year': year,
                        'journal': metadata.get('publisher', {}).get('$', ''),
                        'source': 'OpenAIRE'
                    })
                except Exception as e:
                    log_error(self.error_logs, "OpenAIRE Parser", e, "Item parsing failed")
        except Exception as e:
            log_error(self.error_logs, "OpenAIRE", e, f"query={query}")
        return papers

    def _search_figshare(self, query: str, max_results: int) -> List[Dict]:
        """Search Figshare"""
        papers = []
        try:
            url = "https://api.figshare.com/v2/articles/search"
            params = {
                'search_for': query,
                'page_size': max_results,
                'item_type': 3
            }
            
            success, data = self._safe_json_request(url, params=params, timeout=30)
            
            if not success:
                log_error(self.error_logs, "Figshare", Exception(data), f"query={query}")
                return papers
                
            items = data.get('items', []) if isinstance(data, dict) else data

            for item in items:
                try:
                    pdf_url = item.get('download_url', '')
                    if not pdf_url:
                        article_id = item.get('id', '')
                        if article_id:
                            pdf_url = f"https://ndownloader.figshare.com/files/{article_id}"

                    authors = ', '.join([a.get('full_name', '') for a in item.get('authors', [])])

                    papers.append({
                        'title': item.get('title', 'No Title'),
                        'authors': authors,
                        'abstract': item.get('description', 'No abstract')[:2000],
                        'doi': item.get('doi', ''),
                        'pdf_url': pdf_url,
                        'year': str(item.get('published_date', '')[:4]) if item.get('published_date') else '',
                        'journal': 'Figshare',
                        'source': 'Figshare'
                    })
                except Exception as e:
                    log_error(self.error_logs, "Figshare Parser", e, "Item parsing failed")
        except Exception as e:
            log_error(self.error_logs, "Figshare", e, f"query={query}")
        return papers

    def _search_ssrn(self, query: str, max_results: int) -> List[Dict]:
        """Search SSRN"""
        papers = []
        try:
            url = f"https://www.ssrn.com/index.cfm/en/search/?search_name={quote(query)}"
            
            try:
                self._rate_limit()
                response = self.session.get(url, timeout=30)
                response.raise_for_status()
            except Exception as e:
                log_error(self.error_logs, "SSRN", e, f"Connection failed: {query}")
                return papers
                
            soup = BeautifulSoup(response.content, 'html.parser')

            articles = soup.find_all('div', class_=re.compile(r'result|article|paper', re.I))
            if not articles:
                articles = soup.find_all('tr', class_=re.compile(r'result', re.I))

            for article in articles[:max_results]:
                try:
                    title_elem = (
                        article.find('a', class_=re.compile(r'title', re.I)) or
                        article.find('span', class_=re.compile(r'title', re.I)) or
                        article.find('h3') or
                        article.find('a', href=re.compile(r'/abstract=', re.I))
                    )
                    if not title_elem:
                        continue

                    title = title_elem.get_text(strip=True)
                    link = title_elem.get('href', '') if title_elem.name == 'a' else ''

                    authors_elem = article.find(['div', 'span'], class_=re.compile(r'author', re.I))
                    authors = authors_elem.get_text(strip=True) if authors_elem else "Unknown"

                    if link and not link.startswith('http'):
                        link = f"https://www.ssrn.com{link}"

                    pdf_url = ""
                    pdf_elem = article.find('a', href=re.compile(r'download', re.I))
                    if pdf_elem:
                        pdf_href = pdf_elem.get('href', '')
                        if pdf_href:
                            pdf_url = f"https://www.ssrn.com{pdf_href}" if not pdf_href.startswith('http') else pdf_href

                    papers.append({
                        'title': title,
                        'authors': authors,
                        'abstract': 'Abstract at SSRN',
                        'doi': '',
                        'pdf_url': pdf_url or link,
                        'year': '',
                        'journal': 'SSRN',
                        'source': 'SSRN'
                    })
                except Exception as e:
                    log_error(self.error_logs, "SSRN Parser", e, "Article parsing failed")
        except Exception as e:
            log_error(self.error_logs, "SSRN", e, f"query={query}")
        return papers

    def _search_mdpi(self, query: str, max_results: int) -> List[Dict]:
        """Search MDPI"""
        papers = []
        try:
            url = f"https://www.mdpi.com/search?q={quote(query)}&sort=relevance&page_count={max_results}"
            
            try:
                self._rate_limit()
                response = self.session.get(url, timeout=30)
                response.raise_for_status()
            except Exception as e:
                log_error(self.error_logs, "MDPI", e, f"Connection failed: {query}")
                return papers
                
            soup = BeautifulSoup(response.content, 'html.parser')

            articles = soup.find_all('div', class_=re.compile(r'article-item|generic-item|result', re.I))

            for article in articles[:max_results]:
                try:
                    title_elem = (
                        article.find('a', class_=re.compile(r'title', re.I)) or
                        article.find('h3') or
                        article.find('a', href=re.compile(r'/journal/', re.I))
                    )
                    if not title_elem:
                        continue

                    title = title_elem.get_text(strip=True)
                    link = title_elem.get('href', '')

                    if link and not link.startswith('http'):
                        link = f"https://www.mdpi.com{link}"

                    pdf_url = f"{link}/pdf" if link else ""

                    authors_elem = article.find(['div', 'p'], class_=re.compile(r'author', re.I))
                    authors = authors_elem.get_text(strip=True) if authors_elem else "Unknown"

                    year_elem = article.find('span', class_=re.compile(r'year|date', re.I))
                    year = ""
                    if year_elem:
                        year_match = re.search(r'(\d{4})', year_elem.get_text())
                        if year_match:
                            year = year_match.group(1)

                    papers.append({
                        'title': title,
                        'authors': authors,
                        'abstract': 'Abstract at MDPI',
                        'doi': '',
                        'pdf_url': pdf_url,
                        'year': year,
                        'journal': 'MDPI',
                        'source': 'MDPI'
                    })
                except Exception as e:
                    log_error(self.error_logs, "MDPI Parser", e, "Article parsing failed")
        except Exception as e:
            log_error(self.error_logs, "MDPI", e, f"query={query}")
        return papers

    def _search_scielo(self, query: str, max_results: int) -> List[Dict]:
        """Search SciELO"""
        papers = []
        try:
            url = f"https://search.scielo.org/?q={quote(query)}&lang=en&count={max_results}&sort=relevance"
            
            try:
                self._rate_limit()
                response = self.session.get(url, timeout=30)
                response.raise_for_status()
            except Exception as e:
                log_error(self.error_logs, "SciELO", e, f"Connection failed: {query}")
                return papers
                
            soup = BeautifulSoup(response.content, 'html.parser')

            articles = soup.find_all('div', class_=re.compile(r'result|item', re.I))

            for article in articles[:max_results]:
                try:
                    title_elem = article.find(['div', 'h3', 'a'], class_=re.compile(r'title', re.I))
                    if not title_elem:
                        continue

                    title = title_elem.get_text(strip=True)

                    pdf_elem = article.find('a', href=re.compile(r'pdf|download', re.I))
                    pdf_url = pdf_elem.get('href', '') if pdf_elem else ''

                    authors_elem = article.find(['div', 'p'], class_=re.compile(r'author', re.I))
                    authors = authors_elem.get_text(strip=True) if authors_elem else "Unknown"

                    year_elem = article.find('span', class_=re.compile(r'year|date', re.I))
                    year = ""
                    if year_elem:
                        year_match = re.search(r'(\d{4})', year_elem.get_text())
                        if year_match:
                            year = year_match.group(1)

                    papers.append({
                        'title': title,
                        'authors': authors,
                        'abstract': 'Abstract at SciELO',
                        'doi': '',
                        'pdf_url': pdf_url,
                        'year': year,
                        'journal': 'SciELO',
                        'source': 'SciELO'
                    })
                except Exception as e:
                    log_error(self.error_logs, "SciELO Parser", e, "Article parsing failed")
        except Exception as e:
            log_error(self.error_logs, "SciELO", e, f"query={query}")
        return papers

    def _search_redalyc(self, query: str, max_results: int) -> List[Dict]:
        """Search Redalyc"""
        papers = []
        try:
            url = f"https://www.redalyc.org/busqueda/articulos?q={quote(query)}&pag={max_results}"
            
            try:
                self._rate_limit()
                response = self.session.get(url, timeout=30)
                response.raise_for_status()
            except Exception as e:
                log_error(self.error_logs, "Redalyc", e, f"Connection failed: {query}")
                return papers
                
            soup = BeautifulSoup(response.content, 'html.parser')

            articles = soup.find_all('div', class_=re.compile(r'article|result', re.I))

            for article in articles[:max_results]:
                try:
                    title_elem = article.find(['h3', 'h4', 'a'], class_=re.compile(r'title', re.I))
                    if not title_elem:
                        continue

                    title = title_elem.get_text(strip=True)
                    link = title_elem.get('href', '')

                    if link and not link.startswith('http'):
                        link = f"https://www.redalyc.org{link}"

                    pdf_url = ""
                    pdf_elem = article.find('a', href=re.compile(r'pdf', re.I))
                    if pdf_elem:
                        pdf_url = pdf_elem.get('href', '')
                        if pdf_url and not pdf_url.startswith('http'):
                            pdf_url = f"https://www.redalyc.org{pdf_url}"

                    authors_elem = article.find(['div', 'p'], class_=re.compile(r'author', re.I))
                    authors = authors_elem.get_text(strip=True) if authors_elem else "Unknown"

                    papers.append({
                        'title': title,
                        'authors': authors,
                        'abstract': 'Abstract at Redalyc',
                        'doi': '',
                        'pdf_url': pdf_url or link,
                        'year': '',
                        'journal': 'Redalyc',
                        'source': 'Redalyc'
                    })
                except Exception as e:
                    log_error(self.error_logs, "Redalyc Parser", e, "Article parsing failed")
        except Exception as e:
            log_error(self.error_logs, "Redalyc", e, f"query={query}")
        return papers

    def _reconstruct_abstract(self, inverted_index: Dict) -> str:
        """Reconstruct abstract from OpenAlex inverted index"""
        if not inverted_index:
            return "No abstract available"
        try:
            word_positions = {}
            for word, positions in inverted_index.items():
                for pos in positions:
                    word_positions[pos] = word
            sorted_words = [word_positions[i] for i in sorted(word_positions.keys())]
            return ' '.join(sorted_words)
        except Exception as e:
            log_error(self.error_logs, "Abstract Reconstruction", e, "OpenAlex abstract failed")
            return "No abstract available"

    def _deduplicate_papers(self, papers: List[Dict]) -> List[Dict]:
        """Remove duplicate papers based on DOI/title similarity"""
        seen = {}
        unique = []

        for paper in papers:
            doi = paper.get('doi', '').lower().strip()
            title = paper.get('title', '').lower().strip()

            if doi and doi != 'n/a' and len(doi) > 5:
                key = f"doi:{doi}"
            else:
                title_clean = re.sub(r'[^\w\s]', '', title)[:60].strip()
                key = f"title:{title_clean}"

            is_duplicate = False
            if key in seen:
                is_duplicate = True
            else:
                for existing_key in seen:
                    if existing_key.startswith('title:'):
                        existing_title = existing_key[6:]
                        if abs(len(existing_title) - len(title_clean)) < 5:
                            if title_clean in existing_title or existing_title in title_clean:
                                is_duplicate = True
                                break

            if not is_duplicate:
                seen[key] = True
                unique.append(paper)

        return unique

    def _process_papers(self, papers: List[Dict]):
        """Download PDFs and compile abstracts"""
        pdf_count = 0
        abstract_count = 0
        failed_downloads = 0

        for i, paper in enumerate(papers, 1):
            pdf_path = None
            if paper.get('pdf_url'):
                pdf_path = self._download_pdf(paper['pdf_url'], paper, i)

                if pdf_path and self._is_valid_pdf(pdf_path):
                    paper['local_pdf_path'] = pdf_path
                    paper['access_type'] = 'PDF'
                    paper['file_size'] = os.path.getsize(pdf_path)
                    pdf_count += 1
                else:
                    if pdf_path and os.path.exists(pdf_path):
                        os.remove(pdf_path)
                    paper['local_pdf_path'] = ''
                    paper['access_type'] = 'Abstract Only'
                    paper['download_failed'] = True
                    abstract_count += 1
                    failed_downloads += 1
            else:
                paper['local_pdf_path'] = ''
                paper['access_type'] = 'Abstract Only'
                abstract_count += 1

            self.results.append(paper)

        if abstract_count > 0:
            self._compile_abstracts_pdf()

    def _is_valid_pdf(self, filepath: str) -> bool:
        """Verify file is a valid PDF"""
        try:
            if not os.path.exists(filepath):
                return False

            size = os.path.getsize(filepath)
            if size < 1000:
                return False

            with open(filepath, 'rb') as f:
                header = f.read(4)
                if header != b'%PDF':
                    return False

            if fitz is None:
                return True

            doc = fitz.open(filepath)
            page_count = len(doc)
            doc.close()
            return page_count > 0

        except Exception as e:
            log_error(self.error_logs, "PDF Validation", e, f"File: {filepath}")
            return False

    def _download_pdf(self, url: str, paper: Dict, index: int) -> Optional[str]:
        """Download PDF from URL with multiple fallback strategies"""
        if not url:
            return None

        safe_title = re.sub(r'[^\w\s-]', '', paper['title'])[:50].strip()
        if not safe_title:
            safe_title = f"paper_{index}"

        filename = f"{index:03d}_{safe_title}.pdf"
        filepath = os.path.join(self.full_pdf_folder, filename)

        if os.path.exists(filepath) and self._is_valid_pdf(filepath):
            return filepath

        strategies = [{'url': url, 'headers': {}}]

        if paper.get('pmcid'):
            pmcid = paper['pmcid'].replace('PMC', '').strip()
            strategies.extend([
                {'url': f"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC{pmcid}/pdf/main.pdf", 'headers': {}},
                {'url': f"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC{pmcid}/pdf/", 'headers': {}},
            ])

        if paper.get('pmcid') and paper.get('source') == 'Europe PMC':
            pmcid = paper['pmcid'].replace('PMC', '').strip()
            strategies.append({
                'url': f"https://www.ebi.ac.uk/europepmc/backend/ptpmcrender.fcgi?accid=PMC{pmcid}&blobtype=pdf",
                'headers': {}
            })

        if paper.get('doi'):
            strategies.append({'url': None, 'doi': paper['doi'], 'headers': {}})

        for strategy in strategies:
            try:
                if 'doi' in strategy:
                    unpaywall_url = f"https://api.unpaywall.org/v2/{strategy['doi']}?email=researcher@example.com"
                    self._rate_limit()
                    up_response = self.session.get(unpaywall_url, timeout=10)

                    if up_response.status_code == 200:
                        up_data = up_response.json()
                        pdf_url = up_data.get('best_oa_location', {}).get('url_for_pdf', '')
                        if pdf_url:
                            self._rate_limit()
                            response = self.session.get(pdf_url, timeout=60, stream=True)
                        else:
                            continue
                    else:
                        continue
                else:
                    self._rate_limit()
                    response = self.session.get(
                        strategy['url'],
                        timeout=60,
                        stream=True,
                        allow_redirects=True,
                        headers=strategy['headers']
                    )

                if response.status_code == 200:
                    with open(filepath, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)

                    if self._is_valid_pdf(filepath):
                        return filepath
                    else:
                        os.remove(filepath)

            except Exception as e:
                log_error(self.error_logs, f"PDF Download ({paper.get('source', 'unknown')})", e, f"URL: {url[:50]}...")
                continue

        return None

    def _compile_abstracts_pdf(self):
        """Compile all abstracts into a formatted PDF"""
        try:
            if fitz is None:
                log_warning(self.warning_logs, "PDF Compilation", "PyMuPDF not available")
                return

            doc = fitz.open()
            page = doc.new_page()

            title_text = f"""Dr.R L - Literature Search Results

Abstract Compilation

Query: {self.query}

Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}

Total Abstracts: {len([r for r in self.results if r['access_type'] == 'Abstract Only'])}

Generated by Dr.R L AI Agent"""

            page.insert_text((72, 72), title_text, fontsize=14)

            for paper in self.results:
                if paper['access_type'] == 'Abstract Only':
                    page = doc.new_page()
                    content = f"""TITLE: {paper['title']}

AUTHORS: {paper['authors']}

SOURCE: {paper['source']} | YEAR: {paper.get('year', 'N/A')}

JOURNAL: {paper.get('journal', 'N/A')}

DOI: {paper.get('doi', 'N/A')}

PMID: {paper.get('pmid', 'N/A')}

PMCID: {paper.get('pmcid', 'N/A')}

PDF URL: {paper.get('pdf_url', 'N/A')}

ABSTRACT:

{paper['abstract']}

{'='*70}"""

                    text_area = fitz.Rect(72, 72, page.rect.width-72, page.rect.height-72)
                    page.insert_textbox(text_area, content, fontsize=10)

            abstracts_pdf_path = os.path.join(self.abstracts_folder, "Compiled_Abstracts.pdf")
            doc.save(abstracts_pdf_path)
            doc.close()

        except Exception as e:
            log_error(self.error_logs, "Abstract Compilation", e, "PDF creation failed")

    def _generate_csv_log(self):
        """Generate comprehensive CSV log file"""
        csv_path = os.path.join(self.session_folder, "Research_Log.csv")
        df_data = []

        for paper in self.results:
            df_data.append({
                'Title': paper['title'],
                'Authors': paper['authors'],
                'Year': paper.get('year', ''),
                'Journal': paper.get('journal', ''),
                'Source': paper['source'],
                'Access_Type': paper['access_type'],
                'DOI': paper.get('doi', ''),
                'PMID': paper.get('pmid', ''),
                'PMCID': paper.get('pmcid', ''),
                'ArXiv_ID': paper.get('arxiv_id', ''),
                'PDF_URL': paper.get('pdf_url', ''),
                'Local_File_Path': paper.get('local_pdf_path', ''),
                'File_Size_Bytes': paper.get('file_size', ''),
                'Download_Failed': paper.get('download_failed', False),
                'Relevance_Score': paper.get('relevance_score', 0)
            })

        df = pd.DataFrame(df_data)
        df.to_csv(csv_path, index=False, encoding='utf-8-sig')
        return csv_path

    def _save_all_logs(self):
        """Save all error, warning, and search logs to files"""
        if self.error_logs:
            errors_df = pd.DataFrame(self.error_logs)
            errors_path = os.path.join(self.errors_folder, "Error_Log.csv")
            errors_df.to_csv(errors_path, index=False, encoding='utf-8-sig')

        if self.warning_logs:
            warnings_df = pd.DataFrame(self.warning_logs)
            warnings_path = os.path.join(self.errors_folder, "Warning_Log.csv")
            warnings_df.to_csv(warnings_path, index=False, encoding='utf-8-sig')

        if self.search_logs:
            search_df = pd.DataFrame(self.search_logs)
            search_path = os.path.join(self.errors_folder, "Search_Log.csv")
            search_df.to_csv(search_path, index=False, encoding='utf-8-sig')

    def _create_download_package(self) -> Dict:
        """Create zip file for download"""
        zip_path = f"{self.session_folder}.zip"

        if os.path.exists(zip_path):
            os.remove(zip_path)

        shutil.make_archive(self.session_folder, 'zip', self.session_folder)

        pdf_count = len([r for r in self.results if r['access_type'] == 'PDF'])
        abstract_count = len([r for r in self.results if r['access_type'] == 'Abstract Only'])

        return {
            'zip_path': zip_path,
            'folder_path': self.session_folder,
            'total_papers': len(self.results),
            'pdf_count': pdf_count,
            'abstract_count': abstract_count,
            'session_id': self.session_id,
            'error_count': len(self.error_logs),
            'warning_count': len(self.warning_logs)
        }
