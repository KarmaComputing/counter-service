# Counter Service

A simple HTTP service that maintains counters identified by unique URLs.

## Requirements

<!-- validate:requirements
- python: "3.12"
- docker: true
- pip: true
-->

- Docker
- Python 3.12+
- pip

## Setup

1. Create a Python virtual environment and activate it:
```bash
<!-- validate:step id="setup_venv" -->
python -m venv venv
source venv/bin/activate
```

2. Install Python dependencies:
```bash
<!-- validate:step id="install_deps" depends_on="setup_venv" -->
pip install -r requirements.txt
```

## Running the Service

The service uses Docker to run Redis with persistent storage. Use the provided script to start all services:

```bash
<!-- validate:step id="start_services" depends_on="install_deps" background=true validate_port="6379,5000" -->
./start-services.sh
```

This will:
1. Create a Docker volume for Redis data persistence
2. Start Redis in a Docker container
3. Start the Flask application

To stop all services and clean up, press Ctrl+C or run:
```bash
<!-- validate:cleanup -->
./start-services.sh cleanup
```

## Running Tests

The test suite includes integration tests with Redis. To run the tests:

```bash
<!-- validate:step id="run_tests" depends_on="install_deps" expected_output="test session starts" -->
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
<!-- validate:step id="test_increment" depends_on="start_services" expected_output="1" -->
curl http://localhost:5000/counter/my-counter
```

### Get Counter Value
To get the current value without incrementing:
```bash
<!-- validate:step id="test_value" depends_on="test_increment" expected_output="1" -->
curl http://localhost:5000/counter/my-counter/value
```

### Health Check
Check service health:
```bash
<!-- validate:step id="test_health" depends_on="start_services" expected_output="healthy" -->
curl http://localhost:5000/health
```

### Service Status
Get detailed service status:
```bash
<!-- validate:step id="test_status" depends_on="start_services" expected_output="redis_connected" -->
curl http://localhost:5000/status
```

### Real-Time Dashboard
View all counters and their values in real-time:
```bash
<!-- validate:step id="test_dashboard" depends_on="start_services" validate_url="http://localhost:5000/dashboard" expected_status="200" -->
http://localhost:5000/dashboard
```

The dashboard provides:
- Live counter values with updates every second
- Total number of counters and increments
- Updates per second monitoring
- Timestamp of last update for each counter
- Sound notifications for counter updates (toggle with 🔔/🔕 button)

Each counter_id creates a unique counter. You can use any string as your counter_id!

## Configuration

The service can be configured using environment variables:

<!-- validate:env_vars
- REDIS_HOST: localhost
- REDIS_PORT: 6379
-->

- `REDIS_HOST`: Redis server host (default: localhost)
- `REDIS_PORT`: Redis server port (default: 6379)

## Data Persistence

Counter data is persisted in a Docker volume named `redis-counter-data`. This ensures your counter values survive container restarts.
