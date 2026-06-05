from html.parser import HTMLParser
from typing import List, Tuple

class SimpleHTMLParser(HTMLParser):
    """
    A simple HTML parser that extracts text content and hyperlinks from HTML.
    """
    def __init__(self):
        super().__init__()
        self.text_parts: List[str] = []
        self.links: List[Tuple[str, str]] = []  # (url, link_text)
        self._current_tag: str = ""
        self._current_link_text: str = ""
        self._in_link: bool = False

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, str]]) -> None:
        self._current_tag = tag
        if tag == 'a':
            self._in_link = True
            self._current_link_text = ""
            for attr_name, attr_value in attrs:
                if attr_name == 'href':
                    self.links.append((attr_value, ""))

    def handle_endtag(self, tag: str) -> None:
        if tag == 'a' and self._in_link:
            self._in_link = False
            # Update the last link with its text
            if self.links:
                last_url, _ = self.links[-1]
                self.links[-1] = (last_url, self._current_link_text.strip())
        self._current_tag = ""

    def handle_data(self, data: str) -> None:
        # Collect text data
        stripped = data.strip()
        if stripped:
            self.text_parts.append(stripped)
        # If inside a link, also collect link text
        if self._in_link:
            self._current_link_text += data

    def get_text(self) -> str:
        """Return all extracted text as a single string."""
        return ' '.join(self.text_parts)

    def get_links(self) -> List[Tuple[str, str]]:
        """Return list of (url, link_text) tuples."""
        return self.links

    def reset(self) -> None:
        """Reset parser state for reuse."""
        super().reset()
        self.text_parts = []
        self.links = []
        self._current_tag = ""
        self._current_link_text = ""
        self._in_link = False


def parse_html(html_content: str) -> Tuple[str, List[Tuple[str, str]]]:
    """
    Parse HTML content and return extracted text and links.
    
    Args:
        html_content: Raw HTML string to parse
        
    Returns:
        Tuple of (text_content, list_of_links)
        where each link is (url, link_text)
    """
    parser = SimpleHTMLParser()
    parser.feed(html_content)
    return parser.get_text(), parser.get_links()


# Example usage (commented out)
if __name__ == "__main__":
    sample_html = """
    <html>
        <body>
            <h1>Hello World</h1>
            <p>This is a paragraph with a <a href="https://example.com">link</a>.</p>
            <p>Another paragraph with <a href="https://test.com">another link</a>.</p>
        </body>
    </html>
    """
    text, links = parse_html(sample_html)
    print("Extracted text:", text)
    print("Extracted links:", links)