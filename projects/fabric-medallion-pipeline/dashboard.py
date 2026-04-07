"""
Fabric Medallion Pipeline Dashboard — displays live pipeline execution results in a web UI.

Usage:
    python dashboard.py
    
Then visit http://localhost:8001/
"""
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from flask import Flask, render_template_string, jsonify
import threading

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

app = Flask(__name__)

# Global state
latest_result = None
pipeline_history = []


def run_pipeline_background():
    """Runs the medallion pipeline in sample mode and captures result."""
    global latest_result, pipeline_history
    
    try:
        # Run orchestrator
        cmd = [
            sys.executable,
            str(Path(__file__).parent / "src" / "pipeline-orchestrator" / "main.py"),
            "--mode", "sample"
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        
        # Extract JSON output (last lines)
        lines = result.stdout.strip().split('\n')
        json_start = None
        for i, line in enumerate(lines):
            if line.strip().startswith('{'):
                json_start = i
                break
        
        if json_start is not None:
            json_text = '\n'.join(lines[json_start:])
            latest_result = json.loads(json_text)
            latest_result['timestamp'] = datetime.utcnow().isoformat()
            pipeline_history.append(latest_result)
            if len(pipeline_history) > 10:
                pipeline_history.pop(0)
    except Exception as e:
        latest_result = {
            'status': 'error',
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }
        pipeline_history.append(latest_result)


@app.route('/')
def dashboard():
    """Main dashboard view."""
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Fabric Medallion Pipeline Dashboard</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body {
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                padding: 20px;
            }
            .container {
                max-width: 1200px;
                margin: 0 auto;
            }
            header {
                background: white;
                border-radius: 8px;
                padding: 30px;
                margin-bottom: 30px;
                box-shadow: 0 4px 20px rgba(0,0,0,0.1);
            }
            h1 {
                color: #333;
                font-size: 28px;
                margin-bottom: 10px;
            }
            .subtitle {
                color: #666;
                font-size: 14px;
            }
            .status-badge {
                display: inline-block;
                padding: 8px 16px;
                border-radius: 20px;
                font-weight: 600;
                font-size: 12px;
                margin-top: 12px;
            }
            .status-badge.success {
                background: #d4edda;
                color: #155724;
            }
            .status-badge.failed {
                background: #f8d7da;
                color: #721c24;
            }
            .status-badge.partial {
                background: #fff3cd;
                color: #856404;
            }
            .metrics {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 20px;
                margin-top: 20px;
            }
            .metric-card {
                background: #f5f7fa;
                padding: 20px;
                border-radius: 8px;
                border-left: 4px solid #667eea;
            }
            .metric-label {
                color: #666;
                font-size: 12px;
                font-weight: 600;
                text-transform: uppercase;
                margin-bottom: 8px;
            }
            .metric-value {
                color: #333;
                font-size: 24px;
                font-weight: 700;
            }
            .stages {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
                gap: 20px;
                margin-top: 20px;
            }
            .stage-card {
                background: white;
                border-radius: 8px;
                padding: 20px;
                box-shadow: 0 4px 20px rgba(0,0,0,0.1);
            }
            .stage-header {
                display: flex;
                align-items: center;
                margin-bottom: 16px;
                border-bottom: 2px solid #f0f0f0;
                padding-bottom: 16px;
            }
            .stage-icon {
                font-size: 28px;
                margin-right: 12px;
            }
            .stage-title {
                font-size: 18px;
                font-weight: 600;
                color: #333;
                flex: 1;
            }
            .stage-status {
                padding: 4px 12px;
                border-radius: 12px;
                font-size: 11px;
                font-weight: 600;
            }
            .stage-status.success {
                background: #d4edda;
                color: #155724;
            }
            .stage-status.failed {
                background: #f8d7da;
                color: #721c24;
            }
            .stage-detail {
                margin: 10px 0;
                font-size: 13px;
                color: #555;
            }
            .stage-detail-label {
                font-weight: 600;
                color: #333;
            }
            .run-button {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                border: none;
                padding: 12px 24px;
                border-radius: 6px;
                font-weight: 600;
                cursor: pointer;
                font-size: 14px;
                transition: transform 0.2s;
            }
            .run-button:hover {
                transform: translateY(-2px);
            }
            .run-button:disabled {
                opacity: 0.6;
                cursor: not-allowed;
            }
            .loading {
                display: inline-block;
                width: 16px;
                height: 16px;
                border: 2px solid rgba(255,255,255,0.3);
                border-top: 2px solid white;
                border-radius: 50%;
                animation: spin 0.8s linear infinite;
                margin-left: 8px;
            }
            @keyframes spin {
                to { transform: rotate(360deg); }
            }
            .timestamp {
                color: #999;
                font-size: 12px;
                margin-top: 16px;
                padding-top: 16px;
                border-top: 1px solid #eee;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <header>
                <h1>Fabric Medallion Pipeline Dashboard</h1>
                <p class="subtitle">Real-time execution monitoring & results</p>
                <button class="run-button" onclick="runPipeline()" id="runBtn">
                    ▶ Run Pipeline
                </button>
            </header>
            
            <div id="results">
                <p style="text-align: center; color: white; padding: 40px;">
                    Loading latest results...
                </p>
            </div>
        </div>
        
        <script>
            function runPipeline() {
                const btn = document.getElementById('runBtn');
                btn.disabled = true;
                btn.innerHTML = 'Running<span class="loading"></span>';
                
                fetch('/api/run-pipeline', { method: 'POST' })
                    .then(r => r.json())
                    .then(() => {
                        loadResults();
                        btn.disabled = false;
                        btn.innerHTML = '▶ Run Pipeline';
                    })
                    .catch(e => {
                        console.error(e);
                        btn.disabled = false;
                        btn.innerHTML = '▶ Run Pipeline';
                    });
            }
            
            function formatDuration(seconds) {
                if (seconds < 1) return (seconds * 1000).toFixed(0) + 'ms';
                return seconds.toFixed(3) + 's';
            }
            
            function loadResults() {
                fetch('/api/latest-result')
                    .then(r => r.json())
                    .then(data => {
                        if (!data.result) {
                            document.getElementById('results').innerHTML = 
                                '<p style="text-align: center; color: white; padding: 40px;">No pipeline runs yet</p>';
                            return;
                        }
                        
                        const result = data.result;
                        let html = `
                            <div style="background: white; border-radius: 8px; padding: 30px; margin-bottom: 20px; box-shadow: 0 4px 20px rgba(0,0,0,0.1);">
                                <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 20px;">
                                    <div>
                                        <h2 style="color: #333; margin-bottom: 8px;">Pipeline Execution</h2>
                                        <p style="color: #666; font-size: 14px;">Run ID: <code>${result.run_id || 'N/A'}</code></p>
                                    </div>
                                    <span class="status-badge ${result.status}">
                                        ${result.status.toUpperCase()}
                                    </span>
                                </div>
                                
                                <div class="metrics">
                                    <div class="metric-card">
                                        <div class="metric-label">Total Duration</div>
                                        <div class="metric-value">${formatDuration(result.total_duration_seconds)}</div>
                                    </div>
                                    <div class="metric-card">
                                        <div class="metric-label">Stages Complete</div>
                                        <div class="metric-value">${Object.keys(result.stages).filter(s => result.stages[s].status === 'success').length}/${Object.keys(result.stages).length}</div>
                                    </div>
                                </div>
                            </div>
                            
                            <div class="stages">
        `;
                        
                        // Stage icons
                        const icons = { bronze: '🥉', silver: '🥈', gold: '🥇' };
                        
                        for (const [stageName, stage] of Object.entries(result.stages)) {
                            const icon = icons[stageName] || '⚙️';
                            html += `
                                <div class="stage-card">
                                    <div class="stage-header">
                                        <span class="stage-icon">${icon}</span>
                                        <span class="stage-title">${stageName.charAt(0).toUpperCase() + stageName.slice(1)}</span>
                                        <span class="stage-status ${stage.status}">${stage.status}</span>
                                    </div>
            `;
                            
                            if (stage.status === 'success') {
                                if (stage.records) {
                                    html += `<div class="stage-detail"><span class="stage-detail-label">Records:</span> ${stage.records}</div>`;
                                }
                                if (stage.records_in !== undefined) {
                                    html += `<div class="stage-detail"><span class="stage-detail-label">Input:</span> ${stage.records_in}</div>`;
                                    html += `<div class="stage-detail"><span class="stage-detail-label">Output:</span> ${stage.records_out}</div>`;
                                    if (stage.failed) {
                                        html += `<div class="stage-detail"><span class="stage-detail-label">Failed:</span> ${stage.failed}</div>`;
                                    }
                                }
                                if (stage.customer_metrics !== undefined) {
                                    html += `<div class="stage-detail"><span class="stage-detail-label">Customer Metrics:</span> ${stage.customer_metrics}</div>`;
                                }
                                if (stage.event_type_metrics !== undefined) {
                                    html += `<div class="stage-detail"><span class="stage-detail-label">Event Type Metrics:</span> ${stage.event_type_metrics}</div>`;
                                }
                            } else if (stage.error) {
                                html += `<div class="stage-detail" style="color: #c00;"><span class="stage-detail-label">Error:</span> ${stage.error}</div>`;
                            }
                            
                            html += `<div class="stage-detail"><span class="stage-detail-label">Duration:</span> ${formatDuration(stage.duration_seconds)}</div>`;
                            html += `</div>`;
                        }
                        
                        html += `</div>`;
                        html += `<div class="timestamp">Last updated: ${new Date(result.timestamp).toLocaleString()}</div>`;
                        
                        document.getElementById('results').innerHTML = html;
                    })
                    .catch(e => console.error(e));
            }
            
            // Load on page load and every 3 seconds
            loadResults();
            setInterval(loadResults, 3000);
        </script>
    </body>
    </html>
    """
    return render_template_string(html)


@app.route('/api/latest-result')
def get_latest_result():
    """Returns latest pipeline result as JSON."""
    return jsonify({'result': latest_result})


@app.route('/api/run-pipeline', methods=['POST'])
def run_pipeline_api():
    """Trigger a new pipeline run in background."""
    thread = threading.Thread(target=run_pipeline_background, daemon=True)
    thread.start()
    return jsonify({'status': 'running'})


if __name__ == '__main__':
    # Load initial result
    run_pipeline_background()
    
    print("=" * 60)
    print("Fabric Medallion Pipeline Dashboard")
    print("=" * 60)
    print("Starting server on http://localhost:8001/")
    print("Press Ctrl+C to stop")
    print("=" * 60)
    
    app.run(host='127.0.0.1', port=8001, debug=False)
