from flask import Flask, jsonify, render_template_string
import json
import random
import time
from collections import defaultdict

app = Flask(__name__)

# Simulated data store (in production, this would come from a database or monitoring system)
module_health = {
    "auth-service": "green",
    "payment-gateway": "yellow",
    "inventory-api": "red",
    "notification-service": "green",
    "user-db": "yellow",
    "cache-layer": "green",
    "search-index": "red",
    "logging-service": "green"
}

dependency_graph = {
    "nodes": [
        {"id": "auth-service", "group": 1},
        {"id": "payment-gateway", "group": 2},
        {"id": "inventory-api", "group": 3},
        {"id": "notification-service", "group": 4},
        {"id": "user-db", "group": 5},
        {"id": "cache-layer", "group": 6},
        {"id": "search-index", "group": 7},
        {"id": "logging-service", "group": 8}
    ],
    "links": [
        {"source": "auth-service", "target": "payment-gateway", "value": 1},
        {"source": "auth-service", "target": "inventory-api", "value": 2},
        {"source": "payment-gateway", "target": "notification-service", "value": 1},
        {"source": "inventory-api", "target": "user-db", "value": 3},
        {"source": "inventory-api", "target": "cache-layer", "value": 2},
        {"source": "user-db", "target": "search-index", "value": 1},
        {"source": "cache-layer", "target": "search-index", "value": 1},
        {"source": "notification-service", "target": "logging-service", "value": 1}
    ]
}

failure_rates = {
    "auth-service": [0.02, 0.03, 0.01, 0.04, 0.02, 0.05, 0.03, 0.02, 0.01, 0.03],
    "payment-gateway": [0.05, 0.07, 0.04, 0.06, 0.08, 0.05, 0.09, 0.06, 0.07, 0.05],
    "inventory-api": [0.12, 0.15, 0.10, 0.18, 0.14, 0.20, 0.16, 0.13, 0.17, 0.15],
    "notification-service": [0.01, 0.02, 0.01, 0.03, 0.01, 0.02, 0.01, 0.02, 0.01, 0.02],
    "user-db": [0.08, 0.06, 0.09, 0.07, 0.10, 0.08, 0.11, 0.07, 0.09, 0.08],
    "cache-layer": [0.03, 0.02, 0.04, 0.03, 0.02, 0.05, 0.03, 0.04, 0.02, 0.03],
    "search-index": [0.15, 0.18, 0.12, 0.20, 0.16, 0.22, 0.19, 0.14, 0.21, 0.17],
    "logging-service": [0.01, 0.01, 0.02, 0.01, 0.01, 0.02, 0.01, 0.01, 0.02, 0.01]
}

underutilized_components = [
    {"name": "cache-layer", "usage_percent": 15, "recommendation": "Consider downsizing or sharing with other services"},
    {"name": "logging-service", "usage_percent": 22, "recommendation": "Evaluate consolidation with notification service"},
    {"name": "search-index", "usage_percent": 18, "recommendation": "Optimize indexing frequency or reduce resources"}
]

critical_alerts = [
    {"module": "inventory-api", "severity": "critical", "message": "Integration conflict with payment-gateway: incompatible API version v2.1 vs v3.0"},
    {"module": "search-index", "severity": "critical", "message": "Database connection timeout after 30 seconds - possible deadlock with user-db"},
    {"module": "payment-gateway", "severity": "warning", "message": "Response time exceeding SLA by 40% - investigate upstream dependency"}
]

# New data for consistency checks and repair queue
consistency_checks = [
    {"id": 1, "module": "auth-service", "check_type": "API Schema", "status": "pass", "timestamp": "2024-01-15 10:30:00"},
    {"id": 2, "module": "payment-gateway", "check_type": "Data Integrity", "status": "fail", "timestamp": "2024-01-15 10:35:00"},
    {"id": 3, "module": "inventory-api", "check_type": "Cache Sync", "status": "warning", "timestamp": "2024-01-15 10:40:00"},
    {"id": 4, "module": "notification-service", "check_type": "Queue Depth", "status": "pass", "timestamp": "2024-01-15 10:45:00"},
    {"id": 5, "module": "user-db", "check_type": "Replication Lag", "status": "fail", "timestamp": "2024-01-15 10:50:00"},
    {"id": 6, "module": "cache-layer", "check_type": "TTL Consistency", "status": "pass", "timestamp": "2024-01-15 10:55:00"},
    {"id": 7, "module": "search-index", "check_type": "Index Sync", "status": "warning", "timestamp": "2024-01-15 11:00:00"},
    {"id": 8, "module": "logging-service", "check_type": "Log Format", "status": "pass", "timestamp": "2024-01-15 11:05:00"}
]

