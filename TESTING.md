## Testing

### Main principle

Write tests that verify user-visible behavior and service contracts, not incidental implementation details.

Prefer realistic integration tests when they are practical. Use mocks only at system boundaries: external APIs, third-party services, and nondeterministic or external network dependencies.

### Running tests

In order to run tests, you need to have the test infrastructure running:

```bash
docker compose -f docker-compose.test.yaml up --wait
```

Note that the test infrastructure will be stopped after 1 hour of inactivity.

Run tests:

```bash
uv run -m pytest
```

Useful variants:

```bash
uv run -m pytest --lf
uv run -m pytest -k "some expression"
uv run -m pytest tests/path/to/test_file.py
uv run -m pytest tests/path/to/test_file.py::test_name
uv run -m pytest -n auto --dist=loadscope
uv run -m pytest --cov=src --cov-report=term-missing
```

### Test design

Good tests should be:

* independent from test order
* explicit about expected behavior
* small enough to identify the broken feature
* realistic enough to catch integration bugs
* stable under parallel execution

Avoid tests that depend on hidden global state, production services, arbitrary sleeps, or exact ordering unless ordering is part of the API contract.

### Infrastructure

Use shared test infrastructure and existing fixtures. Do not start databases, object stores, or service containers inside individual tests.

Tests should run against test settings only. Never hardcode production credentials, URLs, buckets, databases, or tokens.

When parallel test execution is enabled, assume multiple workers may run tests at the same time. Use isolated names, unique test data, or existing cleanup fixtures.

### Mocking

Mock external systems, not the code under test.

Acceptable mock targets include:

* external HTTP APIs
* authentication providers
* third-party services
* time-sensitive or nondeterministic boundaries

Avoid mocking internal repositories, services, or business logic when the behavior can be tested through the public API.

You could use `respx` for mocking external HTTP APIs, you can search for examples in the repository.

### Assertions

Assert outcomes, not implementation steps.

Prefer:

```python
assert response.status_code == 404
assert response.json()["detail"] == "Club not found"
```

Over:

```python
assert some_internal_function_was_called
```

For successful responses, assert the fields that define correctness. Avoid asserting entire payloads when only a few fields matter.

### Test data

Use clear, minimal test data.

When creating persistent records, files, buckets, objects, slugs, or IDs, make them unique unless the test specifically verifies conflicts.

Do not rely on data created by another test.

### External network

Tests must not call real external services. All external network interactions should be mocked, stubbed, or routed through controlled test infrastructure.

### Debugging

For visible output:

```bash
uv run -m pytest -s
```

For verbose output:

```bash
uv run -m pytest -vv
```

For one failing test:

```bash
uv run -m pytest tests/path/to/test_file.py::test_name -vv -s
```

### Coverage

Coverage is useful for finding untested areas, but it is not the goal by itself.

Prefer meaningful tests for important behavior over shallow tests written only to increase coverage numbers.


### Commit messages

Use `test(service, ...): description` or `test: description` format for commit messages when adding or updating only tests or test infrastructure.
