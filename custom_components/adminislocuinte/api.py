"""API client for Adminis Locuințe.

Copyright (c) 2026 Emanuel Besliu
Licensed under the MIT License

This integration was developed through reverse engineering of the
adminislocuinte.ro platform and is not affiliated with or endorsed
by Adminis Locuinte.
"""
from __future__ import annotations

import logging
import re
from typing import Any
import aiohttp
from aiohttp import ClientSession, CookieJar

from .const import (
    BASE_URL,
    DASHBOARD_URL,
    LOGIN_URL,
    API_PENDING_PAYMENTS,
    API_PAYMENTS_HISTORY,
    API_COUNTERS,
    # API_RECEIPT,  # Currently returns 403 - disabled
)

_LOGGER = logging.getLogger(__name__)


class AuthenticationError(Exception):
    """Raised when the API returns a 401/403 or session has expired."""


class AdminisLocuinteAPI:
    """API client for Adminis Locuințe platform.

    Uses a dedicated aiohttp.ClientSession with its own cookie jar so that
    session cookies (especially the ``adminis`` session ID) are tracked
    automatically by the jar across requests and redirects.  This avoids
    the problems caused by manually managing cookies in a dict, where
    Set-Cookie headers could be absorbed by the session jar without
    appearing in ``response.cookies``.
    """

    def __init__(self, username: str, password: str) -> None:
        """Initialize the API client.

        Call :meth:`async_init` to create the underlying aiohttp session
        before using any network methods.
        """
        self._username = username
        self._password = password
        self._session: ClientSession | None = None
        self._authenticated = False
        self._location_ids: list[str] = []
        self._location_info: dict[str, dict[str, str]] = {}

    async def async_init(self) -> None:
        """Create the dedicated aiohttp session with its own cookie jar."""
        jar = CookieJar(unsafe=True)  # unsafe=True allows non-RFC cookies
        self._session = ClientSession(cookie_jar=jar)

    async def async_close(self) -> None:
        """Close the dedicated aiohttp session."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    def _clear_cookies(self) -> None:
        """Clear all cookies from the session jar."""
        if self._session:
            self._session.cookie_jar.clear()

    def _has_session_cookie(self) -> bool:
        """Check whether the session jar contains the 'adminis' cookie."""
        if not self._session:
            return False
        for cookie in self._session.cookie_jar:
            if cookie.key == "adminis":
                return True
        return False

    async def authenticate(self) -> bool:
        """Authenticate with the Adminis Locuințe platform.

        The authentication flow:
        1. GET login page to establish initial session cookies
        2. POST credentials with formSubmitted=1
        3. Follow redirects so the cookie jar captures the ``adminis``
           session cookie regardless of which response in the chain sets it
        4. Verify the ``adminis`` cookie is present in the jar
        """
        assert self._session is not None, "Call async_init() first"

        try:
            _LOGGER.debug("Starting Adminis Locuințe authentication")

            # Step 1: GET the login page to seed the cookie jar
            async with self._session.get(LOGIN_URL) as response:
                if response.status != 200:
                    _LOGGER.error(f"Failed to load login page: {response.status}")
                    raise Exception(f"Failed to load login page: {response.status}")

            # Step 2: POST credentials
            login_data = {
                "email": self._username,
                "password": self._password,
                "formSubmitted": "1",
            }

            async with self._session.post(
                LOGIN_URL,
                data=login_data,
                allow_redirects=True,  # Follow the full redirect chain
            ) as response:
                final_url = str(response.url)
                _LOGGER.debug(
                    f"Login POST completed: status={response.status}, "
                    f"final_url={final_url}"
                )

            # Step 3: Verify we got the session cookie in the jar
            if self._has_session_cookie():
                self._authenticated = True
                _LOGGER.info("Successfully authenticated with Adminis Locuințe")
                return True

            # The cookie jar didn't capture 'adminis'.  Log what we do
            # have for debugging.
            jar_cookies = {c.key: c.value[:8] + "..." for c in self._session.cookie_jar}
            _LOGGER.error(
                "Authentication completed but 'adminis' session cookie not found "
                "in cookie jar. Cookies present: %s",
                list(jar_cookies.keys()),
            )
            return False

        except Exception as err:
            _LOGGER.error(f"Authentication error: {err}")
            raise

    async def _extract_location_ids(self) -> list[str]:
        """Extract location IDs and details from the dashboard HTML.

        Location IDs are embedded in <option value="ID" data-code="CODE"> elements.
        We need the value attribute (actual location ID), not the data-code.
        Also extracts location names and addresses.

        Raises:
            AuthenticationError: If the session has expired (redirected to login page).
        """
        assert self._session is not None

        try:
            async with self._session.get(DASHBOARD_URL) as response:
                if response.status in (401, 403):
                    raise AuthenticationError(
                        f"Session expired loading dashboard: {response.status}"
                    )
                if response.status == 200:
                    html = await response.text()

                    # Detect redirect-to-login: server returns 200 with login
                    # page HTML instead of the dashboard
                    if "autentificare" in html.lower() and '<option' not in html:
                        raise AuthenticationError(
                            "Session expired: dashboard returned login page"
                        )

                    # Extract location IDs from <option value="ID" data-code="CODE">Location Name</option>
                    pattern = r'<option\s+value="(\d+)"\s+data-code="(\d+)"[^>]*>([^<]+)</option>'
                    matches = re.findall(pattern, html)

                    location_ids = []
                    for loc_id, code, loc_name in matches:
                        if loc_id not in location_ids:
                            location_ids.append(loc_id)
                            self._location_info[loc_id] = {
                                "name": loc_name.strip(),
                                "id": loc_id,
                                "code": code,
                            }

                            # Try to extract apartment/parking number
                            if ", ap. " in loc_name:
                                apt = loc_name.split(", ap. ")[1].split(",")[0]
                                self._location_info[loc_id]["apartment"] = apt
                                if "PARCARI" in loc_name or apt.startswith("S"):
                                    self._location_info[loc_id]["type"] = "parking"
                                else:
                                    self._location_info[loc_id]["type"] = "apartment"
                            else:
                                self._location_info[loc_id]["type"] = "unknown"

                    # Extract association ID
                    assoc_match = re.search(r'data-assoc="(\d+)"', html)
                    if assoc_match:
                        assoc_id = assoc_match.group(1)
                        _LOGGER.debug(f"Found association ID: {assoc_id}")
                        for loc_id in location_ids:
                            self._location_info[loc_id]["association_id"] = assoc_id

                    _LOGGER.debug(f"Found {len(location_ids)} location(s): {location_ids}")
                    _LOGGER.debug(f"Location info: {self._location_info}")
                    return location_ids
                else:
                    raise Exception(f"Failed to load dashboard: {response.status}")
        except AuthenticationError:
            raise
        except Exception as err:
            _LOGGER.error(f"Error extracting location IDs: {err}")
            return []

    async def get_data(self) -> dict[str, Any]:
        """Fetch consumption and billing data from all locations.

        Returns data structure:
        {
            "locations": {
                "16835": {
                    "pending_payments": {...},
                    "payment_history": [...],
                    "counters": {...}
                },
                "17012": {...}
            },
            "summary": {
                "total_pending": 0.0,
                "last_payment_amount": 862.12,
                "last_payment_date": "30.01.2026",
                "location_count": 2
            }
        }
        """
        # Always re-authenticate before fetching data.
        # Cookies expire between 6-hour refresh cycles, so a fresh login
        # on every call is the only reliable approach.
        self._clear_cookies()
        self._authenticated = False
        await self.authenticate()

        # Re-extract location IDs with fresh cookies every time.
        self._location_ids = await self._extract_location_ids()
        if not self._location_ids:
            _LOGGER.warning("No location IDs found")
            return {"locations": {}, "summary": {"total_pending": 0.0, "location_count": 0}}

        try:
            # Collect data from all locations
            locations_data = {}
            total_pending = 0.0
            last_payment = None

            for location_id in self._location_ids:
                location_data = {}

                # Add location info (name, address, type)
                if location_id in self._location_info:
                    location_data["info"] = self._location_info[location_id]

                # Fetch pending payments for this location
                try:
                    pending_payments = await self._fetch_pending_payments(location_id)
                    location_data["pending_payments"] = pending_payments

                    # Extract pending amount if available
                    if pending_payments and pending_payments.get("results"):
                        results = pending_payments["results"]
                        location_pending = 0.0

                        if results.get("totalsNoviprop"):
                            try:
                                location_pending = float(results["totalsNoviprop"])
                                _LOGGER.debug(f"Location {location_id} pending from totalsNoviprop: {location_pending} RON")
                            except (ValueError, TypeError) as e:
                                _LOGGER.warning(f"Failed to parse totalsNoviprop for location {location_id}: {e}")

                        if location_pending > 0:
                            total_pending += location_pending
                            _LOGGER.info(f"Location {location_id} has pending: {location_pending} RON")

                except AuthenticationError:
                    raise
                except Exception as err:
                    _LOGGER.error(f"Error fetching pending payments for {location_id}: {err}")
                    location_data["pending_payments"] = None

                # Fetch payment history for this location
                try:
                    payment_history = await self._fetch_payment_history(location_id)
                    location_data["payment_history"] = payment_history

                    if payment_history.get("results") and len(payment_history["results"]) > 0:
                        latest = payment_history["results"][0]
                        if not last_payment:
                            last_payment = {
                                "amount": float(latest.get("amount", 0)),
                                "date": latest.get("date", ""),
                                "location_id": location_id,
                            }
                except AuthenticationError:
                    raise
                except Exception as err:
                    _LOGGER.error(f"Error fetching payment history for {location_id}: {err}")
                    location_data["payment_history"] = None

                # Try to fetch counters (API currently returns invalid JSON)
                try:
                    counters = await self._fetch_counters(location_id)
                    location_data["counters"] = counters
                except AuthenticationError:
                    raise
                except (aiohttp.ContentTypeError, ValueError) as err:
                    _LOGGER.debug(f"Counters API returned invalid data for {location_id}: {err}")
                    location_data["counters"] = None
                except Exception as err:
                    _LOGGER.debug(f"Error fetching counters for {location_id}: {err}")
                    location_data["counters"] = None

                locations_data[location_id] = location_data

            # Build summary
            summary: dict[str, Any] = {
                "total_pending": total_pending,
                "location_count": len(self._location_ids),
            }

            if last_payment:
                summary["last_payment_amount"] = last_payment["amount"]
                summary["last_payment_date"] = last_payment["date"]
                summary["last_payment_location_id"] = last_payment["location_id"]

            return {
                "locations": locations_data,
                "summary": summary,
            }

        except Exception as err:
            _LOGGER.error(f"Error fetching data: {err}")
            raise

    # ------------------------------------------------------------------
    # Private fetch helpers
    # ------------------------------------------------------------------

    async def _fetch_pending_payments(self, location_id: str) -> dict[str, Any]:
        """Fetch pending payments for a specific location."""
        assert self._session is not None
        url = API_PENDING_PAYMENTS.format(location_id=location_id)
        async with self._session.get(url) as response:
            if response.status in (401, 403):
                raise AuthenticationError(
                    f"Session expired fetching pending payments: {response.status}"
                )
            if response.status == 200:
                content_type = response.headers.get("Content-Type", "")
                if "text/html" in content_type:
                    raise AuthenticationError(
                        "Session expired: pending payments returned HTML (login redirect)"
                    )
                return await response.json()
            raise Exception(f"Failed to fetch pending payments: {response.status}")

    async def _fetch_receipt(self, location_id: str, month: int | None = None, year: int | None = None) -> dict[str, Any]:
        """Fetch receipt for a specific location and month.

        NOTE: This API currently returns 403 Forbidden. Disabled in get_data().
        Payment history API provides the same data with better reliability.
        """
        assert self._session is not None
        from .const import API_RECEIPT, API_RECEIPT_MONTH

        if month and year:
            url = API_RECEIPT_MONTH.format(location_id=location_id, month=month, year=year)
        else:
            url = API_RECEIPT.format(location_id=location_id)

        async with self._session.get(url) as response:
            if response.status in (401, 403):
                raise AuthenticationError(
                    f"Session expired fetching receipt: {response.status}"
                )
            if response.status == 200:
                content_type = response.headers.get("Content-Type", "")
                if "text/html" in content_type:
                    raise AuthenticationError(
                        "Session expired: receipt returned HTML (login redirect)"
                    )
                return await response.json()
            raise Exception(f"Failed to fetch receipt: {response.status}")

    async def _fetch_payment_history(self, location_id: str) -> dict[str, Any]:
        """Fetch payment history for a specific location."""
        assert self._session is not None
        url = API_PAYMENTS_HISTORY.format(location_id=location_id)
        async with self._session.get(url) as response:
            if response.status in (401, 403):
                raise AuthenticationError(
                    f"Session expired fetching payment history: {response.status}"
                )
            if response.status == 200:
                content_type = response.headers.get("Content-Type", "")
                if "text/html" in content_type:
                    raise AuthenticationError(
                        "Session expired: payment history returned HTML (login redirect)"
                    )
                return await response.json()
            raise Exception(f"Failed to fetch payment history: {response.status}")

    async def _fetch_counters(self, location_id: str) -> dict[str, Any]:
        """Fetch counter readings for a specific location."""
        assert self._session is not None
        url = API_COUNTERS.format(location_id=location_id)
        async with self._session.get(url) as response:
            if response.status in (401, 403):
                raise AuthenticationError(
                    f"Session expired fetching counters: {response.status}"
                )
            if response.status == 200:
                content_type = response.headers.get("Content-Type", "")
                if "text/html" in content_type:
                    raise AuthenticationError(
                        "Session expired: counters returned HTML (login redirect)"
                    )
                return await response.json()
            raise Exception(f"Failed to fetch counters: {response.status}")

    # ------------------------------------------------------------------
    # Public convenience methods
    # ------------------------------------------------------------------

    async def get_monthly_consumption(self, year: int, month: int) -> dict[str, Any]:
        """Get consumption data for a specific month.

        Note: Receipt API currently returns 403. This may require:
        - Active billing data for the specified month
        - Different authentication or permissions
        """
        # TODO: Implement when receipt API access is resolved
        _LOGGER.warning("Monthly consumption API not yet available (403 Forbidden)")
        return {}

    async def get_billing_info(self) -> dict[str, Any]:
        """Get current billing information from all locations."""
        # get_data() handles re-authentication internally
        data = await self.get_data()
        return data.get("summary", {})

    async def get_payment_history(self, location_id: str | None = None) -> list[dict[str, Any]]:
        """Get payment history for all locations or a specific location."""
        # Re-authenticate with fresh cookies
        self._clear_cookies()
        self._authenticated = False
        await self.authenticate()

        if not self._location_ids:
            self._location_ids = await self._extract_location_ids()

        all_payments: list[dict[str, Any]] = []
        location_ids = [location_id] if location_id else self._location_ids

        for loc_id in location_ids:
            try:
                history = await self._fetch_payment_history(loc_id)
                if history.get("results"):
                    for payment in history["results"]:
                        payment["location_id"] = loc_id
                        all_payments.append(payment)
            except Exception as err:
                _LOGGER.error(f"Error fetching payment history for {loc_id}: {err}")

        all_payments.sort(key=lambda x: x.get("date", ""), reverse=True)
        return all_payments

    async def get_locations(self) -> list[str]:
        """Get list of location IDs for this account."""
        # Re-authenticate with fresh cookies
        self._clear_cookies()
        self._authenticated = False
        await self.authenticate()

        self._location_ids = await self._extract_location_ids()
        return self._location_ids
