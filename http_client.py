import urllib.request
import urllib.error
import socket
from typing import Optional, Dict, Any

class HttpClient:
    """Minimal HTTP client for fetching web pages."""
    
    def __init__(self, timeout: int = 10, user_agent: str = "Mozilla/5.0"):
        self.timeout = timeout
        self.user_agent = user_agent
    
    def fetch(self, url: str, headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """
        Fetch a web page and return its content and metadata.
        
        Args:
            url: The URL to fetch
            headers: Optional additional HTTP headers
            
        Returns:
            Dictionary with keys: 'success', 'content', 'status_code', 'error'
        """
        result = {
            'success': False,
            'content': None,
            'status_code': None,
            'error': None
        }
        
        if not url or not isinstance(url, str):
            result['error'] = "Invalid URL provided"
            return result
        
        # Prepare request
        req = urllib.request.Request(url)
        req.add_header('User-Agent', self.user_agent)
        if headers:
            for key, value in headers.items():
                req.add_header(key, value)
        
        try:
            # Execute request with timeout
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                result['status_code'] = response.getcode()
                # Read content and decode
                raw_content = response.read()
                # Try to decode as UTF-8, fallback to latin-1
                try:
                    result['content'] = raw_content.decode('utf-8')
                except UnicodeDecodeError:
                    result['content'] = raw_content.decode('latin-1')
                result['success'] = True
                
        except urllib.error.HTTPError as e:
            result['status_code'] = e.code
            result['error'] = f"HTTP Error {e.code}: {e.reason}"
            # Try to read error body if available
            try:
                result['content'] = e.read().decode('utf-8', errors='replace')
            except Exception:
                pass
                
        except urllib.error.URLError as e:
            result['error'] = f"URL Error: {e.reason}"
            
        except socket.timeout:
            result['error'] = f"Request timed out after {self.timeout} seconds"
            
        except Exception as e:
            result['error'] = f"Unexpected error: {str(e)}"
        
        return result
    
    def fetch_bytes(self, url: str, headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """
        Fetch a web page and return raw bytes content.
        Useful for non-text content.
        """
        result = {
            'success': False,
            'content': None,
            'status_code': None,
            'error': None
        }
        
        if not url or not isinstance(url, str):
            result['error'] = "Invalid URL provided"
            return result
        
        req = urllib.request.Request(url)
        req.add_header('User-Agent', self.user_agent)
        if headers:
            for key, value in headers.items():
                req.add_header(key, value)
        
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                result['status_code'] = response.getcode()
                result['content'] = response.read()
                result['success'] = True
                
        except urllib.error.HTTPError as e:
            result['status_code'] = e.code
            result['error'] = f"HTTP Error {e.code}: {e.reason}"
            try:
                result['content'] = e.read()
            except Exception:
                pass
                
        except urllib.error.URLError as e:
            result['error'] = f"URL Error: {e.reason}"
            
        except socket.timeout:
            result['error'] = f"Request timed out after {self.timeout} seconds"
            
        except Exception as e:
            result['error'] = f"Unexpected error: {str(e)}"
        
        return result


# Example usage
if __name__ == "__main__":
    client = HttpClient(timeout=5)
    
    # Test with a simple URL
    result = client.fetch("http://example.com")
    if result['success']:
        print(f"Success! Status code: {result['status_code']}")
        print(f"Content length: {len(result['content'])} characters")
        print(f"First 200 chars: {result['content'][:200]}")
    else:
        print(f"Failed: {result['error']}")