"""Relevance-based memory retrieval for the self-evolution agent.

Provides contextual recall instead of fixed-window slicing.
Uses TF-IDF style keyword matching — no external dependencies.
"""
import json
import math
import os
import re
from collections import Counter
from typing import Dict, List, Any

from config import MEMORY_DIR
from core.memory import get_knowledge_base, get_evolution_state


STOPWORDS = {
    'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
    'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
    'should', 'may', 'might', 'shall', 'can', 'need', 'dare', 'ought',
    'to', 'of', 'in', 'for', 'on', 'with', 'at', 'by', 'from', 'as',
    'into', 'through', 'during', 'before', 'after', 'above', 'below',
    'between', 'out', 'off', 'over', 'under', 'again', 'further', 'then',
    'once', 'that', 'this', 'these', 'those', 'and', 'but', 'or', 'nor',
    'not', 'so', 'very', 'just', 'than', 'too', 'also', 'if', 'when',
    'which', 'who', 'whom', 'what', 'where', 'how', 'all', 'each',
    'every', 'both', 'few', 'more', 'most', 'other', 'some', 'such',
    'no', 'only', 'own', 'same', 'it', 'its', 'they', 'them', 'their',
    'we', 'us', 'our', 'you', 'your', 'he', 'him', 'his', 'she', 'her',
    'e', 'g', 'i', 'implement', 'create', 'build', 'add', 'make',
    'system', 'module', 'function', 'class', 'method', 'file',
}


def _tokenize(text: str) -> List[str]:
    """Extract meaningful keywords from text."""
    text = text.lower()
    words = re.findall(r'[a-z_][a-z0-9_]*', text)
    return [w for w in words if w not in STOPWORDS and len(w) > 2]


def _compute_idf(corpus: List[List[str]]) -> Dict[str, float]:
    """Compute inverse document frequency for a corpus of tokenized docs."""
    n_docs = len(corpus)
    if n_docs == 0:
        return {}
    doc_freq = Counter()
    for tokens in corpus:
        doc_freq.update(set(tokens))
    return {word: math.log(n_docs / (1 + freq)) for word, freq in doc_freq.items()}


def _score_relevance(query_tokens: List[str], doc_tokens: List[str], idf: Dict[str, float]) -> float:
    """Score relevance of a document to a query using TF-IDF cosine-like overlap."""
    if not query_tokens or not doc_tokens:
        return 0.0
    query_set = set(query_tokens)
    doc_counter = Counter(doc_tokens)
    score = 0.0
    for word in query_set:
        if word in doc_counter:
            tf = 1 + math.log(doc_counter[word])
            score += tf * idf.get(word, 1.0)
    return score


def _load_meta_cognition() -> Dict[str, Any]:
    """Load meta-cognition log."""
    path = os.path.join(MEMORY_DIR, "meta_cognition_log.json")
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"sessions": [], "paradigm_shifts": [], "blind_spots_discovered": []}


def recall_relevant(query: str, top_k: int = 3) -> Dict[str, List[Dict[str, Any]]]:
    """Retrieve memories most relevant to a query from all stores.

    Returns dict with keys: failures, successes, insights, paradigm_shifts
    Each value is a list of the top-k most relevant entries.
    """
    kb = get_knowledge_base()
    meta = _load_meta_cognition()
    query_tokens = _tokenize(query)

    if not query_tokens:
        return {"failures": [], "successes": [], "insights": [], "paradigm_shifts": []}

    results = {}

    # Score failures
    failures = kb.get("failed_approaches", [])
    if failures:
        docs = [_tokenize(f"{f.get('approach', '')} {f.get('reason', '')}") for f in failures]
        idf = _compute_idf(docs)
        scored = [(i, _score_relevance(query_tokens, d, idf)) for i, d in enumerate(docs)]
        scored.sort(key=lambda x: x[1], reverse=True)
        results["failures"] = [failures[i] for i, s in scored[:top_k] if s > 0]
    else:
        results["failures"] = []

    # Score successes
    successes = kb.get("successful_strategies", [])
    if successes:
        docs = [_tokenize(f"{s.get('strategy', '')} {s.get('outcome', '')}") for s in successes]
        idf = _compute_idf(docs)
        scored = [(i, _score_relevance(query_tokens, d, idf)) for i, d in enumerate(docs)]
        scored.sort(key=lambda x: x[1], reverse=True)
        results["successes"] = [successes[i] for i, s in scored[:top_k] if s > 0]
    else:
        results["successes"] = []

    # Score insights
    insights = kb.get("insights", [])
    if insights:
        docs = [_tokenize(i.get("content", "")) for i in insights]
        idf = _compute_idf(docs)
        scored = [(i, _score_relevance(query_tokens, d, idf)) for i, d in enumerate(docs)]
        scored.sort(key=lambda x: x[1], reverse=True)
        results["insights"] = [insights[i] for i, s in scored[:top_k] if s > 0]
    else:
        results["insights"] = []

    # Score paradigm shifts
    shifts = meta.get("paradigm_shifts", [])
    if shifts:
        docs = [_tokenize(s.get("insight", "")) for s in shifts]
        idf = _compute_idf(docs)
        scored = [(i, _score_relevance(query_tokens, d, idf)) for i, d in enumerate(docs)]
        scored.sort(key=lambda x: x[1], reverse=True)
        results["paradigm_shifts"] = [shifts[i] for i, s in scored[:top_k] if s > 0]
    else:
        results["paradigm_shifts"] = []

    return results


