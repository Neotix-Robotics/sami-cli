# SAMI Datasets SDK Test Suite

This directory contains unit and integration tests for the SAMI Datasets SDK.

## Test Categories

- **Unit Tests** (`@pytest.mark.unit`): Tests that don't require external services
- **Integration Tests** (`@pytest.mark.integration`): Tests that require a running backend

## Running Tests

### Install Test Dependencies

```bash
cd sami-datasets
pip install -e ".[dev]"
```

### Run All Tests

```bash
pytest tests/
```

### Run Only Unit Tests

```bash
pytest tests/ -m unit
```

### Run Only Integration Tests

Requires a running backend at `http://localhost:5001`:

```bash
pytest tests/ -m integration
```

### Run with Coverage

```bash
pytest tests/ --cov=sami_datasets --cov-report=html
```

## Test Configuration

Tests can be configured using environment variables:

| Variable             | Default                        | Description                   |
| -------------------- | ------------------------------ | ----------------------------- |
| `SAMI_TEST_API_URL`  | `http://localhost:5001/api/v1` | API URL for integration tests |
| `SAMI_TEST_EMAIL`    | `admin@dextera.company`        | Test user email               |
| `SAMI_TEST_PASSWORD` | `Admin123!`                    | Test user password            |

Example:

```bash
SAMI_TEST_API_URL=https://staging.sami.example.com/api/v1 \
SAMI_TEST_EMAIL=test@example.com \
SAMI_TEST_PASSWORD=secret \
pytest tests/ -m integration
```

## Test Structure

```
tests/
├── conftest.py           # Pytest fixtures and configuration
├── test_auth.py          # Authentication tests
├── test_client.py        # SamiClient integration tests
├── test_exceptions.py    # Exception hierarchy tests
├── test_models.py        # Data model tests
└── test_validation.py    # Dataset validation tests
```

## Writing New Tests

1. Add appropriate markers (`@pytest.mark.unit` or `@pytest.mark.integration`)
2. Use fixtures from `conftest.py` where possible
3. Integration tests should clean up any resources they create
4. Unit tests should mock external dependencies

Example unit test:

```python
@pytest.mark.unit
def test_example(temp_dataset_dir):
    """Test description."""
    # temp_dataset_dir is a fixture that provides a valid dataset structure
    result = some_function(temp_dataset_dir)
    assert result is not None
```

Example integration test:

```python
@pytest.mark.integration
def test_upload_download(authenticated_client, temp_dataset_dir):
    """Test upload and download cycle."""
    dataset = authenticated_client.upload_dataset(
        name="Test",
        path=str(temp_dataset_dir)
    )
    try:
        # Test assertions
        assert dataset.id is not None
    finally:
        # Cleanup
        authenticated_client.delete_dataset(dataset.id)
```
