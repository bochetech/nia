"""
Bokun REST API v1 client.

Authentication: HMAC-SHA1
  Signature = Base64( HmacSHA1( date + accessKey + METHOD + path, secretKey ) )

Headers required on every request:
  X-Bokun-Date        — UTC datetime "yyyy-MM-dd HH:mm:ss"
  X-Bokun-AccessKey   — access key
  X-Bokun-Signature   — computed signature (see above)

POST requests also need:
  Content-Type: application/json;charset=UTF-8
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import time
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlencode

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from shared.utils.logging import get_logger

logger = get_logger(__name__)

_BOKUN_DATE_FMT = "%Y-%m-%d %H:%M:%S"


def _build_signature(
    *,
    date_str: str,
    access_key: str,
    method: str,
    path: str,
    secret_key: str,
) -> str:
    """
    Concatenate date + accessKey + METHOD + path, then HMAC-SHA1 with secretKey,
    then Base64-encode the raw bytes.
    """
    message = f"{date_str}{access_key}{method.upper()}{path}"
    raw = hmac.new(
        secret_key.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha1,
    ).digest()
    return base64.b64encode(raw).decode("utf-8")


def _bokun_headers(
    *,
    access_key: str,
    secret_key: str,
    method: str,
    path: str,
    is_post: bool = False,
) -> dict[str, str]:
    """Return the three mandatory Bokun auth headers (+ Content-Type for POST)."""
    date_str = datetime.now(UTC).strftime(_BOKUN_DATE_FMT)
    signature = _build_signature(
        date_str=date_str,
        access_key=access_key,
        method=method,
        path=path,
        secret_key=secret_key,
    )
    headers: dict[str, str] = {
        "X-Bokun-Date": date_str,
        "X-Bokun-AccessKey": access_key,
        "X-Bokun-Signature": signature,
        "Accept": "application/json",
    }
    if is_post:
        headers["Content-Type"] = "application/json;charset=UTF-8"
    return headers


class BokunClient:
    """Thin async client for the Bokun REST v1 API."""

    def __init__(self, *, access_key: str, secret_key: str, base_url: str) -> None:
        self._access_key = access_key
        self._secret_key = secret_key
        self._base_url = base_url.rstrip("/")

    # ── Private helpers ───────────────────────────────────────────────────────

    def _headers(self, method: str, path: str, is_post: bool = False) -> dict[str, str]:
        return _bokun_headers(
            access_key=self._access_key,
            secret_key=self._secret_key,
            method=method,
            path=path,
            is_post=is_post,
        )

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
    async def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        # Build full path with query string for signature
        qs = ("?" + urlencode(params)) if params else ""
        full_path = path + qs
        headers = self._headers("GET", full_path)
        t0 = time.perf_counter()
        async with httpx.AsyncClient(base_url=self._base_url, timeout=20.0) as client:
            resp = await client.get(path, params=params, headers=headers)
        resp.raise_for_status()
        latency_ms = round((time.perf_counter() - t0) * 1000)
        logger.debug("bokun_get", path=path, status=resp.status_code, latency_ms=latency_ms)
        return resp.json()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
    async def _post(self, path: str, body: dict[str, Any], params: dict[str, Any] | None = None) -> Any:
        qs = ("?" + urlencode(params)) if params else ""
        full_path = path + qs
        headers = self._headers("POST", full_path, is_post=True)
        t0 = time.perf_counter()
        async with httpx.AsyncClient(base_url=self._base_url, timeout=30.0) as client:
            resp = await client.post(path, json=body, params=params, headers=headers)
        resp.raise_for_status()
        latency_ms = round((time.perf_counter() - t0) * 1000)
        logger.debug("bokun_post", path=path, status=resp.status_code, latency_ms=latency_ms)
        return resp.json()

    # ── Public API methods ────────────────────────────────────────────────────

    async def get_active_activity_ids(self) -> list[int]:
        """
        GET /activity.json/active-ids
        Returns the list of activity IDs that are currently active / published.

        Bokun returns one of:
          - A plain JSON array:  [101, 202, ...]
          - A supplier-grouped object:  {"suppliers": [{"supplierId": X, "activityIds": [...]}]}
          - A simple object:  {"activityIds": [...]}
        """
        result = await self._get("/activity.json/active-ids")
        if isinstance(result, list):
            return [int(x) for x in result]
        if isinstance(result, dict):
            # Simple flat list
            if "activityIds" in result:
                return [int(x) for x in result["activityIds"]]
            # Supplier-grouped: flatten all IDs across all suppliers
            if "suppliers" in result:
                ids: list[int] = []
                for supplier in result["suppliers"]:
                    ids.extend(int(x) for x in supplier.get("activityIds", []))
                return ids
        return []

    async def get_activity(
        self,
        activity_id: int,
        *,
        lang: str = "EN",
        currency: str = "USD",
    ) -> dict[str, Any]:
        """
        GET /activity.json/{id}
        Returns full details for a single activity.
        """
        path = f"/activity.json/{activity_id}"
        return await self._get(path, params={"lang": lang, "currency": currency})

    async def get_availabilities(
        self,
        activity_id: int,
        *,
        start_date: str,
        end_date: str,
        currency: str = "CLP",
        lang: str = "EN",
        include_sold_out: bool = False,
    ) -> list[dict[str, Any]]:
        """
        GET /activity.json/{id}/availabilities?start=YYYY-MM-DD&end=YYYY-MM-DD&currency=CLP
        Returns a list of availability slot objects for the date range.

        Note: Bokun uses `start`/`end` query params (not `startDate`/`endDate`).
              The endpoint is GET, not POST.
              includeSoldOut is not a supported query param — filter client-side if needed.
        """
        path = f"/activity.json/{activity_id}/availabilities"
        params: dict[str, Any] = {
            "start": start_date,
            "end": end_date,
            "currency": currency,
        }
        result = await self._get(path, params=params)
        slots: list[dict[str, Any]] = result if isinstance(result, list) else []
        if not include_sold_out:
            slots = [s for s in slots if s.get("availabilityCount", 1) > 0]
        return slots

    async def list_activities_with_details(
        self,
        *,
        lang: str = "EN",
        currency: str = "USD",
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """
        Convenience: fetches all active activity IDs, then concurrently retrieves
        details for each one (up to `limit`).
        Returns a list of activity detail dicts.
        """
        import asyncio

        ids = await self.get_active_activity_ids()
        ids = ids[:limit]

        if not ids:
            return []

        results = await asyncio.gather(
            *[self.get_activity(aid, lang=lang, currency=currency) for aid in ids],
            return_exceptions=True,
        )

        activities: list[dict[str, Any]] = []
        for aid, result in zip(ids, results):
            if isinstance(result, Exception):
                logger.warning("bokun_activity_detail_failed", activity_id=aid, error=str(result))
            else:
                activities.append(result)
        return activities
