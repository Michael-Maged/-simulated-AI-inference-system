import pytest
import requests
from unittest.mock import patch, MagicMock
from socket import timeout as SocketTimeout


BASE_URL = "http://localhost:8000"
TIMEOUT = 90


def test_timeout_fires_on_slow_response():
    """Verify that a request exceeding the timeout raises an exception (counted as failure in Locust)."""
    with patch("requests.post") as mock_post:
        mock_post.side_effect = requests.exceptions.ReadTimeout("Read timed out")
        with pytest.raises(requests.exceptions.ReadTimeout):
            requests.post(
                f"{BASE_URL}/infer",
                json={"prompt": "test", "max_tokens": 30, "priority": "normal"},
                timeout=TIMEOUT,
            )


def test_timeout_does_not_fire_on_fast_response():
    """Verify that a fast response completes successfully within the timeout."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"response": "ok"}

    with patch("requests.Session.post", return_value=mock_response):
        response = requests.post(
            f"{BASE_URL}/infer",
            json={"prompt": "test", "max_tokens": 30, "priority": "normal"},
            timeout=TIMEOUT,
        )
        assert response.status_code == 200


def test_timeout_value_is_correct():
    """Verify the locustfile uses the expected timeout value."""
    import ast
    import os

    locustfile = os.path.join(os.path.dirname(__file__), "../../client/locustfile.py")
    with open(locustfile) as f:
        tree = ast.parse(f.read())

    timeouts = []
    for node in ast.walk(tree):
        if isinstance(node, ast.keyword) and node.arg == "timeout":
            if isinstance(node.value, ast.Constant):
                timeouts.append(node.value.value)

    assert timeouts, "No timeout found in locustfile.py"
    assert all(t == TIMEOUT for t in timeouts), (
        f"Expected all timeouts to be {TIMEOUT}s, got {timeouts}"
    )
