from flask import Flask, jsonify, g, render_template, Response
import redis
import os
import json
from datetime import datetime, timezone
import time

app = Flask(__name__)

def get_redis_client():
    """Get Redis client based on app configuration or environment variables."""
    if not hasattr(g, 'redis_client'):
        port = app.config.get('REDIS_PORT') or int(os.getenv('REDIS_PORT', 6379))
        g.redis_client = redis.Redis(
            host=os.getenv('REDIS_HOST', 'localhost'),
            port=port,
            decode_responses=True
        )
    return g.redis_client

@app.teardown_appcontext
def close_redis(error):
    """Close Redis connection when the app context ends."""
    if hasattr(g, 'redis_client'):
        g.redis_client.close()

@app.route('/counter/<path:counter_id>', methods=['GET'])
def increment_counter(counter_id):
    """
    Increment counter for the given counter_id and return the new value
    """
    try:
        redis_client = get_redis_client()
        new_count = redis_client.incr(f"counter:{counter_id}")
        return jsonify({
            "counter_id": counter_id,
            "count": new_count
        })
    except redis.RedisError as e:
        return jsonify({"error": "Counter service temporarily unavailable"}), 503

@app.route('/counter/<path:counter_id>/value', methods=['GET'])
def get_counter(counter_id):
    """
    Get the current value of the counter without incrementing
    """
    try:
        redis_client = get_redis_client()
        count = redis_client.get(f"counter:{counter_id}") or 0
        return jsonify({
            "counter_id": counter_id,
            "count": int(count)
        })
    except redis.RedisError as e:
        return jsonify({"error": "Counter service temporarily unavailable"}), 503

@app.route('/health', methods=['GET'])
def health_check():
    """
    Health check endpoint that verifies the service and its dependencies are functioning
    """
    try:
        redis_client = get_redis_client()
        redis_client.ping()
        return jsonify({
            "status": "healthy",
            "service": "counter-service",
            "checks": {
                "redis": "ok"
            }
        })
    except redis.RedisError as e:
        return jsonify({
            "status": "unhealthy",
            "service": "counter-service",
            "checks": {
                "redis": "failed"
            },
            "error": str(e)
        }), 503

@app.route('/status', methods=['GET'])
def status_check():
    """
    Detailed status endpoint that includes Redis connection status and basic metrics
    """
    try:
        redis_client = get_redis_client()
        redis_client.ping()
        redis_status = "connected"
        
        # Get some basic metrics
        total_counters = len(redis_client.keys("counter:*"))
        
        return jsonify({
            "status": "healthy",
            "components": {
                "redis": {
                    "status": redis_status,
                    "host": redis_client.connection_pool.connection_kwargs['host'],
                    "port": redis_client.connection_pool.connection_kwargs['port']
                },
                "application": {
                    "status": "running",
                    "total_counters": total_counters
                }
            },
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
    except redis.RedisError as e:
        return jsonify({
            "status": "degraded",
            "components": {
                "redis": {
                    "status": "disconnected",
                    "error": str(e)
                },
                "application": {
                    "status": "running"
                }
            },
            "timestamp": datetime.now(timezone.utc).isoformat()
        }), 503

@app.route('/dashboard')
def dashboard():
    """
    Render the real-time dashboard page
    """
    return render_template('dashboard.html')

@app.route('/dashboard/stream')
def dashboard_stream():
    """Stream counter updates."""
    def generate():
        with app.app_context():
            while True:
                redis_client = get_redis_client()
                
                # Get all counter keys
                counter_keys = redis_client.keys('counter:*')
                counters = {}
                total_increments = 0
                
                # Get values for each counter
                for key in counter_keys:
                    # Handle both string and bytes keys
                    key_str = key if isinstance(key, str) else key.decode()
                    value = int(redis_client.get(key) or 0)
                    counters[key_str] = value
                    total_increments += value
                
                # Create event data
                data = {
                    'counters': counters,
                    'total_counters': len(counter_keys),
                    'total_increments': total_increments,
                    'timestamp': datetime.now(timezone.utc).isoformat(),
                    'updates_per_second': len(counter_keys)  # This is a placeholder, could be calculated from actual updates
                }
                
                yield f"data: {json.dumps(data)}\n\n"
                time.sleep(1)  # Update every second
    
    return Response(generate(), mimetype='text/event-stream')


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
