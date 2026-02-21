import os
import json
import logging
import requests
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

class DrRLAgent:
    def __init__(self):
        self.groq_api_key = os.environ.get('GROQ_API_KEY')
        self.groq_api_url = "https://api.groq.com/openai/v1/chat/completions"
        
        if not self.groq_api_key:
            logger.error("❌ GROQ_API_KEY not set - agent cannot function")
            raise ValueError("GROQ_API_KEY environment variable is required")
        
        logger.info("✅ DrRLAgent initialized with Groq API")
        
        # Database configurations
        self.databases = {
            'pubmed': 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi',
            'europe_pmc': 'https://www.ebi.ac.uk/europepmc/webservices/rest/search',
            'arxiv': 'http://export.arxiv.org/api/query',
            'openalex': 'https://api.openalex.org/works'
        }
    
    def search(self, query: str, max_results: int = 20) -> List[Dict[str, Any]]:
        """
        Main search function - queries multiple databases and uses Groq for synthesis
        """
        if not query or not query.strip():
            logger.warning("Empty query received")
            return []
        
        query = query.strip()
        logger.info(f"🔍 Starting search for: '{query}' (max: {max_results})")
        
        all_results = []
        search_errors = []
        
        # Search each database with error isolation
        for db_name, db_url in self.databases.items():
            try:
                logger.info(f"   Searching {db_name}...")
                db_results = self._search_database(db_name, db_url, query, max_results // 4 + 1)
                all_results.extend(db_results)
                logger.info(f"   ✓ {db_name}: found {len(db_results)} results")
            except Exception as e:
                error_msg = f"{db_name}: {str(e)}"
                search_errors.append(error_msg)
                logger.error(f"   ✗ {error_msg}")
                continue
        
        # If all databases failed, inform the user
        if not all_results and search_errors:
            logger.error("All database searches failed")
            return [{
                'title': 'Search Error',
                'error': True,
                'message': 'All database searches failed',
                'details': search_errors,
                'source': 'system',
                'year': 2024
            }]
        
        # Use Groq to rank/synthesize results if we have many
        if len(all_results) > 5 and self.groq_api_key:
            try:
                all_results = self._rank_with_groq(query, all_results, max_results)
            except Exception as e:
                logger.error(f"Groq ranking failed: {e}")
                # Fall back to basic sorting
                all_results = self._basic_sort(all_results)[:max_results]
        else:
            all_results = self._basic_sort(all_results)[:max_results]
        
        logger.info(f"✅ Search complete: returning {len(all_results)} results")
        return all_results
    
    def _search_database(self, db_name: str, db_url: str, query: str, limit: int) -> List[Dict]:
        """Search individual database with proper error handling"""
        try:
            if db_name == 'pubmed':
                return self._search_pubmed(db_url, query, limit)
            elif db_name == 'europe_pmc':
                return self._search_europe_pmc(db_url, query, limit)
            elif db_name == 'arxiv':
                return self._search_arxiv(db_url, query, limit)
            elif db_name == 'openalex':
                return self._search_openalex(db_url, query, limit)
            else:
                logger.warning(f"Unknown database: {db_name}")
                return []
        except Exception as e:
            logger.error(f"Database search error ({db_name}): {e}")
            raise
    
    def _search_pubmed(self, base_url: str, query: str, limit: int) -> List[Dict]:
        """Search PubMed Central"""
        try:
            # Search for IDs first
            search_params = {
                'db': 'pmc',
                'term': query,
                'retmode': 'json',
                'retmax': limit
            }
            
            response = requests.get(base_url, params=search_params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            ids = data.get('esearchresult', {}).get('idlist', [])
            if not ids:
                return []
            
            # Fetch summaries (limited to avoid overwhelming the API)
            summary_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
            summary_params = {
                'db': 'pmc',
                'id': ','.join(ids[:limit]),
                'retmode': 'json'
            }
            
            sum_response = requests.get(summary_url, params=summary_params, timeout=10)
            sum_response.raise_for_status()
            sum_data = sum_response.json()
            
            results = []
            for uid, article in sum_data.get('result', {}).items():
                if uid == 'uids':
                    continue
                results.append({
                    'title': article.get('title', 'No title'),
                    'authors': article.get('authors', []),
                    'year': article.get('pubdate', '2024')[:4],
                    'source': 'PubMed Central',
                    'url': f"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC{uid}/",
                    'abstract': article.get('abstract', 'No abstract available')[:500] + '...'
                })
            
            return results
            
        except requests.exceptions.Timeout:
            raise Exception("PubMed API timeout")
        except requests.exceptions.RequestException as e:
            raise Exception(f"PubMed API error: {str(e)}")
        except Exception as e:
            raise Exception(f"PubMed parsing error: {str(e)}")
    
    def _search_europe_pmc(self, base_url: str, query: str, limit: int) -> List[Dict]:
        """Search Europe PMC"""
        try:
            params = {
                'query': query,
                'format': 'json',
                'pageSize': limit,
                'resultType': 'lite'
            }
            
            response = requests.get(base_url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            results = []
            for item in data.get('resultList', {}).get('result', []):
                results.append({
                    'title': item.get('title', 'No title'),
                    'authors': [a.get('fullName', '') for a in item.get('authorList', {}).get('author', [])],
                    'year': item.get('pubYear', '2024'),
                    'source': 'Europe PMC',
                    'url': item.get('fullTextUrlList', {}).get('fullTextUrl', [{}])[0].get('url', ''),
                    'abstract': item.get('abstractText', 'No abstract available')[:500] + '...'
                })
            
            return results
            
        except requests.exceptions.Timeout:
            raise Exception("Europe PMC API timeout")
        except requests.exceptions.RequestException as e:
            raise Exception(f"Europe PMC API error: {str(e)}")
        except Exception as e:
            raise Exception(f"Europe PMC parsing error: {str(e)}")
    
    def _search_arxiv(self, base_url: str, query: str, limit: int) -> List[Dict]:
        """Search arXiv"""
        try:
            import xml.etree.ElementTree as ET
            
            params = {
                'search_query': f'all:{query}',
                'start': 0,
                'max_results': limit
            }
            
            response = requests.get(base_url, params=params, timeout=10)
            response.raise_for_status()
            
            # Parse Atom XML
            root = ET.fromstring(response.content)
            ns = {'atom': 'http://www.w3.org/2005/Atom'}
            
            results = []
            for entry in root.findall('atom:entry', ns):
                title = entry.find('atom:title', ns)
                summary = entry.find('atom:summary', ns)
                published = entry.find('atom:published', ns)
                id_elem = entry.find('atom:id', ns)
                
                # Get authors
                authors = []
                for author in entry.findall('atom:author', ns):
                    name = author.find('atom:name', ns)
                    if name is not None:
                        authors.append(name.text)
                
                if title is not None:
                    results.append({
                        'title': title.text.strip(),
                        'authors': authors,
                        'year': published.text[:4] if published is not None else '2024',
                        'source': 'arXiv',
                        'url': id_elem.text if id_elem is not None else '',
                        'abstract': (summary.text[:500] + '...') if summary is not None else 'No abstract'
                    })
            
            return results
            
        except requests.exceptions.Timeout:
            raise Exception("arXiv API timeout")
        except requests.exceptions.RequestException as e:
            raise Exception(f"arXiv API error: {str(e)}")
        except Exception as e:
            raise Exception(f"arXiv parsing error: {str(e)}")
    
    def _search_openalex(self, base_url: str, query: str, limit: int) -> List[Dict]:
        """Search OpenAlex"""
        try:
            params = {
                'search': query,
                'per-page': limit,
                'filter': 'has_pdf:true'
            }
            
            response = requests.get(base_url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            results = []
            for work in data.get('results', []):
                authorships = work.get('authorships', [])
                authors = [a.get('author', {}).get('display_name', '') for a in authorships]
                
                # Get best PDF URL
                open_access = work.get('open_access', {})
                pdf_url = open_access.get('oa_url', '')
                
                results.append({
                    'title': work.get('display_name', 'No title'),
                    'authors': authors,
                    'year': work.get('publication_year', '2024'),
                    'source': 'OpenAlex',
                    'url': pdf_url or work.get('id', ''),
                    'abstract': work.get('abstract', 'No abstract available')[:500] + '...'
                })
            
            return results
            
        except requests.exceptions.Timeout:
            raise Exception("OpenAlex API timeout")
        except requests.exceptions.RequestException as e:
            raise Exception(f"OpenAlex API error: {str(e)}")
        except Exception as e:
            raise Exception(f"OpenAlex parsing error: {str(e)}")
    
    def _rank_with_groq(self, query: str, results: List[Dict], limit: int) -> List[Dict]:
        """Use Groq API to rank results by relevance"""
        try:
            # Prepare context for Groq
            results_text = "\n\n".join([
                f"{i+1}. {r['title']} ({r['source']}, {r['year']})"
                for i, r in enumerate(results[:20])  # Limit context
            ])
            
            prompt = f"""Given the search query: "{query}"
            
Rank these research papers by relevance (1 = most relevant). Return only the numbers in order of relevance, comma-separated. For example: "3,1,4,2"

Papers:
{results_text}"""
            
            headers = {
                'Authorization': f'Bearer {self.groq_api_key}',
                'Content-Type': 'application/json'
            }
            
            payload = {
                'model': 'llama-3.1-8b-instant',
                'messages': [
                    {'role': 'system', 'content': 'You are a research assistant. Respond only with comma-separated numbers.'},
                    {'role': 'user', 'content': prompt}
                ],
                'temperature': 0.1,
                'max_tokens': 100
            }
            
            response = requests.post(
                self.groq_api_url,
                headers=headers,
                json=payload,
                timeout=30
            )
            response.raise_for_status()
            
            data = response.json()
            ranking_text = data['choices'][0]['message']['content'].strip()
            
            # Parse ranking
            try:
                indices = [int(x.strip()) - 1 for x in ranking_text.split(',') if x.strip().isdigit()]
                # Reorder results
                ranked = []
                for idx in indices[:limit]:
                    if 0 <= idx < len(results):
                        ranked.append(results[idx])
                # Add any missing results at the end
                seen = set(indices)
                for i, r in enumerate(results):
                    if i not in seen and len(ranked) < limit:
                        ranked.append(r)
                return ranked
            except:
                logger.warning("Failed to parse Groq ranking, using basic sort")
                return self._basic_sort(results)[:limit]
                
        except Exception as e:
            logger.error(f"Groq ranking error: {e}")
            return self._basic_sort(results)[:limit]
    
    def _basic_sort(self, results: List[Dict]) -> List[Dict]:
        """Basic sorting by year (newest first)"""
        return sorted(results, key=lambda x: x.get('year', 0), reverse=True)
