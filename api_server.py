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


def _read_json(path, default=None):
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default or {}


@app.route('/')
def index():
    return jsonify({
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


@app.route('/api/state')
def get_state():
    state = get_evolution_state()
    return jsonify(state)


@app.route('/api/capabilities')
def get_capabilities():
    state = get_evolution_state()
    return jsonify({"capabilities": state.get("capabilities", []), "count": len(state.get("capabilities", []))})


@app.route('/api/goals')
def get_goals_api():
    goals = get_goals()
    return jsonify(goals)


@app.route('/api/knowledge')
def get_knowledge():
    kb = get_knowledge_base()
    return jsonify({
        "insights_count": len(kb.get("insights", [])),
        "successes_count": len(kb.get("successful_strategies", [])),
        "failures_count": len(kb.get("failed_approaches", [])),
        "recent_insights": kb.get("insights", [])[-10:],
        "recent_successes": kb.get("successful_strategies", [])[-5:],
    })


@app.route('/api/meta')
def get_meta():
    data = _read_json(os.path.join(MEMORY_DIR, "meta_cognition_log.json"), {})
    return jsonify({
        "total_sessions": len(data.get("sessions", [])),
        "paradigm_shifts": data.get("paradigm_shifts", []),
        "blind_spots": data.get("blind_spots_discovered", []),
    })


@app.route('/api/mutations')
def get_mutations():
    data = _read_json(os.path.join(MEMORY_DIR, "mutation_log.json"), [])
    successful = _read_json(os.path.join(MEMORY_DIR, "successful_mutations.json"), [])
    return jsonify({
        "total_cycles": len(data),
        "successful_mutations": len(successful),
        "recent": data[-5:] if isinstance(data, list) else [],
    })


@app.route('/api/research')
def get_research():
    data = _read_json(os.path.join(MEMORY_DIR, "research_log.json"), [])
    return jsonify({"total_topics": len(data), "recent": data[-5:]})


@app.route('/api/log')
def get_log():
    lines = int(request.args.get('lines', 30))
    log_path = os.path.join(LOGS_DIR, "evolution.log")
    try:
        with open(log_path, 'r') as f:
            all_lines = f.readlines()
        return jsonify({"lines": all_lines[-lines:]})
    except FileNotFoundError:
        return jsonify({"lines": []})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8081, debug=False)
