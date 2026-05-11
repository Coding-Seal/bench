from unittest.mock import MagicMock, patch

import pytest
import requests

from src.metrics_client import _get, _range_avg


def _range_response(values: list) -> dict:
    return {
        "status": "success",
        "data": {"result": [{"values": [[i, str(v)] for i, v in enumerate(values)]}]},
    }


# ── _range_avg ────────────────────────────────────────────────────────────────


def test_range_avg_basic():
    assert _range_avg(_range_response([10.0, 20.0, 30.0])) == pytest.approx(20.0)


def test_range_avg_single_value():
    assert _range_avg(_range_response([42.0])) == pytest.approx(42.0)


def test_range_avg_drops_inf():
    # inf dropped; average of 10 and 30
    assert _range_avg(_range_response([10.0, float("inf"), 30.0])) == pytest.approx(20.0)


def test_range_avg_drops_nan():
    assert _range_avg(_range_response([float("nan"), 50.0])) == pytest.approx(50.0)


def test_range_avg_empty_result_raises():
    data = {"status": "success", "data": {"result": []}}
    with pytest.raises(RuntimeError, match="no data"):
        _range_avg(data)


def test_range_avg_all_non_finite_raises():
    with pytest.raises(RuntimeError, match="non-finite"):
        _range_avg(_range_response([float("nan"), float("inf")]))


def test_range_avg_error_status_raises():
    data = {"status": "error", "data": {"result": []}}
    with pytest.raises(RuntimeError):
        _range_avg(data)


# ── _get: retry logic ─────────────────────────────────────────────────────────


def _ok_response(payload: dict) -> MagicMock:
    resp = MagicMock()
    resp.json.return_value = payload
    resp.raise_for_status.return_value = None
    return resp


def test_get_returns_on_first_success():
    mock_session = MagicMock()
    mock_session.get.return_value = _ok_response({"status": "ok"})
    with patch("src.metrics_client._session", mock_session):
        result = _get("http://prometheus/api", {}, retries=3, delay=0)
    assert result == {"status": "ok"}
    assert mock_session.get.call_count == 1


def test_get_retries_on_connection_error():
    mock_session = MagicMock()
    mock_session.get.side_effect = [
        requests.ConnectionError("refused"),
        _ok_response({"data": "ok"}),
    ]
    with patch("src.metrics_client._session", mock_session):
        result = _get("http://prometheus/api", {}, retries=3, delay=0)
    assert result == {"data": "ok"}
    assert mock_session.get.call_count == 2


def test_get_retries_on_timeout():
    mock_session = MagicMock()
    mock_session.get.side_effect = [
        requests.Timeout("timed out"),
        requests.Timeout("timed out"),
        _ok_response({"recovered": True}),
    ]
    with patch("src.metrics_client._session", mock_session):
        result = _get("http://prometheus/api", {}, retries=3, delay=0)
    assert result["recovered"] is True
    assert mock_session.get.call_count == 3


def test_get_raises_after_all_retries_exhausted():
    mock_session = MagicMock()
    mock_session.get.side_effect = requests.ConnectionError("refused")
    with patch("src.metrics_client._session", mock_session):
        with pytest.raises(requests.ConnectionError):
            _get("http://prometheus/api", {}, retries=3, delay=0)
    assert mock_session.get.call_count == 3


def test_get_retries_on_500_error():
    error_resp = MagicMock()
    error_resp.status_code = 500
    http_error = requests.HTTPError(response=error_resp)
    error_resp.raise_for_status.side_effect = http_error

    mock_session = MagicMock()
    mock_session.get.side_effect = [error_resp, _ok_response({"ok": True})]

    with patch("src.metrics_client._session", mock_session):
        result = _get("http://prometheus/api", {}, retries=3, delay=0)
    assert result == {"ok": True}


def test_get_does_not_retry_on_404():
    error_resp = MagicMock()
    error_resp.status_code = 404
    http_error = requests.HTTPError(response=error_resp)
    error_resp.raise_for_status.side_effect = http_error

    mock_session = MagicMock()
    mock_session.get.return_value = error_resp

    with patch("src.metrics_client._session", mock_session):
        with pytest.raises(requests.HTTPError):
            _get("http://prometheus/api", {}, retries=3, delay=0)
    assert mock_session.get.call_count == 1
