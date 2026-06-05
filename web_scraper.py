import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from datetime import datetime
from typing import List, Dict, Optional

class WebScraper:
    def __init__(self):
        self.total_scrapes = 0
        self.successful_scrapes = 0
        self.failed_scrapes = 0
        self.data_quality_scores: List[float] = []
        self.rate_limit_violations = 0
        self.sources_scraped: set = set()
        self.last_request_time: Optional[datetime] = None
        self.min_request_interval = 1.0  # seconds between requests

    def scrape(self, url: str) -> Optional[Dict]:
        """
        Scrape a webpage and return its title, text content, and links.
        
        Args:
            url (str): The URL of the webpage to scrape.
        
        Returns:
            dict: A dictionary with keys 'title', 'text', and 'links'.
                  Returns None if an error occurs.
        """
        self.total_scrapes += 1
        self.sources_scraped.add(url)
        
        # Check rate limit compliance
        if self.last_request_time:
            time_since_last = (datetime.now() - self.last_request_time).total_seconds()
            if time_since_last < self.min_request_interval:
                self.rate_limit_violations += 1
        
        try:
            # Send HTTP GET request
            response = requests.get(url, timeout=10)
            response.raise_for_status()  # Raise an exception for HTTP errors
            
            # Parse HTML content
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract page title
            title = soup.title.string.strip() if soup.title else "No title found"
            
            # Extract text content (excluding script and style elements)
            for script in soup(["script", "style"]):
                script.decompose()
            text = soup.get_text(separator='\n', strip=True)
            
            # Extract all links
            links = []
            for a_tag in soup.find_all('a', href=True):
                href = a_tag['href']
                # Convert relative URLs to absolute URLs
                absolute_url = urljoin(url, href)
                links.append(absolute_url)
            
            # Calculate data quality score
            quality_score = self._calculate_data_quality(title, text, links)
            self.data_quality_scores.append(quality_score)
            
            self.successful_scrapes += 1
            self.last_request_time = datetime.now()
            
            return {
                'title': title,
                'text': text,
                'links': links
            }
        
        except requests.exceptions.RequestException as e:
            print(f"Error fetching {url}: {e}")
            self.failed_scrapes += 1
            self.data_quality_scores.append(0.0)
            return None
        except Exception as e:
            print(f"Error parsing {url}: {e}")
            self.failed_scrapes += 1
            self.data_quality_scores.append(0.0)
            return None

    def _calculate_data_quality(self, title: str, text: str, links: List[str]) -> float:
        """
        Calculate data quality score for a scrape result.
        
        Args:
            title (str): Page title
            text (str): Page text content
            links (List[str]): Extracted links
        
        Returns:
            float: Quality score between 0 and 1
        """
        score = 0.0
        
        # Title quality (0.3 max)
        if title and title != "No title found":
            score += 0.3
        
        # Text quality (0.4 max)
        if text:
            text_length = len(text)
            if text_length > 1000:
                score += 0.4
            elif text_length > 500:
                score += 0.3
            elif text_length > 100:
                score += 0.2
            else:
                score += 0.1
        
        # Links quality (0.3 max)
        if links:
            if len(links) >= 10:
                score += 0.3
            elif len(links) >= 5:
                score += 0.2
            else:
                score += 0.1
        
        return min(score, 1.0)

    def get_health_score(self) -> float:
        """
        Calculate overall health score based on:
        - Successful scrapes vs failures
        - Data quality metrics
        - Rate limit compliance
        - Source diversity
        
        Returns:
            float: Health score between 0 and 1
        """
        if self.total_scrapes == 0:
            return 1.0  # Perfect score if no scrapes performed
        
        # Success rate (0.4 weight)
        success_rate = self.successful_scrapes / self.total_scrapes
        success_score = success_rate * 0.4
        
        # Data quality (0.3 weight)
        if self.data_quality_scores:
            avg_quality = sum(self.data_quality_scores) / len(self.data_quality_scores)
        else:
            avg_quality = 0.0
        quality_score = avg_quality * 0.3
        
        # Rate limit compliance (0.15 weight)
        if self.total_scrapes > 0:
            violation_rate = self.rate_limit_violations / self.total_scrapes
            rate_limit_score = (1 - violation_rate) * 0.15
        else:
            rate_limit_score = 0.15
        
        # Source diversity (0.15 weight)
        if self.total_scrapes > 0:
            diversity_ratio = len(self.sources_scraped) / self.total_scrapes
            diversity_score = min(diversity_ratio, 1.0) * 0.15
        else:
            diversity_score = 0.15
        
        total_score = success_score + quality_score + rate_limit_score + diversity_score
        return min(total_score, 1.0)


def scrape(url):
    """
    Scrape a webpage and return its title, text content, and links.
    
    Args:
        url (str): The URL of the webpage to scrape.
    
    Returns:
        dict: A dictionary with keys 'title', 'text', and 'links'.
              Returns None if an error occurs.
    """
    scraper = WebScraper()
    return scraper.scrape(url)


def scrape_task(url):
    """
    Wrapper function that makes the scraper compatible with the scheduler's task interface.
    Takes no arguments (url is captured from closure or passed via default), returns a dict
    with status, title, text, links, and timestamp.
    
    Args:
        url (str): The URL of the webpage to scrape.
    
    Returns:
        dict: A dictionary with keys 'status', 'title', 'text', 'links', and 'timestamp'.
              If an error occurs, returns a dict with 'status': 'error' and 'error' message.
    """
    try:
        result = scrape(url)
        if result is None:
            return {
                'status': 'error',
                'error': f'Failed to scrape {url}',
                'timestamp': datetime.now().isoformat()
            }
        
        return {
            'status': 'success',
            'title': result['title'],
            'text': result['text'],
            'links': result['links'],
            'timestamp': datetime.now().isoformat()
        }
    
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }