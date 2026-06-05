"""Internet knowledge acquisition module.

Enables the agent to fetch, process, and learn from web content.
This breaks the agent out of the closed-world assumption and allows
it to discover new techniques, libraries, and approaches.
"""
import json
import os
import sys
import time
import urllib.request
import urllib.error
from html.parser import HTMLParser

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.llm import call_deepseek
from core.memory import add_insight, get_knowledge_base, save_knowledge_base
from config import MEMORY_DIR


class SimpleHTMLTextExtractor(HTMLParser):
    """Extract readable text from HTML."""
    
    def __init__(self):
        super().__init__()
        self.text_parts = []
        self.skip_tags = {'script', 'style', 'nav', 'footer', 'header'}
        self._skip = False
    
    def handle_starttag(self, tag, attrs):
        if tag in self.skip_tags:
            self._skip = True
    
    def handle_endtag(self, tag):
        if tag in self.skip_tags:
            self._skip = False
    
    def handle_data(self, data):
        if not self._skip:
            text = data.strip()
            if text:
                self.text_parts.append(text)
    
    def get_text(self):
        return '\n'.join(self.text_parts)


def fetch_url(url, timeout=15):
    """Fetch a URL and return text content."""
    try:
        req = urllib.request.Request(url, headers={
            'User-Agent': 'SelfEvolutionAgent/1.0 (research bot)'
        })
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            html = resp.read().decode('utf-8', errors='ignore')
        
        extractor = SimpleHTMLTextExtractor()
        extractor.feed(html)
        return extractor.get_text()[:8000]
    except Exception as e:
        return f"Error fetching {url}: {str(e)}"


def search_and_learn(query, num_sources=3):
    """Search for knowledge on a topic and extract learnings.
    
    Uses a simple approach: fetch known high-quality sources.
    """
    knowledge_sources = [
        f"https://en.wikipedia.org/wiki/{query.replace(' ', '_')}",
    ]
    
    all_content = []
    for url in knowledge_sources[:num_sources]:
        content = fetch_url(url)
        if not content.startswith("Error"):
            all_content.append(f"Source: {url}\n{content[:3000]}")
    
    if not all_content:
        return {"success": False, "reason": "Could not fetch any sources"}
    
    combined = '\n\n---\n\n'.join(all_content)
    
    prompt = f"""Analyze the following web content and extract useful knowledge for a self-evolving AI agent.

Content:
{combined[:5000]}

Extract:
1. Key concepts and techniques mentioned
2. Anything applicable to software engineering or AI systems
3. Novel approaches or patterns we haven't considered

Output JSON:
{{"key_learnings": [...], "applicable_techniques": [...], "novel_ideas": [...], "summary": "..."}}
"""
    
    messages = [
        {"role": "system", "content": "You extract actionable knowledge from web content for an AI agent."},
        {"role": "user", "content": prompt}
    ]
    
    response = call_deepseek(messages, temperature=0.4)
    
    try:
        start = response.find('{')
        end = response.rfind('}') + 1
        if start >= 0 and end > start:
            result = json.loads(response[start:end])
            for learning in result.get("key_learnings", [])[:3]:
                add_insight(f"[Web学习] {learning[:150]}")
            return {"success": True, "data": result}
    except json.JSONDecodeError:
        pass
    
    return {"success": False, "reason": "Failed to parse learnings"}


def research_topic(topic):
    """Deep research on a specific topic relevant to self-evolution."""
    prompt = f"""I am a self-evolving AI agent. I want to research: {topic}

Based on your knowledge, provide:
1. State of the art approaches
2. Key papers/techniques I should know about
3. Practical implementation strategies
4. Common pitfalls to avoid
5. Unconventional approaches worth trying

Output JSON:
{{"state_of_art": "...", "key_techniques": [...], "implementation_strategies": [...], "pitfalls": [...], "unconventional": [...]}}
"""
    
    messages = [
        {"role": "system", "content": "You are a research assistant helping a self-evolving AI agent learn new domains."},
        {"role": "user", "content": prompt}
    ]
    
    response = call_deepseek(messages, temperature=0.5, max_tokens=4096)
    
    try:
        start = response.find('{')
        end = response.rfind('}') + 1
        if start >= 0 and end > start:
            result = json.loads(response[start:end])
            add_insight(f"[研究] {topic}: {result.get('state_of_art', '')[:100]}")
            save_research(topic, result)
            return {"success": True, "data": result}
    except json.JSONDecodeError:
        pass
    
    return {"success": False, "reason": "Parse failed", "raw": response[:500]}


def save_research(topic, data):
    """Save research results to knowledge base."""
    path = os.path.join(MEMORY_DIR, "research_log.json")
    try:
        with open(path, 'r') as f:
            log = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        log = []
    
    log.append({"topic": topic, "data": data, "timestamp": time.time()})
    if len(log) > 50:
        log = log[-50:]
    
    with open(path, 'w') as f:
        json.dump(log, f, indent=2, ensure_ascii=False)


def autonomous_research_cycle():
    """Decide what to research based on current gaps and curiosity."""
    kb = get_knowledge_base()
    recent_failures = kb.get("failed_approaches", [])[-5:]
    
    prompt = f"""I am a self-evolving AI agent. Based on my recent failures and knowledge gaps, 
suggest 3 research topics that would help me evolve faster.

Recent failures: {json.dumps([f.get('approach','')[:80] for f in recent_failures], ensure_ascii=False)}

My current capabilities: web scraping, task scheduling, self-evaluation, testing, mutation engine, AST rewriting

Suggest topics that would enable fundamentally new capabilities or fix recurring problems.
Output JSON array of strings (topic names only).
"""
    
    messages = [
        {"role": "system", "content": "Suggest research topics for an AI agent."},
        {"role": "user", "content": prompt}
    ]
    
    response = call_deepseek(messages, temperature=0.7)
    
    try:
        start = response.find('[')
        end = response.rfind(']') + 1
        if start >= 0 and end > start:
            topics = json.loads(response[start:end])
            results = []
            for topic in topics[:2]:
                result = research_topic(topic)
                results.append({"topic": topic, "result": result})
            return results
    except (json.JSONDecodeError, ValueError):
        pass
    
    return research_topic("self-modifying code architectures")


if __name__ == "__main__":
    print("Testing internet knowledge acquisition...")
    result = research_topic("genetic programming and code evolution")
    print(json.dumps(result, indent=2, ensure_ascii=False)[:1000])
