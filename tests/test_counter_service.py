import pytest
import threading
import docker
import time
import os
import sys
import json
from pathlib import Path

# Add the project root directory to Python path
sys.path.append(str(Path(__file__).parent.parent))

from app import app, get_redis_client

# Test configuration
TEST_REDIS_PORT = 6380
REDIS_CONTAINER_NAME = 'redis-counter-test'

@pytest.fixture(scope='session')
def redis_container():
    """Start a Redis container for testing."""
    client = docker.from_env()
    
    # Remove existing container if it exists
    try:
        container = client.containers.get(REDIS_CONTAINER_NAME)
        container.remove(force=True)
    except docker.errors.NotFound:
        pass
    
    # Start new container
    container = client.containers.run(
        'redis:5.0.0',
        name=REDIS_CONTAINER_NAME,
        ports={'6379/tcp': TEST_REDIS_PORT},
        detach=True
    )
    
    # Wait for Redis to be ready
    time.sleep(2)
    
    yield container
    
    # Cleanup
    container.remove(force=True)
    print(REDIS_CONTAINER_NAME)

@pytest.fixture
def client(redis_container):
    """Create a test client for the app."""
    # Configure app to use test Redis
    app.config['TESTING'] = True
    app.config['REDIS_PORT'] = TEST_REDIS_PORT
    
    with app.test_client() as test_client:
        with app.app_context():
            yield test_client

@pytest.fixture
def redis_client(client):
    """Get Redis client configured for testing."""
    with app.app_context():
        return get_redis_client()

@pytest.fixture(autouse=True)
def clean_redis(redis_client):
    """Clean all counters from Redis before each test."""
    # Delete all counters before test
    for key in redis_client.keys('counter:*'):
        redis_client.delete(key)
    yield
    # Delete all counters after test
    for key in redis_client.keys('counter:*'):
        redis_client.delete(key)

def test_increment_counter(client, redis_client):
    """Test that counter increments correctly."""
    # Clear any existing counter
    redis_client.delete('counter:test-counter')
    
    # First request should return 1
    response = client.get('/counter/test-counter')
    assert response.status_code == 200
    assert response.json['count'] == 1
    
    # Second request should return 2
    response = client.get('/counter/test-counter')
    assert response.status_code == 200
    assert response.json['count'] == 2

def test_get_counter_value(client, redis_client):
    """Test getting counter value without incrementing."""
    # Set initial counter value
    redis_client.set('counter:test-counter-2', 42)
    
    # Check value endpoint
    response = client.get('/counter/test-counter-2/value')
    assert response.status_code == 200
    assert response.json['count'] == 42

def test_health_check_healthy(client):
    """Test health check endpoint when Redis is available."""
    response = client.get('/health')
    assert response.status_code == 200
    assert response.json['status'] == 'healthy'
    assert response.json['checks']['redis'] == 'ok'

def test_status_check(client, redis_client):
    """Test status check endpoint."""
    response = client.get('/status')
    assert response.status_code == 200
    assert response.json['status'] == 'healthy'
    assert response.json['components']['redis']['status'] == 'connected'
    assert response.json['components']['redis']['port'] == TEST_REDIS_PORT

def test_concurrent_increments(client, redis_client):
    """Test that concurrent counter increments work correctly."""
    counter_id = 'concurrent-test'
    redis_client.delete(f'counter:{counter_id}')
    
    num_requests = 50
    
    def make_request():
        with app.test_client() as test_client:
            test_client.get(f'/counter/{counter_id}')
    
    # Create threads for concurrent requests
    threads = [threading.Thread(target=make_request) for _ in range(num_requests)]
    
    # Start all threads
    for thread in threads:
        thread.start()
    
    # Wait for all threads to complete
    for thread in threads:
        thread.join()
    
    # Check final counter value
    response = client.get(f'/counter/{counter_id}/value')
    assert response.status_code == 200
    assert response.json['count'] == num_requests

def test_different_counters_independence(client, redis_client):
    """Test that different counters are independent."""
    # Clear existing counters
    redis_client.delete('counter:counter1')
    redis_client.delete('counter:counter2')
    
    # Increment counter1 twice
    client.get('/counter/counter1')
    client.get('/counter/counter1')
    
    # Increment counter2 once
    client.get('/counter/counter2')
    
    # Check values
    response1 = client.get('/counter/counter1/value')
    response2 = client.get('/counter/counter2/value')
    
    assert response1.json['count'] == 2
    assert response2.json['count'] == 1

def test_dashboard_page(client):
    """Test that dashboard page loads."""
    response = client.get('/dashboard')
    assert response.status_code == 200
    assert b'Counter Service Dashboard' in response.data

def test_dashboard_stream(client, redis_client):
    """Test dashboard SSE stream."""
    # Set up some test data
    redis_client.set('counter:test1', 5)
    redis_client.set('counter:test2', 10)
    
    # Get stream response
    response = client.get('/dashboard/stream')
    assert response.status_code == 200
    assert response.mimetype == 'text/event-stream'
    
    # Get first chunk of data (one event)
    data = next(response.iter_encoded())
    assert data.startswith(b'data: ')
    
    # Parse JSON data
    json_data = json.loads(data.decode().replace('data: ', '').strip())
    
    # Verify structure and content
    assert 'counters' in json_data
    assert 'total_counters' in json_data
    assert 'total_increments' in json_data
    assert json_data['total_counters'] == 2
    assert json_data['total_increments'] == 15
    assert json_data['counters']['counter:test1'] == 5
    assert json_data['counters']['counter:test2'] == 10

if __name__ == '__main__':
    pytest.main(['-v'])
