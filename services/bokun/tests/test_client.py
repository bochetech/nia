"""
Unit tests for the Bokun client — HMAC signature and endpoint logic.
All HTTP calls are mocked; no real API credentials required.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import httpx

from app.client import BokunClient, _build_signature, _bokun_headers


# ─────────────────────────────────────────────────────────────────
# Signature helpers
# ─────────────────────────────────────────────────────────────────

def _expected_sig(date_str: str, access_key: str, method: str, path: str, secret_key: str) -> str:
    msg = f"{date_str}{access_key}{method.upper()}{path}"
    raw = hmac.new(secret_key.encode(), msg.encode(), hashlib.sha1).digest()
    return base64.b64encode(raw).decode()


def test_build_signature_matches_reference():
    """Reproduce the official Bokun signature example from the docs."""
    sig = _build_signature(
        date_str="2013-11-09 14:33:46",
        access_key="de235a6a15c340b6b1e1cb5f3687d04a",
        method="POST",
        path="/activity.json/search?lang=EN&currency=ISK",
        secret_key="23e2c7da7f7048e5b46f96bc91324800",
    )
    assert sig == "XrOiTYa9Y34zscnLCsAEh8ieoyo="


def test_bokun_headers_get():
    headers = _bokun_headers(
        access_key="abc",
        secret_key="xyz",
        method="GET",
        path="/activity.json/active-ids",
    )
    assert "X-Bokun-Date" in headers
    assert headers["X-Bokun-AccessKey"] == "abc"
    assert "X-Bokun-Signature" in headers
    assert "Content-Type" not in headers


def test_bokun_headers_post_has_content_type():
    headers = _bokun_headers(
        access_key="abc",
        secret_key="xyz",
        method="POST",
        path="/activity.json/1/availabilities",
        is_post=True,
    )
    assert headers.get("Content-Type") == "application/json;charset=UTF-8"


# ─────────────────────────────────────────────────────────────────
# BokunClient unit tests (mocked HTTP)
# ─────────────────────────────────────────────────────────────────

FAKE_CREDS = {"access_key": "TESTKEY", "secret_key": "TESTSECRET", "base_url": "https://api.bokun.io"}


def _make_response(data, status_code: int = 200) -> MagicMock:
    mock = MagicMock(spec=httpx.Response)
    mock.status_code = status_code
    mock.json.return_value = data
    mock.raise_for_status = MagicMock()
    return mock


@pytest.mark.asyncio
async def test_get_active_activity_ids_list():
    """get_active_activity_ids should parse a plain JSON array."""
    client = BokunClient(**FAKE_CREDS)
    with patch("app.client.httpx.AsyncClient") as mock_cls:
        mock_http = AsyncMock()
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_http.get = AsyncMock(return_value=_make_response([101, 202, 303]))

        ids = await client.get_active_activity_ids()
        assert ids == [101, 202, 303]


@pytest.mark.asyncio
async def test_get_active_activity_ids_dict_format():
    """get_active_activity_ids should also handle {'activityIds': [...]} format."""
    client = BokunClient(**FAKE_CREDS)
    with patch("app.client.httpx.AsyncClient") as mock_cls:
        mock_http = AsyncMock()
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_http.get = AsyncMock(return_value=_make_response({"activityIds": [1, 2]}))

        ids = await client.get_active_activity_ids()
        assert ids == [1, 2]


@pytest.mark.asyncio
async def test_get_availabilities_calls_get():
    """get_availabilities should use GET with start/end query params."""
    client = BokunClient(**FAKE_CREDS)
    fake_slots = [{"availabilityCount": 5, "startTime": "10:00", "startTimeLabel": "10:00 AM"}]

    with patch("app.client.httpx.AsyncClient") as mock_cls:
        mock_http = AsyncMock()
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_http.get = AsyncMock(return_value=_make_response(fake_slots))

        result = await client.get_availabilities(
            42,
            start_date="2026-06-01",
            end_date="2026-06-07",
            currency="CLP",
        )
        assert result == fake_slots

        # Check the GET was called with the correct query params
        call_kwargs = mock_http.get.call_args
        params = call_kwargs.kwargs.get("params") or {}
        assert params["start"] == "2026-06-01"
        assert params["end"] == "2026-06-07"
        assert params["currency"] == "CLP"


@pytest.mark.asyncio
async def test_list_activities_with_details_concurrent():
    """list_activities_with_details should fetch details for each ID."""
    client = BokunClient(**FAKE_CREDS)

    ids_response = [1, 2]
    detail_1 = {"id": 1, "title": "Wine Tour"}
    detail_2 = {"id": 2, "title": "Horseback Ride"}

    call_count = 0

    async def fake_get(path, params=None, headers=None):
        nonlocal call_count
        call_count += 1
        if "active-ids" in path:
            return _make_response(ids_response)
        if "/1" in path:
            return _make_response(detail_1)
        if "/2" in path:
            return _make_response(detail_2)
        return _make_response({})

    with patch("app.client.httpx.AsyncClient") as mock_cls:
        mock_http = AsyncMock()
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_http.get = fake_get

        activities = await client.list_activities_with_details()
        assert len(activities) == 2
