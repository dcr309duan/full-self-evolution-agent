"""Web dashboard for monitoring the Self-Evolution Agent."""
import json
import os
import sys
import time
from http.server import HTTPServer, SimpleHTTPRequestHandler

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import PROJECT_ROOT, LOGS_DIR, MEMORY_DIR
from core.memory import get_evolution_state, get_knowledge_base, get_goals


def get_dashboard_data():
    """Collect all data for the dashboard."""
    state = get_evolution_state()
    kb = get_knowledge_base()
    goals = get_goals()

    history = state.get("history", [])
    total = len(history)
    successes = sum(1 for h in history if h.get("success"))
    recent = history[-20:]
    recent_success = sum(1 for h in recent if h.get("success"))

    log_lines = []
    log_path = os.path.join(LOGS_DIR, "evolution.log")
    if os.path.exists(log_path):
        with open(log_path, 'r') as f:
            log_lines = f.readlines()[-50:]

    return {
        "cycle": state.get("cycle_count", 0),
        "generation": state.get("current_generation", 1),
        "status": state.get("status", "unknown"),
        "last_activity": state.get("last_evolution_time"),
        "capabilities": state.get("capabilities", []),
        "history": history[-30:],
        "total_cycles": total,
        "total_successes": successes,
        "success_rate": round(successes / total * 100, 1) if total > 0 else 0,
        "recent_success_rate": round(recent_success / len(recent) * 100, 1) if recent else 0,
        "insights": kb.get("insights", [])[-10:],
        "strategies": kb.get("successful_strategies", [])[-5:],
        "failures": kb.get("failed_approaches", [])[-5:],
        "pending_goals": [g for g in goals.get("sub_goals", []) if g["status"] == "pending"],
        "completed_goals": goals.get("completed_goals", [])[-10:],
        "log_lines": log_lines,
        "meta_cognition": _get_meta_cognition_data(),
    }


def _get_meta_cognition_data():
    meta_path = os.path.join(MEMORY_DIR, "meta_cognition_log.json")
    try:
        with open(meta_path, 'r') as f:
            data = json.load(f)
        return {
            "total_sessions": len(data.get("sessions", [])),
            "paradigm_shifts": data.get("paradigm_shifts", [])[-5:],
            "blind_spots": data.get("blind_spots_discovered", [])[-5:],
            "last_session": data.get("sessions", [{}])[-1] if data.get("sessions") else None,
        }
    except (FileNotFoundError, json.JSONDecodeError):
        return {"total_sessions": 0, "paradigm_shifts": [], "blind_spots": [], "last_session": None}


