# Counter Service

A simple HTTP service that maintains counters identified by unique URLs.

## Requirements

- Docker
- Python 3.12+
- pip

## Setup

1. Create a Python virtual environment and activate it:
```bash
python -m venv venv
source venv/bin/activate
```

2. Install Python dependencies:
```bash
pip install -r requirements.txt
```

## Running the Service

The service uses Docker to run Redis with persistent storage. Use the provided script to start all services:

```bash
./start-services.sh
```

This will:
1. Create a Docker volume for Redis data persistence
2. Start Redis in a Docker container
3. Start the Flask application

To stop all services and clean up, press Ctrl+C or run:
```bash
./start-services.sh cleanup
```

## Running Tests

The test suite includes integration tests with Redis. To run the tests:

```bash
pytest -v tests/
```

The tests will:
- Start a separate Redis container for testing
- Run all test cases including:
  - Basic counter operations
  - Concurrent increment testing
  - Health and status endpoint verification
- Automatically clean up the test container

## Usage

### Increment Counter
Send a GET request to `/counter/<counter_id>` to increment the counter:
```bash
curl http://localhost:5000/counter/my-counter
```

### Get Counter Value
To get the current value without incrementing:
```bash
curl http://localhost:5000/counter/my-counter/value
```

### Health Check
Check service health:
```bash
curl http://localhost:5000/health
```

### Service Status
Get detailed service status:
```bash
curl http://localhost:5000/status
```

### Real-Time Dashboard
View all counters and their values in real-time:
```bash
http://localhost:5000/dashboard
```

The dashboard provides:
- Live counter values with updates every second
- Total number of counters and increments
- Updates per second monitoring
- Timestamp of last update for each counter

Each counter_id creates a unique counter. You can use any string as your counter_id!

## Configuration

The service can be configured using environment variables:

- `REDIS_HOST`: Redis server host (default: localhost)
- `REDIS_PORT`: Redis server port (default: 6379)

## Data Persistence

Counter data is persisted in a Docker volume named `redis-counter-data`. This ensures your counter values survive container restarts.
