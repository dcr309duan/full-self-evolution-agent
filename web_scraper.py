import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from datetime import datetime

def scrape(url):
    """
    Scrape a webpage and return its title, text content, and links.
    
    Args:
        url (str): The URL of the webpage to scrape.
    
    Returns:
        dict: A dictionary with keys 'title', 'text', and 'links'.
              Returns None if an error occurs.
    """
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
        
        return {
            'title': title,
            'text': text,
            'links': links
        }
    
    except requests.exceptions.RequestException as e:
        print(f"Error fetching {url}: {e}")
        return None
    except Exception as e:
        print(f"Error parsing {url}: {e}")
        return None


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