repair_queue = [
    {"id": 1, "module": "payment-gateway", "mismatch_type": "API Version Mismatch", "severity": "high", "description": "Payment gateway v3.0 expects v2.1 API but receiving v2.0"},
    {"id": 2, "module": "user-db", "mismatch_type": "Data Schema Drift", "severity": "high", "description": "User database schema has diverged from expected schema by 3 fields"},
    {"id": 3, "module": "inventory-api", "mismatch_type": "Cache Inconsistency", "severity": "medium", "description": "Inventory cache shows 150 items but database has 145 items"},
    {"id": 4, "module": "search-index", "mismatch_type": "Index Out of Sync", "severity": "medium", "description": "Search index is 2 hours behind database updates"},
    {"id": 5, "module": "auth-service", "mismatch_type": "Token Format", "severity": "low", "description": "JWT token format differs from standard by expiration field order"}
]

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Dashboard - Module Health Monitor</title>
    <script src="https://d3js.org/d3.v7.min.js"></script>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }
        .container { max-width: 1400px; margin: 0 auto; }
        h1 { color: #333; text-align: center; }
        .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-top: 20px; }
        .card { background: white; border-radius: 8px; padding: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .card h2 { margin-top: 0; color: #555; }
        .heatmap { display: flex; flex-wrap: wrap; gap: 10px; }
        .module-box { padding: 15px; border-radius: 5px; color: white; font-weight: bold; text-align: center; min-width: 120px; }
        .green { background-color: #4CAF50; }
        .yellow { background-color: #FFC107; color: #333; }
        .red { background-color: #F44336; }
        .graph-container { width: 100%; height: 400px; }
        .chart-container { width: 100%; height: 300px; }
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 10px; text-align: left; border-bottom: 1px solid #ddd; }
        th { background-color: #f2f2f2; }
        .alert { padding: 10px; margin: 5px 0; border-radius: 5px; }
        .alert.critical { background-color: #ffebee; border-left: 4px solid #F44336; }
        .alert.warning { background-color: #fff3e0; border-left: 4px solid #FF9800; }
        .full-width { grid-column: 1 / -1; }
        .status-pass { color: #4CAF50; font-weight: bold; }
        .status-fail { color: #F44336; font-weight: bold; }
        .status-warning { color: #FF9800; font-weight: bold; }
        .severity-high { background-color: #ffebee; }
        .severity-medium { background-color: #fff3e0; }
        .severity-low { background-color: #e8f5e9; }
        .repair-item { padding: 10px; margin: 5px 0; border-radius: 5px; border-left: 4px solid #999; }
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 System Dashboard</h1>
        <div class="grid">
            <div class="card">
                <h2>Module Health Heatmap</h2>
                <div class="heatmap" id="heatmap"></div>
            </div>
            <div class="card">
                <h2>Dependency Graph</h2>
                <div class="graph-container" id="dependency-graph"></div>
            </div>
            <div class="card full-width">
                <h2>Failure Rates Over Time</h2>
                <div class="chart-container" id="failure-chart"></div>
            </div>
            <div class="card">
                <h2>Underutilized Components</h2>
                <table id="underutilized-table">
                    <thead>
                        <tr>
                            <th>Component</th>
                            <th>Usage %</th>
                            <th>Recommendation</th>
                        </tr>
                    </thead>
                    <tbody></tbody>
                </table>
            </div>
            <div class="card">
                <h2>Critical Alerts</h2>
                <div id="alerts-container"></div>
            </div>
            <div class="card full-width">
                <h2>Recent Consistency Checks</h2>
                <table id="consistency-table">
                    <thead>
                        <tr>
                            <th>ID</th>
                            <th>Module</th>
                            <th>Check Type</th>
                            <th>Status</th>
                            <th>Timestamp</th>
                        </tr>
                    </thead>
                    <tbody></tbody>
                </table>
            </div>
            <div class="card full-width">
                <h2>Repair Queue - Pending Mismatches</h2>
                <div id="repair-queue-container"></div>
            </div>
        </div>
    </div>
    <script>
        // Load data from API
        async function loadData() {
            const response = await fetch('/api/dashboard');
            const data = await response.json();
            
            // Render heatmap
            const heatmap = document.getElementById('heatmap');
            heatmap.innerHTML = '';
            data.module_health.forEach(([name, status]) => {
                const div = document.createElement('div');
                div.className = `module-box ${status}`;
                div.textContent = name;
                heatmap.appendChild(div);
            });
            
            // Render dependency graph
            renderGraph(data.dependency_graph, data.module_health);
            
            // Render failure chart
            renderFailureChart(data.failure_rates);
            
            // Render underutilized table
            const tableBody = document.querySelector('#underutilized-table tbody');
            tableBody.innerHTML = '';
            data.underutilized_components.forEach(comp => {
                const row = document.createElement('tr');
                row.innerHTML = `<td>${comp.name}</td><td>${comp.usage_percent}%</td><td>${comp.recommendation}</td>`;
                tableBody.appendChild(row);
            });
            
            // Render alerts
            const alertsContainer = document.getElementById('alerts-container');
            alertsContainer.innerHTML = '';
            data.critical_alerts.forEach(alert => {
                const div = document.createElement('div');
                div.className = `alert ${alert.severity}`;
                div.innerHTML = `<strong>${alert.module}</strong> (${alert.severity}): ${alert.message}`;
                alertsContainer.appendChild(div);
            });
            
            // Render consistency checks table
            const consistencyBody = document.querySelector('#consistency-table tbody');
            consistencyBody.innerHTML = '';
            data.consistency_checks.forEach(check => {
                const row = document.createElement('tr');
                const statusClass = `status-${check.status}`;
                row.innerHTML = `<td>${check.id}</td><td>${check.module}</td><td>${check.check_type}</td><td class="${statusClass}">${check.status}</td><td>${check.timestamp}</td>`;
                consistencyBody.appendChild(row);
            });
            
            // Render repair queue
            const repairContainer = document.getElementById('repair-queue-container');
            repairContainer.innerHTML = '';
            data.repair_queue.forEach(item => {
                const div = document.createElement('div');
                div.className = `repair-item severity-${item.severity}`;
                div.style.borderLeftColor = item.severity === 'high' ? '#F44336' : item.severity === 'medium' ? '#FF9800' : '#4CAF50';
                div.innerHTML = `<strong>${item.module}</strong> - ${item.mismatch_type}<br>
                                 <em>Severity: ${item.severity}</em><br>
                                 ${item.description}`;
                repairContainer.appendChild(div);
            });
        }
        
        function renderGraph(graphData, moduleHealth) {
            const width = document.getElementById('dependency-graph').clientWidth;
            const height = 400;
            
            // Clear previous graph
            d3.select('#dependency-graph').selectAll('*').remove();
            
            const svg = d3.select('#dependency-graph')
                .append('svg')
                .attr('width', width)
                .attr('height', height);
            
            const simulation = d3.forceSimulation(graphData.nodes)
                .force('link', d3.forceLink(graphData.links).id(d => d.id).distance(100))
                .force('charge', d3.forceManyBody().strength(-200))
                .force('center', d3.forceCenter(width / 2, height / 2));
            
            const link = svg.append('g')
                .selectAll('line')
                .data(graphData.links)
                .enter().append('line')
                .attr('stroke', '#999')
                .attr('stroke-opacity', 0.6)
                .attr('stroke-width', d => Math.sqrt(d.value));
            
            const node = svg.append('g')
                .selectAll('circle')
                .data(graphData.nodes)
                .enter().append('circle')
                .attr('r', 10)
                .attr('fill', d => {
                    const health = moduleHealth.find(m => m[0] === d.id);
                    return health ? (health[1] === 'green' ? '#4CAF50' : health[1] === 'yellow' ? '#FFC107' : '#F44336') : '#999';
                })
                .call(d3.drag()
                    .on('start', (event, d) => {
                        if (!event.active) simulation.alphaTarget(0.3).restart();
                        d.fx = d.x;
                        d.fy = d.y;
                    })
                    .on('drag', (event, d) => {
                        d.fx = event.x;
                        d.fy = event.y;
                    })
                    .on('end', (event, d) => {
                        if (!event.active) simulation.alphaTarget(0);
                        d.fx = null;
                        d.fy = null;
                    }));
            
            const label = svg.append('g')
                .selectAll('text')
                .data(graphData.nodes)
                .enter().append('text')
                .text(d => d.id)
                .attr('font-size', 12)
                .attr('dx', 15)
                .attr('dy', 4);
            
            simulation.on('tick', () => {
                link.attr('x1', d => d.source.x)
                    .attr('y1', d => d.source.y)
                    .attr('x2', d => d.target.x)
                    .attr('y2', d => d.target.y);
                
                node.attr('cx', d => d.x)
                    .attr('cy', d => d.y);
                
                label.attr('x', d => d.x)
                    .attr('y', d => d.y);
            });
        }
        
        function renderFailureChart(failureData) {
            const width = document.getElementById('failure-chart').clientWidth;
            const height = 300;
            const margin = {top: 20, right: 30, bottom: 30, left: 50};
            
            // Clear previous chart
            d3.select('#failure-chart').selectAll('*').remove();
            
            const svg = d3.select('#failure-chart')
                .append('svg')
                .attr('width', width)
                .attr('height', height);
            
            const xScale = d3.scaleLinear()
                .domain([0, 9])
                .range([margin.left, width - margin.right]);
            
            const yScale = d3.scaleLinear()
                .domain([0, 0.25])
                .range([height - margin.bottom, margin.top]);
            
            const color = d3.scaleOrdinal(d3.schemeCategory10);
            
            Object.entries(failureData).forEach(([module, rates], i) => {
                const line = d3.line()
                    .x((d, i) => xScale(i))
                    .y(d => yScale(d))
                    .curve(d3.curveMonotoneX);
                
                svg.append('path')
                    .datum(rates)
                    .attr('fill', 'none')
                    .attr('stroke', color(i))
                    .attr('stroke-width', 2)
                    .attr('d', line);
                
                // Add legend
                svg.append('text')
                    .attr('x', width - 120)
                    .attr('y', margin.top + i * 20)
                    .attr('fill', color(i))
                    .attr('font-size', 12)
                    .text(module);
            });
            
            // Add axes
            svg.append('g')
                .attr('transform', `translate(0,${height - margin.bottom})`)
                .call(d3.axisBottom(xScale).ticks(10));
            
            svg.append('g')
                .attr('transform', `translate(${margin.left},0)`)
                .call(d3.axisLeft(yScale));
        }
        
        // Initial load and refresh every 10 seconds
        loadData();
        setInterval(loadData, 10000);
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/dashboard')
def get_dashboard_data():
    # Simulate real-time updates by slightly modifying data
    for module in module_health:
        if random.random() < 0.1:  # 10% chance of status change
            module_health[module] = random.choice(['green', 'yellow', 'red'])
    
    # Update failure rates with slight random variation
    for module in failure_rates:
        if random.random() < 0.3:
            failure_rates[module].append(round(random.uniform(0.01, 0.25), 2))
            if len(failure_rates[module]) > 20:
                failure_rates[module] = failure_rates[module][-20:]
    
    # Simulate consistency checks updates
    updated_checks = []
    for check in consistency_checks:
        if random.random() < 0.2:  # 20% chance of status change
            check["status"] = random.choice(["pass", "fail", "warning"])
        updated_checks.append(check)
    
    # Simulate repair queue updates
    updated_queue = []
    for item in repair_queue:
        if random.random() < 0.1:  # 10% chance of severity change
            item["severity"] = random.choice(["high", "medium", "low"])
        updated_queue.append(item)
    
    return jsonify({
        "module_health": list(module_health.items()),
        "dependency_graph": dependency_graph,
        "failure_rates": failure_rates,
        "underutilized_components": underutilized_components,
        "critical_alerts": critical_alerts,
        "consistency_checks": updated_checks,
        "repair_queue": updated_queue
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)