DASHBOARD_HTML = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>自进化智能体 - 监控面板</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { 
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: #0f1117; color: #e1e4e8; min-height: 100vh;
}
.header {
    background: linear-gradient(135deg, #1a1f35 0%, #0d1117 100%);
    border-bottom: 1px solid #21262d;
    padding: 20px 40px;
    display: flex; justify-content: space-between; align-items: center;
}
.header h1 { font-size: 22px; color: #58a6ff; }
.header .status-badge {
    padding: 6px 16px; border-radius: 20px; font-size: 13px; font-weight: 600;
    text-transform: uppercase; letter-spacing: 0.5px;
}
.status-evolving { background: #1b4332; color: #40c057; border: 1px solid #2d6a4f; }
.status-paused { background: #3d2e00; color: #f5a623; border: 1px solid #5c4400; }
.status-error { background: #3d0000; color: #f85149; border: 1px solid #5c0000; }
.container { max-width: 1400px; margin: 0 auto; padding: 24px; }
.grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 24px; }
.metric-card {
    background: #161b22; border: 1px solid #21262d; border-radius: 12px;
    padding: 20px; text-align: center;
}
.metric-card .value { font-size: 36px; font-weight: 700; color: #58a6ff; }
.metric-card .label { font-size: 12px; color: #8b949e; margin-top: 6px; text-transform: uppercase; letter-spacing: 0.5px; }
.section {
    background: #161b22; border: 1px solid #21262d; border-radius: 12px;
    padding: 24px; margin-bottom: 20px;
}
.section h2 { font-size: 16px; color: #c9d1d9; margin-bottom: 16px; display: flex; align-items: center; gap: 8px; }
.section h2::before { content: ''; width: 4px; height: 18px; background: #58a6ff; border-radius: 2px; }
.two-col { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
.capability-list { list-style: none; }
.capability-list li {
    padding: 10px 14px; margin-bottom: 6px; background: #0d1117;
    border-radius: 8px; border-left: 3px solid #238636; font-size: 13px;
}
.goal-item {
    padding: 10px 14px; margin-bottom: 6px; background: #0d1117;
    border-radius: 8px; display: flex; align-items: center; gap: 10px; font-size: 13px;
}
.goal-priority {
    background: #1f6feb; color: #fff; border-radius: 10px;
    padding: 2px 8px; font-size: 11px; font-weight: 600; min-width: 28px; text-align: center;
}
.completed-goal { text-decoration: line-through; color: #8b949e; }
.activity-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.activity-table th { text-align: left; padding: 10px; color: #8b949e; border-bottom: 1px solid #21262d; }
.activity-table td { padding: 10px; border-bottom: 1px solid #21262d; }
.result-success { color: #3fb950; font-weight: 600; }
.result-failed { color: #f85149; font-weight: 600; }
.insight-item { padding: 8px 12px; margin-bottom: 6px; background: #0d1117; border-radius: 6px; font-size: 12px; border-left: 3px solid #8957e5; overflow-wrap: break-word; white-space: pre-wrap; }
.insight-time { color: #8b949e; font-size: 11px; }
.log-area {
    background: #010409; border: 1px solid #21262d; border-radius: 8px;
    padding: 16px; font-family: 'JetBrains Mono', 'Fira Code', monospace;
    font-size: 11px; line-height: 1.6; max-height: 400px; overflow-y: auto;
    white-space: pre-wrap; word-break: break-all; color: #8b949e;
}
.chart-bar { display: flex; align-items: center; gap: 8px; margin-bottom: 4px; }
.chart-bar .bar { height: 20px; border-radius: 4px; min-width: 2px; transition: width 0.3s; }
.chart-bar .bar-success { background: #238636; }
.chart-bar .bar-fail { background: #f85149; }
.chart-bar .bar-label { font-size: 11px; color: #8b949e; min-width: 40px; }
.refresh-info { text-align: center; color: #484f58; font-size: 12px; margin-top: 20px; }
.gen-badge { background: #8957e5; color: #fff; padding: 4px 10px; border-radius: 12px; font-size: 12px; font-weight: 600; }
@media (max-width: 768px) {
    .grid { grid-template-columns: repeat(2, 1fr); }
    .two-col { grid-template-columns: 1fr; }
    .container { padding: 12px; }
    .header { padding: 16px 20px; }
}
</style>
</head>
<body>
<div class="header">
    <h1>自进化智能体</h1>
    <div>
        <span class="gen-badge" id="gen-badge">第 1 代</span>
        <span class="status-badge status-evolving" id="status-badge">加载中</span>
    </div>
</div>
<div class="container">
    <div class="grid">
        <div class="metric-card"><div class="value" id="m-cycle">-</div><div class="label">进化周期</div></div>
        <div class="metric-card"><div class="value" id="m-rate">-</div><div class="label">成功率</div></div>
        <div class="metric-card"><div class="value" id="m-caps">-</div><div class="label">已获能力</div></div>
        <div class="metric-card"><div class="value" id="m-goals">-</div><div class="label">已完成目标</div></div>
    </div>

    <div class="two-col">
        <div class="section">
            <h2>已获得能力</h2>
            <ul class="capability-list" id="cap-list"></ul>
        </div>
        <div class="section">
            <h2>待完成目标</h2>
            <div id="goal-list"></div>
        </div>
    </div>

    <div class="section">
        <h2>最近活动</h2>
        <table class="activity-table">
            <thead><tr><th>周期</th><th>目标</th><th>结果</th><th>时间</th></tr></thead>
            <tbody id="activity-body"></tbody>
        </table>
    </div>

    <div class="two-col">
        <div class="section">
            <h2>最新洞察</h2>
            <div id="insights-list"></div>
        </div>
        <div class="section">
            <h2>成功率趋势（近20轮）</h2>
            <div id="chart-area"></div>
        </div>
    </div>

    <div class="section" style="border-left: 3px solid #8957e5;">
        <h2>递归元认知</h2>
        <div style="display:flex;gap:24px;margin-bottom:16px;">
            <div><span style="color:#8b949e;font-size:12px;">元认知会话</span><br><span style="font-size:20px;color:#8957e5;" id="meta-sessions">0</span></div>
            <div><span style="color:#8b949e;font-size:12px;">范式转移</span><br><span style="font-size:20px;color:#f0883e;" id="meta-shifts">0</span></div>
            <div><span style="color:#8b949e;font-size:12px;">盲区发现</span><br><span style="font-size:20px;color:#f85149;" id="meta-blinds">0</span></div>
        </div>
        <div id="meta-details"></div>
    </div>

    <div class="section">
        <h2>实时日志</h2>
        <div class="log-area" id="log-area">加载中...</div>
    </div>

    <div class="refresh-info">每 10 秒自动刷新 | <span id="last-update"></span></div>
</div>

<script>
function formatTime(ts) {
    if (!ts) return '-';
    const d = new Date(ts * 1000);
    return d.toLocaleString('zh-CN', {month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit'});
}

function updateDashboard(data) {
    document.getElementById('m-cycle').textContent = data.cycle;
    document.getElementById('m-rate').textContent = data.success_rate + '%';
    document.getElementById('m-caps').textContent = data.capabilities.length;
    document.getElementById('m-goals').textContent = data.completed_goals.length;
    document.getElementById('gen-badge').textContent = '第 ' + data.generation + ' 代';

    const statusMap = {evolving:'进化中', paused:'已暂停', initialized:'已初始化', error:'异常'};
    const badge = document.getElementById('status-badge');
    badge.textContent = statusMap[data.status] || data.status;
    badge.className = 'status-badge status-' + (data.status === 'evolving' ? 'evolving' : data.status === 'paused' ? 'paused' : 'error');

    const capList = document.getElementById('cap-list');
    capList.innerHTML = data.capabilities.map(c => '<li>' + c + '</li>').join('') || '<li style="color:#8b949e">暂无</li>';

    const goalList = document.getElementById('goal-list');
    goalList.innerHTML = data.pending_goals.slice(0, 8).map(g =>
        '<div class="goal-item"><span class="goal-priority">' + (g.priority||'?') + '</span>' + g.description + '</div>'
    ).join('') || '<div style="color:#8b949e">暂无待完成目标</div>';

    const tbody = document.getElementById('activity-body');
    tbody.innerHTML = data.history.slice().reverse().slice(0, 15).map(h =>
        '<tr><td>' + h.cycle + '</td><td>' + (h.goal||'').substring(0,70) + '</td><td class="' +
        (h.success ? 'result-success' : 'result-failed') + '">' + (h.success ? '成功' : '失败') +
        '</td><td>' + formatTime(h.timestamp) + '</td></tr>'
    ).join('');

    const insightsList = document.getElementById('insights-list');
    insightsList.innerHTML = data.insights.slice().reverse().map(i =>
        '<div class="insight-item"><span class="insight-time">' + formatTime(i.timestamp) + '</span> ' + i.content.substring(0,150) + '</div>'
    ).join('') || '<div style="color:#8b949e">暂无洞察</div>';

    const chartArea = document.getElementById('chart-area');
    const last20 = data.history.slice(-20);
    chartArea.innerHTML = last20.map(h =>
        '<div class="chart-bar"><span class="chart-bar-label">C' + h.cycle + '</span>' +
        '<div class="bar ' + (h.success ? 'bar-success' : 'bar-fail') + '" style="width:' + (h.success ? '100' : '40') + 'px"></div></div>'
    ).join('');

    document.getElementById('log-area').textContent = data.log_lines.join('');

    // Meta-cognition
    const meta = data.meta_cognition || {};
    document.getElementById('meta-sessions').textContent = meta.total_sessions || 0;
    document.getElementById('meta-shifts').textContent = (meta.paradigm_shifts || []).length;
    document.getElementById('meta-blinds').textContent = (meta.blind_spots || []).length;
    let metaHtml = '';
    (meta.paradigm_shifts || []).slice().reverse().forEach(s => {
        metaHtml += '<div class="insight-item" style="border-left-color:#f0883e;word-wrap:break-word;white-space:pre-wrap;"><span class="insight-time">' + formatTime(s.timestamp) + '</span> <strong>[范式转移]</strong> ' + (s.insight||'') + '</div>';
    });
    (meta.blind_spots || []).slice().reverse().forEach(b => {
        metaHtml += '<div class="insight-item" style="border-left-color:#f85149;word-wrap:break-word;white-space:pre-wrap;"><span class="insight-time">' + formatTime(b.timestamp) + '</span> <strong>[盲区]</strong> ' + (b.description||'') + '</div>';
    });
    document.getElementById('meta-details').innerHTML = metaHtml || '<span style="color:#8b949e;font-size:12px;">等待第一次元认知会话（每10轮触发）</span>';

    document.getElementById('last-update').textContent = '最后更新: ' + new Date().toLocaleTimeString('zh-CN');
}

function fetchData() {
    fetch('/api/status')
        .then(r => r.json())
        .then(updateDashboard)
        .catch(e => console.error('Fetch error:', e));
}

fetchData();
setInterval(fetchData, 10000);
</script>
</body>
</html>'''


class DashboardHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/' or self.path == '/index.html':
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(DASHBOARD_HTML.encode('utf-8'))
        elif self.path == '/api/status':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            data = get_dashboard_data()
            self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass


def run_dashboard(host='0.0.0.0', port=8080):
    server = HTTPServer((host, port), DashboardHandler)
    print(f"[Dashboard] Running at http://{host}:{port}")
    server.serve_forever()


if __name__ == '__main__':
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    run_dashboard(port=port)
