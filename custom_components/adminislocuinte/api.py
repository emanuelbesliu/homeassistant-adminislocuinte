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

    def _get_session_cookie_value(self) -> str | None:
        """Return the current value of the 'adminis' session cookie."""
        if not self._session:
            return None
        for cookie in self._session.cookie_jar:
            if cookie.key == "adminis":
                return cookie.value
        return None

    @property
    def _browser_headers(self) -> dict[str, str]:
        """Return browser-like headers to avoid Cloudflare/WAF blocks."""
        return {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "ro-RO,ro;q=0.9,en;q=0.8",
            "Referer": DASHBOARD_URL,
            "X-Requested-With": "XMLHttpRequest",
        }

    async def authenticate(self) -> bool:
        """Authenticate with the Adminis Locuințe platform.

        The authentication flow:
        1. GET login page to establish initial session cookies
        2. Record the pre-login session cookie value
        3. POST credentials with formSubmitted=1
        4. Follow redirects so the cookie jar captures the new ``adminis``
           session cookie regardless of which response in the chain sets it
        5. Verify authentication succeeded by checking:
           a. The ``adminis`` cookie value changed (new authenticated session)
           b. OR the final URL is the dashboard (redirect after login)
           c. AND the response body does not contain login error messages
        """
        assert self._session is not None, "Call async_init() first"

        # Browser-like headers to avoid Cloudflare blocks
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
            "Accept": (
                "text/html,application/xhtml+xml,application/xml;"
                "q=0.9,image/webp,*/*;q=0.8"
            ),
            "Accept-Language": "ro-RO,ro;q=0.9,en;q=0.8",
            "Referer": LOGIN_URL,
            "Origin": BASE_URL,
        }

        try:
            _LOGGER.debug("Starting Adminis Locuințe authentication")

            # Step 1: GET the login page to seed the cookie jar
            async with self._session.get(LOGIN_URL, headers=headers) as response:
                if response.status != 200:
                    _LOGGER.error(f"Failed to load login page: {response.status}")
                    raise Exception(f"Failed to load login page: {response.status}")

            # Step 2: Record pre-login cookie value
            pre_login_cookie = self._get_session_cookie_value()
            _LOGGER.debug(
                "Pre-login session cookie: %s",
                pre_login_cookie[:8] + "..." if pre_login_cookie else "None",
            )

            # Step 3: POST credentials
            login_data = {
                "email": self._username,
                "password": self._password,
                "formSubmitted": "1",
            }

            async with self._session.post(
                LOGIN_URL,
                data=login_data,
                headers=headers,
                allow_redirects=True,  # Follow the full redirect chain
            ) as response:
                final_url = str(response.url)
                response_text = await response.text()
                _LOGGER.debug(
                    f"Login POST completed: status={response.status}, "
                    f"final_url={final_url}"
                )

            # Step 4: Verify authentication actually succeeded
            post_login_cookie = self._get_session_cookie_value()
            _LOGGER.debug(
                "Post-login session cookie: %s",
                post_login_cookie[:8] + "..." if post_login_cookie else "None",
            )

            # Check for login error messages in the response HTML
            error_indicators = [
                "notification-error",
                "Completarea adresei de e-mail",
                "parolei sunt obligatorii",
                "Adresa de e-mail sau parola sunt incorecte",
                "autentificare eșuată",
            ]
            response_lower = response_text.lower()
            for indicator in error_indicators:
                if indicator.lower() in response_lower:
                    _LOGGER.error(
                        "Authentication failed - login page returned error: "
                        "found '%s' in response",
                        indicator,
                    )
                    raise AuthenticationError(
                        f"Login failed: server returned error page "
                        f"(detected '{indicator}')"
                    )

            # Verify the session cookie changed (indicates server created
            # a new authenticated session) OR we were redirected to dashboard
            dashboard_redirect = "/i/" in final_url and "autentificare" not in final_url
            cookie_changed = (
                post_login_cookie
                and pre_login_cookie
                and post_login_cookie != pre_login_cookie
            )

            if dashboard_redirect or cookie_changed:
                self._authenticated = True
                _LOGGER.info(
                    "Successfully authenticated with Adminis Locuințe "
                    "(redirect=%s, cookie_changed=%s)",
                    dashboard_redirect,
                    cookie_changed,
                )
                return True

            # Fallback: cookie exists and we're not on the login page
            if self._has_session_cookie() and "autentificare" not in final_url:
                self._authenticated = True
                _LOGGER.info(
                    "Successfully authenticated with Adminis Locuințe "
                    "(fallback: cookie present, not on login page)"
                )
                return True

            # Authentication failed
            jar_cookies = {c.key: c.value[:8] + "..." for c in self._session.cookie_jar}
            _LOGGER.error(
                "Authentication failed. Cookie changed: %s, "
                "dashboard redirect: %s, final_url: %s, "
                "cookies present: %s",
                cookie_changed,
                dashboard_redirect,
                final_url,
                list(jar_cookies.keys()),
            )
            raise AuthenticationError(
                f"Login failed: no redirect to dashboard and session cookie "
                f"did not change. Final URL: {final_url}"
            )

        except AuthenticationError:
            raise
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
            async with self._session.get(DASHBOARD_URL, headers=self._browser_headers) as response:
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
            pending_data_available = False
            last_payment = None
            payment_data_available = False

            for location_id in self._location_ids:
                location_data = {}

                # Add location info (name, address, type)
                if location_id in self._location_info:
                    location_data["info"] = self._location_info[location_id]

                # Fetch pending payments for this location
                try:
                    pending_payments = await self._fetch_pending_payments(location_id)
                    location_data["pending_payments"] = pending_payments
                    pending_data_available = True

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
                    payment_data_available = True

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
            # If no pending data was fetched at all (all locations failed),
            # set total_pending to None so the global sensor shows unavailable
            summary: dict[str, Any] = {
                "total_pending": total_pending if pending_data_available else None,
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

    async def _check_api_response(
        self, response: aiohttp.ClientResponse, endpoint_name: str
    ) -> dict[str, Any]:
        """Validate an API response and return the parsed JSON.

        Distinguishes between:
        - **Server-side API errors** (403 with JSON body like
          ``{"error":1,"message":"Eroare comunicare server."}``) which are
          transient backend problems — NOT authentication failures.
        - **Session expiry** (401/403 with HTML body or redirect to login)
          which indicates the session cookie is no longer valid.

        Raises:
            AuthenticationError: If the session has expired (HTML redirect
                to login page or 401 without a JSON body).
            Exception: For server-side API errors (503-like conditions
                returned as 403 by the Adminis backend) or other HTTP errors.
        """
        content_type = response.headers.get("Content-Type", "")

        if response.status in (401, 403):
            # Try to read the body to distinguish auth failure from API error
            if "application/json" in content_type:
                try:
                    data = await response.json()
                    # Server-side error: the API authenticated us fine but
                    # its backend failed (e.g., database/billing system down).
                    # This is NOT an authentication error — don't trigger reauth.
                    error_msg = data.get("message", "Unknown server error")
                    _LOGGER.warning(
                        "Server-side API error fetching %s (HTTP %d): %s",
                        endpoint_name,
                        response.status,
                        error_msg,
                    )
                    raise Exception(
                        f"Server error fetching {endpoint_name}: "
                        f"{error_msg} (HTTP {response.status})"
                    )
                except (ValueError, KeyError):
                    pass  # Not valid JSON — fall through to auth error

            # Non-JSON 401/403 = genuine session expiry
            raise AuthenticationError(
                f"Session expired fetching {endpoint_name}: {response.status}"
            )

        if response.status == 200:
            if "text/html" in content_type:
                raise AuthenticationError(
                    f"Session expired: {endpoint_name} returned HTML "
                    f"(login redirect)"
                )
            return await response.json()

        raise Exception(
            f"Failed to fetch {endpoint_name}: HTTP {response.status}"
        )

    async def _fetch_pending_payments(self, location_id: str) -> dict[str, Any]:
        """Fetch pending payments for a specific location."""
        assert self._session is not None
        url = API_PENDING_PAYMENTS.format(location_id=location_id)
        async with self._session.get(url, headers=self._browser_headers) as response:
            return await self._check_api_response(response, "pending payments")

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

        async with self._session.get(url, headers=self._browser_headers) as response:
            return await self._check_api_response(response, "receipt")

    async def _fetch_payment_history(self, location_id: str) -> dict[str, Any]:
        """Fetch payment history for a specific location."""
        assert self._session is not None
        url = API_PAYMENTS_HISTORY.format(location_id=location_id)
        async with self._session.get(url, headers=self._browser_headers) as response:
            return await self._check_api_response(response, "payment history")

    async def _fetch_counters(self, location_id: str) -> dict[str, Any]:
        """Fetch counter readings for a specific location."""
        assert self._session is not None
        url = API_COUNTERS.format(location_id=location_id)
        async with self._session.get(url, headers=self._browser_headers) as response:
            return await self._check_api_response(response, "counters")

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
