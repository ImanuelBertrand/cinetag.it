# CineTagIt Tests

This directory contains tests for the CineTagIt application.

## Running Tests

### Using Docker (Recommended)

The easiest way to run the tests is using the Docker environment, which provides all the necessary dependencies (database, Redis, etc.).

```bash
# From the repository root
./devenv/docker-run-tests.sh
```

This script will:
1. Rebuild the Docker image to ensure all dependencies are installed
2. Start the Docker environment
3. Initialize the main application database
4. Initialize the test database
5. Run the tests inside the Docker container
6. Return the test exit code

### Running Specific Tests

To run specific tests, you can modify the docker-run-tests.sh script or run the following command:

```bash
# Start the Docker environment first
./devenv/docker-start.sh

# Run specific tests
docker-compose -p cinetagit exec app python -m pytest -v -s tests/services/test_user_service.py

# Stop the Docker environment when done
./devenv/docker-stop.sh
```

## Test Structure

- `conftest.py`: Contains pytest fixtures used by the tests
- `services/`: Tests for service layer components

## Adding New Tests

When adding new tests:
1. Follow the existing pattern of using fixtures from conftest.py
2. Use descriptive test names that explain what is being tested
3. Add appropriate assertions to verify the expected behavior