def recall_lessons(goal: str) -> str:
    """Retrieve and format relevant memories as a ready-to-inject prompt context.

    This is the primary interface for all LLM call sites.
    Returns a concise, formatted string of relevant past experience.
    """
    memories = recall_relevant(goal, top_k=3)
    parts = []

    # Format relevant failures with their reasons
    for f in memories.get("failures", []):
        approach = f.get("approach", "")[:100]
        reason = f.get("reason", "")[:100]
        if approach:
            parts.append(f"[Past failure] \"{approach}\" failed because: {reason}")

    # Format relevant successes
    for s in memories.get("successes", []):
        strategy = s.get("strategy", "")[:100]
        outcome = s.get("outcome", "")[:80]
        if strategy:
            parts.append(f"[Successful pattern] \"{strategy}\" -> {outcome}")

    # Format relevant insights
    for i in memories.get("insights", []):
        content = i.get("content", "")[:150]
        if content:
            parts.append(f"[Insight] {content}")

    # Format paradigm shifts
    for p in memories.get("paradigm_shifts", []):
        insight = p.get("insight", "")[:150]
        if insight:
            parts.append(f"[Meta-insight] {insight}")

    if not parts:
        return ""

    return "Relevant experience from past cycles:\n" + "\n".join(parts)


def get_failure_patterns() -> List[Dict[str, Any]]:
    """Aggregate failure patterns — which approaches fail most and why.

    Returns top recurring failure themes with counts and common reasons.
    """
    kb = get_knowledge_base()
    failures = kb.get("failed_approaches", [])
    if not failures:
        return []

    # Extract key phrases from approaches and group
    pattern_counter: Dict[str, Dict[str, Any]] = {}
    for f in failures:
        approach = f.get("approach", "")
        reason = f.get("reason", "")
        # Extract the core action type
        tokens = _tokenize(approach)
        key_phrase = " ".join(tokens[:5]) if tokens else "unknown"
        if key_phrase not in pattern_counter:
            pattern_counter[key_phrase] = {"count": 0, "reasons": [], "example": approach[:100]}
        pattern_counter[key_phrase]["count"] += 1
        if reason and len(pattern_counter[key_phrase]["reasons"]) < 3:
            pattern_counter[key_phrase]["reasons"].append(reason[:80])

    # Sort by frequency
    patterns = sorted(pattern_counter.values(), key=lambda x: x["count"], reverse=True)
    return patterns[:10]


def get_unacted_insights() -> List[str]:
    """Find paradigm shifts and insights that were recorded but never influenced behavior.

    Detects insights about problems that continued to recur after the insight was recorded.
    """
    meta = _load_meta_cognition()
    kb = get_knowledge_base()

    shifts = meta.get("paradigm_shifts", [])
    failures_after = kb.get("failed_approaches", [])

    unacted = []
    for shift in shifts:
        shift_time = shift.get("timestamp", 0)
        insight_text = shift.get("insight", "")
        insight_tokens = set(_tokenize(insight_text))

        if not insight_tokens:
            continue

        # Check if failures after this insight contain related keywords
        later_failures = [f for f in failures_after if f.get("timestamp", 0) > shift_time]
        related_later = 0
        for f in later_failures:
            f_tokens = set(_tokenize(f.get("approach", "") + " " + f.get("reason", "")))
            overlap = len(insight_tokens & f_tokens)
            if overlap >= 3:
                related_later += 1

        if related_later >= 2:
            unacted.append(f"[Unacted insight] \"{insight_text[:120]}\" — {related_later} related failures occurred AFTER this realization")

    return unacted[:5]
