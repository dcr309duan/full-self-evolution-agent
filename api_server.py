"""Real API server that exposes the actual evolution agent's state and capabilities."""
import os
import sys
import json
import time
import threading

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, jsonify, request
from config import PROJECT_ROOT, MEMORY_DIR, LOGS_DIR
from core.memory import get_evolution_state, get_knowledge_base, get_goals

app = Flask(__name__)

# Health tracking metrics
_request_success_count = 0
_request_failure_count = 0
_total_response_time = 0.0
_response_count = 0
_active_endpoints = set()
_error_count = 0
_metrics_lock = threading.Lock()


def _read_json(path, default=None):
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default or {}


def _track_request(endpoint, success=True, response_time=0.0):
    """Track request metrics for health scoring."""
    global _request_success_count, _request_failure_count, _total_response_time, _response_count, _active_endpoints, _error_count
    with _metrics_lock:
        if success:
            _request_success_count += 1
        else:
            _request_failure_count += 1
            _error_count += 1
        _total_response_time += response_time
        _response_count += 1
        _active_endpoints.add(endpoint)


def get_health_score() -> float:
    """
    Calculate and return a health score between 0 and 1 based on:
    - Request success rate
    - Average response time
    - Number of active endpoints
    - Error count
    """
    with _metrics_lock:
        total_requests = _request_success_count + _request_failure_count
        if total_requests == 0:
            return 1.0  # No requests yet, assume healthy
        
        # Success rate component (0-0.5 weight)
        success_rate = _request_success_count / total_requests if total_requests > 0 else 1.0
        success_score = success_rate * 0.5
        
        # Response time component (0-0.2 weight)
        avg_response_time = _total_response_time / _response_count if _response_count > 0 else 0.0
        # Normalize: assume 1 second is max acceptable, scale inversely
        response_time_score = max(0.0, 1.0 - (avg_response_time / 1.0)) * 0.2
        
        # Active endpoints component (0-0.15 weight)
        # Assume 8 endpoints is full health
        endpoint_count = len(_active_endpoints)
        endpoint_score = min(1.0, endpoint_count / 8.0) * 0.15
        
        # Error count component (0-0.15 weight)
        # Penalize based on error ratio, assume 10% errors is threshold
        error_ratio = _error_count / total_requests if total_requests > 0 else 0.0
        error_score = max(0.0, 1.0 - (error_ratio / 0.1)) * 0.15
        
        total_score = success_score + response_time_score + endpoint_score + error_score
        return min(1.0, max(0.0, total_score))


@app.route('/')
def index():
    start_time = time.time()
    result = jsonify({
        "service": "Self-Evolution Agent API",
        "version": "1.0",
        "endpoints": [
            "GET /api/state - 进化状态",
            "GET /api/capabilities - 已获得能力",
            "GET /api/goals - 目标队列",
            "GET /api/knowledge - 知识库",
            "GET /api/meta - 元认知数据",
            "GET /api/mutations - 变异记录",
            "GET /api/research - 研究记录",
            "GET /api/log - 最近日志",
        ]
    })
    _track_request('/', success=True, response_time=time.time() - start_time)
    return result


@app.route('/api/state')
def get_state():
    start_time = time.time()
    try:
        state = get_evolution_state()
        _track_request('/api/state', success=True, response_time=time.time() - start_time)
        return jsonify(state)
    except Exception as e:
        _track_request('/api/state', success=False, response_time=time.time() - start_time)
        return jsonify({"error": str(e)}), 500


@app.route('/api/capabilities')
def get_capabilities():
    start_time = time.time()
    try:
        state = get_evolution_state()
        _track_request('/api/capabilities', success=True, response_time=time.time() - start_time)
        return jsonify({"capabilities": state.get("capabilities", []), "count": len(state.get("capabilities", []))})
    except Exception as e:
        _track_request('/api/capabilities', success=False, response_time=time.time() - start_time)
        return jsonify({"error": str(e)}), 500


@app.route('/api/goals')
def get_goals_api():
    start_time = time.time()
    try:
        goals = get_goals()
        _track_request('/api/goals', success=True, response_time=time.time() - start_time)
        return jsonify(goals)
    except Exception as e:
        _track_request('/api/goals', success=False, response_time=time.time() - start_time)
        return jsonify({"error": str(e)}), 500


@app.route('/api/knowledge')
def get_knowledge():
    start_time = time.time()
    try:
        kb = get_knowledge_base()
        _track_request('/api/knowledge', success=True, response_time=time.time() - start_time)
        return jsonify({
            "insights_count": len(kb.get("insights", [])),
            "successes_count": len(kb.get("successful_strategies", [])),
            "failures_count": len(kb.get("failed_approaches", [])),
            "recent_insights": kb.get("insights", [])[-10:],
            "recent_successes": kb.get("successful_strategies", [])[-5:],
        })
    except Exception as e:
        _track_request('/api/knowledge', success=False, response_time=time.time() - start_time)
        return jsonify({"error": str(e)}), 500


@app.route('/api/meta')
def get_meta():
    start_time = time.time()
    try:
        data = _read_json(os.path.join(MEMORY_DIR, "meta_cognition_log.json"), {})
        _track_request('/api/meta', success=True, response_time=time.time() - start_time)
        return jsonify({
            "total_sessions": len(data.get("sessions", [])),
            "paradigm_shifts": data.get("paradigm_shifts", []),
            "blind_spots": data.get("blind_spots_discovered", []),
        })
    except Exception as e:
        _track_request('/api/meta', success=False, response_time=time.time() - start_time)
        return jsonify({"error": str(e)}), 500


@app.route('/api/mutations')
def get_mutations():
    start_time = time.time()
    try:
        data = _read_json(os.path.join(MEMORY_DIR, "mutation_log.json"), [])
        successful = _read_json(os.path.join(MEMORY_DIR, "successful_mutations.json"), [])
        _track_request('/api/mutations', success=True, response_time=time.time() - start_time)
        return jsonify({
            "total_cycles": len(data),
            "successful_mutations": len(successful),
            "recent": data[-5:] if isinstance(data, list) else [],
        })
    except Exception as e:
        _track_request('/api/mutations', success=False, response_time=time.time() - start_time)
        return jsonify({"error": str(e)}), 500


@app.route('/api/research')
def get_research():
    start_time = time.time()
    try:
        data = _read_json(os.path.join(MEMORY_DIR, "research_log.json"), [])
        _track_request('/api/research', success=True, response_time=time.time() - start_time)
        return jsonify({"total_topics": len(data), "recent": data[-5:]})
    except Exception as e:
        _track_request('/api/research', success=False, response_time=time.time() - start_time)
        return jsonify({"error": str(e)}), 500


@app.route('/api/log')
def get_log():
    start_time = time.time()
    try:
        lines = int(request.args.get('lines', 30))
        log_path = os.path.join(LOGS_DIR, "evolution.log")
        with open(log_path, 'r') as f:
            all_lines = f.readlines()
        _track_request('/api/log', success=True, response_time=time.time() - start_time)
        return jsonify({"lines": all_lines[-lines:]})
    except FileNotFoundError:
        _track_request('/api/log', success=True, response_time=time.time() - start_time)
        return jsonify({"lines": []})
    except Exception as e:
        _track_request('/api/log', success=False, response_time=time.time() - start_time)
        return jsonify({"error": str(e)}), 500


@app.route('/api/health')
def health_endpoint():
    """Endpoint to get the current health score."""
    score = get_health_score()
    return jsonify({
        "health_score": score,
        "status": "healthy" if score > 0.7 else "degraded" if score > 0.4 else "unhealthy"
    })


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8081, debug=False)