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
from aiohttp import ClientSession

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


class AdminisLocuinteAPI:
    """API client for Adminis Locuințe platform."""

    def __init__(self, session: ClientSession, username: str, password: str) -> None:
        """Initialize the API client."""
        self._session = session
        self._username = username
        self._password = password
        self._cookies: dict[str, str] = {}
        self._authenticated = False
        self._location_ids: list[str] = []
        self._location_info: dict[str, dict[str, str]] = {}  # Store location details

    async def authenticate(self) -> bool:
        """Authenticate with the Adminis Locuințe platform.
        
        The authentication flow:
        1. GET login page to establish session
        2. POST credentials with formSubmitted=1
        3. Server responds with 302 redirect and sets 'adminis' cookie
        4. Cookie is used for all subsequent API calls
        """
        try:
            # First, get the login page to establish initial session
            async with self._session.get(LOGIN_URL) as response:
                if response.status != 200:
                    _LOGGER.error(f"Failed to load login page: {response.status}")
                    raise Exception(f"Failed to load login page: {response.status}")
                
                # Store cookies from initial page load
                self._cookies.update({k: v.value for k, v in response.cookies.items()})

            # Prepare login data - exact format required by the API
            login_data = {
                "email": self._username,
                "password": self._password,
                "formSubmitted": "1",
            }

            # Submit login form
            async with self._session.post(
                LOGIN_URL,
                data=login_data,
                cookies=self._cookies,
                allow_redirects=False,  # Don't follow redirects to capture cookies
            ) as response:
                # Update cookies after login - the 'adminis' cookie is the session ID
                self._cookies.update({k: v.value for k, v in response.cookies.items()})
                
                # Successful login returns 302 redirect to /i/
                if response.status == 302:
                    # Verify we got the session cookie
                    if 'adminis' in self._cookies:
                        self._authenticated = True
                        _LOGGER.info("Successfully authenticated with Adminis Locuințe")
                        return True
                    else:
                        _LOGGER.error("Login returned 302 but no session cookie found")
                        return False
                else:
                    _LOGGER.error(f"Login failed with status: {response.status}")
                    return False

        except Exception as err:
            _LOGGER.error(f"Authentication error: {err}")
            raise

    async def _extract_location_ids(self) -> list[str]:
        """Extract location IDs and details from the dashboard HTML.
        
        Location IDs are embedded in the dashboard HTML as data-code attributes.
        Also extracts location names and addresses.
        """
        try:
            async with self._session.get(
                DASHBOARD_URL,
                cookies=self._cookies,
            ) as response:
                if response.status == 200:
                    html = await response.text()
                    
                    # Extract location IDs and names
                    # Pattern: data-code="123456">Location Name</
                    pattern = r'data-code="(\d+)"[^>]*>([^<]+)<'
                    matches = re.findall(pattern, html)
                    
                    location_ids = []
                    for loc_id, loc_name in matches:
                        if loc_id not in location_ids:
                            location_ids.append(loc_id)
                            # Parse location name to extract details
                            # Format: "Str. Exemplu nr. 1, bloc A1, scara A, ap. 12, Iasi, Iasi"
                            self._location_info[loc_id] = {
                                "name": loc_name.strip(),
                                "id": loc_id
                            }
                            
                            # Try to extract apartment/parking number
                            if ", ap. " in loc_name:
                                apt = loc_name.split(", ap. ")[1].split(",")[0]
                                self._location_info[loc_id]["apartment"] = apt
                                # Determine type
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
                    _LOGGER.error(f"Failed to load dashboard: {response.status}")
                    return []
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
        if not self._authenticated:
            await self.authenticate()

        try:
            # Get location IDs if we don't have them yet
            if not self._location_ids:
                self._location_ids = await self._extract_location_ids()
                if not self._location_ids:
                    _LOGGER.warning("No location IDs found")
                    return {"locations": {}, "summary": {"total_pending": 0.0, "location_count": 0}}

            # Collect data from all locations
            locations_data = {}
            total_pending = 0.0
            last_payment = None

            for location_id in self._location_ids:
                location_data = {}
                
                # Add location info (name, address, type)
                if location_id in self._location_info:
                    location_data["info"] = self._location_info[location_id]
                
                # Receipt API currently returns 403 Forbidden - skipping
                # Payment history provides the same data with better reliability
                # Uncomment when receipt API access is resolved
                # try:
                #     current_receipt = await self._fetch_receipt(location_id)
                #     location_data["current_receipt"] = current_receipt
                # except Exception as err:
                #     _LOGGER.debug(f"Error fetching current receipt for {location_id}: {err}")
                #     location_data["current_receipt"] = None
                
                # Fetch pending payments for this location
                try:
                    pending_payments = await self._fetch_pending_payments(location_id)
                    location_data["pending_payments"] = pending_payments
                    
                    # Extract pending amount if available
                    # Note: Current API returns null for all values, but structure is prepared
                    if pending_payments.get("results"):
                        results = pending_payments["results"]
                        if results.get("owner") or results.get("assoc"):
                            # TODO: Calculate actual pending amount when data is available
                            pass
                except Exception as err:
                    _LOGGER.error(f"Error fetching pending payments for {location_id}: {err}")
                    location_data["pending_payments"] = None

                # Fetch payment history for this location
                try:
                    payment_history = await self._fetch_payment_history(location_id)
                    location_data["payment_history"] = payment_history
                    
                    # Extract last payment info for summary
                    if payment_history.get("results") and len(payment_history["results"]) > 0:
                        latest = payment_history["results"][0]
                        if not last_payment:
                            last_payment = {
                                "amount": float(latest.get("amount", 0)),
                                "date": latest.get("date", ""),
                                "location_id": location_id
                            }
                except Exception as err:
                    _LOGGER.error(f"Error fetching payment history for {location_id}: {err}")
                    location_data["payment_history"] = None

                # Try to fetch counters (API currently returns invalid JSON)
                try:
                    counters = await self._fetch_counters(location_id)
                    location_data["counters"] = counters
                except (aiohttp.ContentTypeError, ValueError) as err:
                    _LOGGER.debug(f"Counters API returned invalid data for {location_id}: {err}")
                    location_data["counters"] = None
                except Exception as err:
                    _LOGGER.debug(f"Error fetching counters for {location_id}: {err}")
                    location_data["counters"] = None

                locations_data[location_id] = location_data

            # Build summary
            summary = {
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

    async def _fetch_pending_payments(self, location_id: str) -> dict[str, Any]:
        """Fetch pending payments for a specific location."""
        url = API_PENDING_PAYMENTS.format(location_id=location_id)
        async with self._session.get(url, cookies=self._cookies) as response:
            if response.status == 200:
                return await response.json()
            else:
                raise Exception(f"Failed to fetch pending payments: {response.status}")

    async def _fetch_receipt(self, location_id: str, month: int | None = None, year: int | None = None) -> dict[str, Any]:
        """Fetch receipt for a specific location and month.
        
        NOTE: This API currently returns 403 Forbidden. Disabled in get_data().
        Payment history API provides the same data with better reliability.
        
        Args:
            location_id: Location ID
            month: Month number (1-12). If None, fetches current month.
            year: Year (YYYY). If None, fetches current year.
            
        Returns:
            Receipt data with detailed breakdown of charges.
        """
        from .const import API_RECEIPT, API_RECEIPT_MONTH
        
        if month and year:
            url = API_RECEIPT_MONTH.format(location_id=location_id, month=month, year=year)
        else:
            url = API_RECEIPT.format(location_id=location_id)
        
        async with self._session.get(url, cookies=self._cookies) as response:
            if response.status == 200:
                return await response.json()
            else:
                raise Exception(f"Failed to fetch receipt: {response.status}")

    async def _fetch_payment_history(self, location_id: str) -> dict[str, Any]:
        """Fetch payment history for a specific location.
        
        Returns detailed payment history with breakdown of all charges.
        """
        url = API_PAYMENTS_HISTORY.format(location_id=location_id)
        async with self._session.get(url, cookies=self._cookies) as response:
            if response.status == 200:
                return await response.json()
            else:
                raise Exception(f"Failed to fetch payment history: {response.status}")

    async def _fetch_counters(self, location_id: str) -> dict[str, Any]:
        """Fetch counter readings for a specific location."""
        url = API_COUNTERS.format(location_id=location_id)
        async with self._session.get(url, cookies=self._cookies) as response:
            if response.status == 200:
                return await response.json()
            else:
                raise Exception(f"Failed to fetch counters: {response.status}")

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
        if not self._authenticated:
            await self.authenticate()
        
        # Use the main get_data method which fetches pending payments
        data = await self.get_data()
        return data.get("summary", {})

    async def get_payment_history(self, location_id: str | None = None) -> list[dict[str, Any]]:
        """Get payment history for all locations or a specific location.
        
        Args:
            location_id: Optional location ID. If None, returns history for all locations.
            
        Returns:
            List of payment records with details.
        """
        if not self._authenticated:
            await self.authenticate()
        
        if not self._location_ids:
            self._location_ids = await self._extract_location_ids()
        
        all_payments = []
        location_ids = [location_id] if location_id else self._location_ids
        
        for loc_id in location_ids:
            try:
                history = await self._fetch_payment_history(loc_id)
                if history.get("results"):
                    # Add location_id to each payment for identification
                    for payment in history["results"]:
                        payment["location_id"] = loc_id
                        all_payments.append(payment)
            except Exception as err:
                _LOGGER.error(f"Error fetching payment history for {loc_id}: {err}")
        
        # Sort by date (most recent first)
        all_payments.sort(key=lambda x: x.get("date", ""), reverse=True)
        return all_payments

    async def get_locations(self) -> list[str]:
        """Get list of location IDs for this account."""
        if not self._authenticated:
            await self.authenticate()
        
        if not self._location_ids:
            self._location_ids = await self._extract_location_ids()
        
        return self._location_ids
