import requests
from bs4 import BeautifulSoup
import time
import threading
from datetime import datetime, timedelta

class Scheduler:
    def __init__(self):
        self.tasks = []
        self.running = False
        self.execution_count = 0

    def add_task(self, interval, task):
        self.tasks.append({'interval': interval, 'task': task, 'last_run': None})

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._run)
        self.thread.start()

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join()

    def _run(self):
        while self.running:
            current_time = datetime.now()
            for task in self.tasks:
                if task['last_run'] is None or (current_time - task['last_run']).total_seconds() >= task['interval']:
                    task['task']()
                    task['last_run'] = current_time
                    self.execution_count += 1
            time.sleep(1)

def scrape_url(url):
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        return soup
    except requests.exceptions.RequestException as e:
        print(f"Error fetching {url}: {e}")
        return None

def main():
    url = "http://example.com"
    print(f"Scraping {url}...")
    soup = scrape_url(url)
    if soup:
        print("Title:", soup.title.string if soup.title else "No title found")
        print("First paragraph:", soup.find('p').get_text() if soup.find('p') else "No paragraph found")
        print("All links:")
        for link in soup.find_all('a'):
            href = link.get('href')
            text = link.get_text(strip=True)
            if href:
                print(f"  - {text}: {href}")
    else:
        print("Failed to scrape the URL.")

def test_scheduler_integration():
    scheduler = Scheduler()
    
    # Create a scrape task with 10-second interval
    url = "http://example.com"
    def scrape_task():
        soup = scrape_url(url)
        if soup:
            print(f"[{datetime.now()}] Scraped {url} - Title: {soup.title.string if soup.title else 'No title'}")
    
    scheduler.add_task(10, scrape_task)
    
    # Run for 30 seconds
    scheduler.start()
    print("Scheduler started. Running for 30 seconds...")
    time.sleep(30)
    scheduler.stop()
    
    # Verify at least 2 executions occurred
    assert scheduler.execution_count >= 2, f"Expected at least 2 executions, got {scheduler.execution_count}"
    print(f"Test passed: {scheduler.execution_count} executions occurred (expected at least 2)")
    
    # Clean up
    print("Cleanup complete.")

if __name__ == "__main__":
    # Run the original main function
    main()
    
    # Run the scheduler integration test
    print("\n--- Running Scheduler Integration Test ---")
    test_scheduler_integration()