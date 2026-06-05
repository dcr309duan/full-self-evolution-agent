import json
import os
from datetime import datetime
from collections import Counter

class DashboardGenerator:
    def __init__(self, data_file='failure_clusters.json', output_file='dashboard.html'):
        self.data_file = data_file
        self.output_file = output_file

    def load_clusters(self):
        if not os.path.exists(self.data_file):
            return []
        with open(self.data_file, 'r') as f:
            return json.load(f)

    def compute_summary_stats(self, clusters):
        total_failures = sum(c.get('failure_count', 0) for c in clusters)
        active_clusters = sum(1 for c in clusters if c.get('status', 'active') == 'active')
        top_errors = Counter()
        for c in clusters:
            error_type = c.get('error_type', 'Unknown')
            top_errors[error_type] += c.get('failure_count', 0)
        top_error_types = top_errors.most_common(5)
        return {
            'total_failures': total_failures,
            'active_clusters': active_clusters,
            'top_error_types': top_error_types
        }

    def generate_timeline_data(self, clusters):
        timeline = {}
        for c in clusters:
            cycle = c.get('cycle', 0)
            if cycle not in timeline:
                timeline[cycle] = 0
            timeline[cycle] += c.get('failure_count', 0)
        return dict(sorted(timeline.items()))

    def generate_cluster_table(self, clusters):
        table_rows = []
        for i, c in enumerate(clusters):
            severity = c.get('severity_score', 0)
            table_rows.append({
                'id': i + 1,
                'error_type': c.get('error_type', 'Unknown'),
                'failure_count': c.get('failure_count', 0),
                'cycle': c.get('cycle', 0),
                'severity_score': severity,
                'status': c.get('status', 'active')
            })
        return table_rows

    def generate_recommended_fixes(self, clusters):
        fixes = []
        for c in clusters:
            if c.get('status') == 'active' and c.get('severity_score', 0) > 5:
                fixes.append({
                    'error_type': c.get('error_type', 'Unknown'),
                    'severity': c.get('severity_score', 0),
                    'recommendation': c.get('recommended_fix', 'Investigate and apply patch')
                })
        return fixes

    def generate_html(self):
        clusters = self.load_clusters()
        summary = self.compute_summary_stats(clusters)
        timeline_data = self.generate_timeline_data(clusters)
        table_rows = self.generate_cluster_table(clusters)
        fixes = self.generate_recommended_fixes(clusters)

        timeline_labels = json.dumps(list(timeline_data.keys()))
        timeline_values = json.dumps(list(timeline_data.values()))

        html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Failure Cluster Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: auto; }}
        .card {{ background: white; border-radius: 8px; padding: 20px; margin: 20px 0; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .stats {{ display: flex; gap: 20px; flex-wrap: wrap; }}
        .stat-box {{ flex: 1; min-width: 200px; background: #e3f2fd; padding: 15px; border-radius: 8px; text-align: center; }}
        .stat-box h3 {{ margin: 0 0 10px 0; color: #1565c0; }}
        .stat-box p {{ font-size: 24px; font-weight: bold; margin: 0; }}
        table {{ width: 100%; border-collapse: collapse; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
        th {{ background-color: #1976d2; color: white; }}
        tr:hover {{ background-color: #f1f1f1; }}
        .severity-high {{ color: red; font-weight: bold; }}
        .severity-medium {{ color: orange; font-weight: bold; }}
        .severity-low {{ color: green; }}
        .fix-item {{ background: #fff3e0; padding: 10px; margin: 5px 0; border-left: 4px solid #ff9800; }}
        .timestamp {{ color: #666; font-size: 0.9em; }}
        .chart-container {{ height: 400px; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Failure Cluster Dashboard</h1>
        <p class="timestamp">Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>

        <div class="card">
            <h2>Summary Statistics</h2>
            <div class="stats">
                <div class="stat-box">
                    <h3>Total Failures</h3>
                    <p>{summary['total_failures']}</p>
                </div>
                <div class="stat-box">
                    <h3>Active Clusters</h3>
                    <p>{summary['active_clusters']}</p>
                </div>
                <div class="stat-box">
                    <h3>Top Error Types</h3>
                    <ul style="list-style: none; padding: 0;">
                        {''.join(f'<li>{err[0]}: {err[1]}</li>' for err in summary['top_error_types'])}
                    </ul>
                </div>
            </div>
        </div>

        <div class="card">
            <h2>Cluster Timeline</h2>
            <div class="chart-container">
                <canvas id="timelineChart"></canvas>
            </div>
        </div>

        <div class="card">
            <h2>Cluster Details</h2>
            <table>
                <thead>
                    <tr>
                        <th>ID</th>
                        <th>Error Type</th>
                        <th>Failure Count</th>
                        <th>Cycle</th>
                        <th>Severity Score</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody>
                    {''.join(f'''
                    <tr>
                        <td>{row['id']}</td>
                        <td>{row['error_type']}</td>
                        <td>{row['failure_count']}</td>
                        <td>{row['cycle']}</td>
                        <td class="{'severity-high' if row['severity_score'] > 7 else 'severity-medium' if row['severity_score'] > 4 else 'severity-low'}">{row['severity_score']}</td>
                        <td>{row['status']}</td>
                    </tr>
                    ''' for row in table_rows)}
                </tbody>
            </table>
        </div>

        <div class="card">
            <h2>Recommended Fixes</h2>
            {''.join(f'''
            <div class="fix-item">
                <strong>{fix['error_type']}</strong> (Severity: {fix['severity']})<br>
                {fix['recommendation']}
            </div>
            ''' for fix in fixes) if fixes else '<p>No critical fixes needed at this time.</p>'}
        </div>
    </div>

    <script>
        const ctx = document.getElementById('timelineChart').getContext('2d');
        new Chart(ctx, {{
            type: 'line',
            data: {{
                labels: {timeline_labels},
                datasets: [{{
                    label: 'Failure Events',
                    data: {timeline_values},
                    borderColor: '#1976d2',
                    backgroundColor: 'rgba(25, 118, 210, 0.1)',
                    fill: true,
                    tension: 0.1
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                scales: {{
                    x: {{ title: {{ display: true, text: 'Cycle' }} }},
                    y: {{ beginAtZero: true, title: {{ display: true, text: 'Failure Count' }} }}
                }}
            }}
        }});
    </script>
</body>
</html>
"""
        return html_content

    def update_dashboard(self):
        html = self.generate_html()
        with open(self.output_file, 'w') as f:
            f.write(html)
        print(f"Dashboard updated: {self.output_file}")

if __name__ == '__main__':
    generator = DashboardGenerator()
    generator.update_dashboard()