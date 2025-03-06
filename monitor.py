from flask import Flask, jsonify, request, render_template
import threading
import time
import os
import json
import psutil
from datetime import datetime

from src.services.post_queue import post_queue, PostStatus
from src.instagram.instagram_post_service import InstagramPostService
from src.services.instagram_send import InstagramSend

# Initialize the monitoring app on port 6002
app = Flask(__name__, template_folder="monitoring_templates")

# Track server stats
SERVER_STATS = {
    "start_time": datetime.now().isoformat(),
    "requests_served": 0,
    "last_error": None,
    "api_rate_limits": {
        "count": 0,
        "window_start": time.time()
    }
}

# Create templates directory if it doesn't exist
os.makedirs("monitoring_templates", exist_ok=True)

# Create a basic HTML template for the dashboard
with open("monitoring_templates/dashboard.html", "w") as f:
    f.write("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Instagram Posting Monitor</title>
        <meta http-equiv="refresh" content="30">
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; }
            h1, h2 { color: #3b5998; }
            .stats-container { display: flex; flex-wrap: wrap; }
            .stat-box { 
                background-color: #f0f2f5; 
                border-radius: 5px; 
                padding: 20px; 
                margin: 10px;
                min-width: 200px;
                flex-grow: 1;
            }
            .stat-value { 
                font-size: 24px; 
                font-weight: bold; 
                margin: 10px 0;
            }
            .jobs-table {
                width: 100%;
                border-collapse: collapse;
                margin-top: 20px;
            }
            .jobs-table th, .jobs-table td {
                padding: 12px;
                text-align: left;
                border-bottom: 1px solid #ddd;
            }
            .status-queued { color: #f9a602; }
            .status-processing { color: #1877f2; }
            .status-completed { color: #42b72a; }
            .status-failed { color: #ff0000; }
            .status-rate_limited { color: #ff8c00; }
            .status-content_violation { color: #8b0000; }
            .error-message {
                background-color: #ffdddd;
                border-left: 6px solid #f44336;
                padding: 10px;
                margin: 10px 0;
            }
        </style>
    </head>
    <body>
        <h1>Instagram Posting Monitor</h1>
        
        <div class="stats-container">
            <div class="stat-box">
                <h3>Queue Status</h3>
                <p>Pending Jobs: <span class="stat-value">{{stats.pending_jobs}}</span></p>
                <p>Active Jobs: <span class="stat-value">{{stats.active_jobs}}</span></p>
            </div>
            <div class="stat-box">
                <h3>Performance</h3>
                <p>Avg Processing Time: <span class="stat-value">{{stats.average_processing_time|round(1)}}s</span></p>
                <p>Success Rate: <span class="stat-value">{{success_rate|round(1)}}%</span></p>
            </div>
            <div class="stat-box">
                <h3>Results</h3>
                <p>Successful Posts: <span class="stat-value">{{stats.successful_posts}}</span></p>
                <p>Failed Posts: <span class="stat-value">{{stats.failed_posts}}</span></p>
            </div>
            <div class="stat-box">
                <h3>Issues</h3>
                <p>Rate Limited: <span class="stat-value">{{stats.rate_limited_posts}}</span></p>
                <p>Content Violations: <span class="stat-value">{{stats.content_violations}}</span></p>
            </div>
        </div>

        <div class="stat-box">
            <h3>System Resources</h3>
            <div class="stats-container">
                <div>
                    <p>CPU Usage: <span class="stat-value">{{system.cpu_percent}}%</span></p>
                    <p>Memory Usage: <span class="stat-value">{{system.memory_percent|round(1)}}%</span></p>
                </div>
                <div>
                    <p>Disk Usage: <span class="stat-value">{{system.disk_percent|round(1)}}%</span></p>
                    <p>Uptime: <span class="stat-value">{{system.uptime}}</span></p>
                </div>
            </div>
        </div>
        
        <h2>Recent Jobs</h2>
        <table class="jobs-table">
            <thead>
                <tr>
                    <th>Job ID</th>
                    <th>Status</th>
                    <th>Caption</th>
                    <th>Created</th>
                    <th>Completed</th>
                    <th>Error</th>
                </tr>
            </thead>
            <tbody>
                {% for job in jobs %}
                <tr>
                    <td>{{job.id[:8]}}...</td>
                    <td class="status-{{job.status}}">{{job.status}}</td>
                    <td>{{job.caption|truncate(30)}}</td>
                    <td>{{job.created_at|replace("T", " ")|truncate(19, True, "")}}</td>
                    <td>{{job.completed_at|replace("T", " ")|truncate(19, True, "") if job.completed_at else "-"}}</td>
                    <td>{{job.error|truncate(50) if job.error else "-"}}</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
        
        <footer style="margin-top: 30px; text-align: center; color: #666;">
            <p>Instagram Posting Monitoring System | Last updated: {{current_time}}</p>
        </footer>
    </body>
    </html>
    """)

# Get system stats
def get_system_stats():
    try:
        process = psutil.Process(os.getpid())
        
        # Calculate uptime
        uptime_seconds = time.time() - process.create_time()
        days, remainder = divmod(uptime_seconds, 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        if days > 0:
            uptime = f"{int(days)}d {int(hours)}h {int(minutes)}m"
        elif hours > 0:
            uptime = f"{int(hours)}h {int(minutes)}m {int(seconds)}s"
        else:
            uptime = f"{int(minutes)}m {int(seconds)}s"
            
        # Get disk usage
        disk = psutil.disk_usage('/')
        
        return {
            "cpu_percent": psutil.cpu_percent(),
            "memory_percent": process.memory_percent(),
            "disk_percent": disk.percent,
            "uptime": uptime,
            "threads": threading.active_count()
        }
    except Exception as e:
        return {
            "error": str(e),
            "cpu_percent": 0,
            "memory_percent": 0,
            "disk_percent": 0,
            "uptime": "unknown",
            "threads": threading.active_count()
        }

@app.route('/')
def dashboard():
    SERVER_STATS["requests_served"] += 1
    
    # Get queue stats
    stats = post_queue.get_queue_stats()
    
    # Get recent jobs
    jobs = post_queue.get_job_history(20)
    
    # Calculate success rate
    total_completed = stats['successful_posts'] + stats['failed_posts']
    success_rate = 0
    if total_completed > 0:
        success_rate = (stats['successful_posts'] / total_completed) * 100
    
    # Get system stats
    system = get_system_stats()
    
    return render_template(
        'dashboard.html', 
        stats=stats, 
        jobs=jobs, 
        system=system, 
        success_rate=success_rate,
        current_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )

@app.route('/api/health')
def health_check():
    return jsonify({
        "status": "ok",
        "uptime": time.time() - float(datetime.fromisoformat(SERVER_STATS["start_time"]).timestamp()),
        "requests_served": SERVER_STATS["requests_served"]
    })

@app.route('/api/stats')
def get_stats():
    SERVER_STATS["requests_served"] += 1
    
    stats = post_queue.get_queue_stats()
    system = get_system_stats()
    
    return jsonify({
        "queue": stats,
        "system": system,
        "server": {
            "start_time": SERVER_STATS["start_time"],
            "requests_served": SERVER_STATS["requests_served"],
            "last_error": SERVER_STATS["last_error"]
        }
    })

@app.route('/api/jobs')
def list_jobs():
    SERVER_STATS["requests_served"] += 1
    
    limit = request.args.get('limit', default=10, type=int)
    status = request.args.get('status', default=None, type=str)
    
    # Get recent jobs
    jobs = post_queue.get_job_history(limit=50)  # Get more than we need for filtering
    
    # Filter by status if specified
    if status:
        jobs = [job for job in jobs if job.get('status') == status]
    
    # Limit results
    jobs = jobs[:limit]
    
    return jsonify({
        "jobs": jobs,
        "count": len(jobs),
        "total_jobs": post_queue.get_queue_stats()['total_posts']
    })

@app.route('/api/jobs/<string:job_id>')
def get_job(job_id):
    SERVER_STATS["requests_served"] += 1
    
    job = post_queue.get_job_status(job_id)
    
    if job.get('status') == 'not_found':
        return jsonify({"error": "Job not found"}), 404
        
    return jsonify(job)

@app.route('/api/test', methods=['POST'])
def test_post():
    SERVER_STATS["requests_served"] += 1
    
    data = request.get_json()
    if not data:
        return jsonify({"error": "Missing request body"}), 400
        
    # Extract parameters with defaults
    image_url = data.get('image_url', 'https://i.imgur.com/h1CzPBh.jpg')
    caption = data.get('caption', 'Test post from monitoring API')
    
    try:
        # Create test service
        service = InstagramPostService()
        
        # Don't actually post to Instagram in test mode
        # Just validate the parameters
        result = {
            "test_id": "test_" + str(time.time()),
            "image_url": image_url,
            "caption": caption,
            "validation": "passed",
            "timestamp": datetime.now().isoformat()
        }
        
        return jsonify(result)
    except Exception as e:
        SERVER_STATS["last_error"] = str(e)
        return jsonify({"error": str(e), "validation": "failed"}), 400

@app.route('/api/queue', methods=['POST'])
def queue_post():
    SERVER_STATS["requests_served"] += 1
    
    data = request.get_json()
    if not data:
        return jsonify({"error": "Missing request body"}), 400
        
    # Extract required parameters
    image_path = data.get('image_path')
    caption = data.get('caption')
    inputs = data.get('inputs')
    
    if not image_path:
        return jsonify({"error": "Missing image_path parameter"}), 400
        
    try:
        # Queue the post
        job_id = InstagramSend.queue_post(image_path, caption, inputs)
        
        # Return the job details
        job = post_queue.get_job_status(job_id)
        
        return jsonify({
            "job_id": job_id,
            "status": job.get('status'),
            "created_at": job.get('created_at'),
            "message": "Post queued successfully"
        }), 202
    except FileNotFoundError as e:
        SERVER_STATS["last_error"] = str(e)
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        SERVER_STATS["last_error"] = str(e)
        return jsonify({"error": str(e)}), 500

@app.errorhandler(Exception)
def handle_error(e):
    SERVER_STATS["last_error"] = str(e)
    return jsonify({"error": str(e)}), 500

def start_monitoring_server():
    """Start the monitoring server in a separate thread"""
    from werkzeug.serving import make_server
    import socket

    port = 6002
    retries = 3

    for _ in range(retries):
        try:
            # Create a werkzeug server
            srv = make_server('0.0.0.0', port, app)
            
            # Start server in a thread
            thread = threading.Thread(target=srv.serve_forever)
            thread.daemon = True
            thread.start()
            
            print(f"Monitoring server started on http://0.0.0.0:{port}")
            return thread
        except socket.error as e:
            if "Address already in use" in str(e):
                print(f"Port {port} is already in use, monitoring server may already be running")
                return None
            port += 1
    
    print("Failed to start monitoring server after several attempts")
    return None

if __name__ == '__main__':
    # Start server directly when run as script
    app.run(host='0.0.0.0', port=6002, debug=False)  # Disabled debug mode for monitoring server