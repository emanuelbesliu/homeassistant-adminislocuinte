"""Sensor platform for Adminis Locuințe integration.

Copyright (c) 2026 Emanuel Besliu
Licensed under the MIT License
"""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CURRENCY_EURO
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Adminis Locuințe sensors based on a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    # Global sensors
    sensors = [
        AdminisLocuinteLocationCountSensor(coordinator, entry),
        AdminisLocuinteTotalPendingSensor(coordinator, entry),
        AdminisLocuinteLastPaymentAmountSensor(coordinator, entry),
        AdminisLocuinteLastPaymentDateSensor(coordinator, entry),
    ]
    
    # Per-location sensors - dynamically added based on available locations
    if coordinator.data and "locations" in coordinator.data:
        for location_id, location_data in coordinator.data["locations"].items():
            # Get location name for friendly sensor names
            location_name = "Unknown"
            if "info" in location_data:
                info = location_data["info"]
                if "apartment" in info:
                    location_name = info["apartment"]
                elif "name" in info:
                    # Extract apartment/parking from full name
                    name_parts = info["name"].split(", ap. ")
                    if len(name_parts) > 1:
                        location_name = name_parts[1].split(",")[0]
            
            # Add 3 sensors per location
            sensors.extend([
                AdminisLocuinteLocationMonthlyBillSensor(coordinator, entry, location_id, location_name),
                AdminisLocuinteLocationPendingSensor(coordinator, entry, location_id, location_name),
                AdminisLocuinteLocationLastPaymentSensor(coordinator, entry, location_id, location_name),
            ])

    async_add_entities(sensors)


class AdminisLocuinteBaseSensor(CoordinatorEntity, SensorEntity):
    """Base class for Adminis Locuințe sensors."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        entry: ConfigEntry,
        sensor_type: str,
        name: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_{sensor_type}"
        self._attr_name = f"Adminis Locuințe {name}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "Adminis Locuințe",
            "manufacturer": "Adminis Locuințe",
            "model": "Apartment Management",
        }


class AdminisLocuinteLocationCountSensor(AdminisLocuinteBaseSensor):
    """Sensor for number of locations."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "location_count", "Location Count")
        self._attr_icon = "mdi:home-group"

    @property
    def native_value(self) -> int | None:
        """Return the state of the sensor."""
        if self.coordinator.data and "summary" in self.coordinator.data:
            return self.coordinator.data["summary"].get("location_count")
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        attrs = {}
        if self.coordinator.data and "locations" in self.coordinator.data:
            locations = self.coordinator.data["locations"]
            attrs["location_ids"] = list(locations.keys())
        return attrs


class AdminisLocuinteTotalPendingSensor(AdminisLocuinteBaseSensor):
    """Sensor for total pending payments across all locations."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "total_pending", "Total Pending")
        self._attr_device_class = SensorDeviceClass.MONETARY
        self._attr_state_class = SensorStateClass.TOTAL
        self._attr_native_unit_of_measurement = "RON"
        self._attr_icon = "mdi:cash-multiple"

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        if self.coordinator.data and "summary" in self.coordinator.data:
            return self.coordinator.data["summary"].get("total_pending")
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes with per-location breakdown."""
        attrs = {}
        if self.coordinator.data and "locations" in self.coordinator.data:
            locations = self.coordinator.data["locations"]
            for loc_id, loc_data in locations.items():
                if loc_data.get("pending_payments"):
                    payment_info = loc_data["pending_payments"]
                    attrs[f"location_{loc_id}_status"] = "ok" if payment_info.get("error") == 0 else "error"
                    attrs[f"location_{loc_id}_allow_payments"] = payment_info.get("allowPayments")
        return attrs


class AdminisLocuinteLastPaymentAmountSensor(AdminisLocuinteBaseSensor):
    """Sensor for last payment amount."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "last_payment_amount", "Last Payment Amount")
        self._attr_device_class = SensorDeviceClass.MONETARY
        self._attr_state_class = SensorStateClass.TOTAL
        self._attr_native_unit_of_measurement = "RON"
        self._attr_icon = "mdi:receipt"

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        if self.coordinator.data and "summary" in self.coordinator.data:
            return self.coordinator.data["summary"].get("last_payment_amount")
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes with payment details."""
        attrs = {}
        if self.coordinator.data and "summary" in self.coordinator.data:
            summary = self.coordinator.data["summary"]
            attrs["date"] = summary.get("last_payment_date")
            attrs["location_id"] = summary.get("last_payment_location_id")
            
            # Add breakdown from payment history if available
            if "locations" in self.coordinator.data:
                loc_id = summary.get("last_payment_location_id")
                if loc_id and loc_id in self.coordinator.data["locations"]:
                    loc_data = self.coordinator.data["locations"][loc_id]
                    if loc_data.get("payment_history") and loc_data["payment_history"].get("results"):
                        latest = loc_data["payment_history"]["results"][0]
                        if latest.get("details"):
                            # Group charges by category
                            breakdown = {}
                            for detail in latest["details"]:
                                name = detail.get("name", "Unknown")
                                amount = detail.get("amount", 0)
                                breakdown[name] = amount
                            attrs["breakdown"] = breakdown
        return attrs


class AdminisLocuinteLastPaymentDateSensor(AdminisLocuinteBaseSensor):
    """Sensor for last payment date."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "last_payment_date", "Last Payment Date")
        self._attr_device_class = None  # Date sensors don't have a standard device class for formatted dates
        self._attr_icon = "mdi:calendar-check"

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        if self.coordinator.data and "summary" in self.coordinator.data:
            return self.coordinator.data["summary"].get("last_payment_date")
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        attrs = {}
        if self.coordinator.data and "summary" in self.coordinator.data:
            summary = self.coordinator.data["summary"]
            attrs["amount"] = summary.get("last_payment_amount")
            attrs["location_id"] = summary.get("last_payment_location_id")
        return attrs


class AdminisLocuinteLocationMonthlyBillSensor(AdminisLocuinteBaseSensor):
    """Sensor for monthly bill of a specific location."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        entry: ConfigEntry,
        location_id: str,
        location_name: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(
            coordinator,
            entry,
            f"monthly_bill_{location_id}",
            f"{location_name} Monthly Bill",
        )
        self._location_id = location_id
        self._attr_device_class = SensorDeviceClass.MONETARY
        self._attr_state_class = SensorStateClass.TOTAL
        self._attr_native_unit_of_measurement = "RON"
        self._attr_icon = "mdi:file-document"

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        if self.coordinator.data and "locations" in self.coordinator.data:
            location_data = self.coordinator.data["locations"].get(self._location_id)
            if location_data and "payment_history" in location_data:
                history = location_data["payment_history"]
                if history and history.get("results") and len(history["results"]) > 0:
                    latest = history["results"][0]
                    amount_str = latest.get("amount", "0")
                    try:
                        return float(amount_str)
                    except (ValueError, TypeError):
                        return None
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes with bill breakdown."""
        attrs = {}
        if self.coordinator.data and "locations" in self.coordinator.data:
            location_data = self.coordinator.data["locations"].get(self._location_id)
            
            # Add location info
            if location_data and "info" in location_data:
                info = location_data["info"]
                attrs["location_name"] = info.get("name", "Unknown")
                attrs["location_type"] = info.get("type", "unknown")
                attrs["apartment"] = info.get("apartment", "N/A")
            
            # Add latest bill details
            if location_data and "payment_history" in location_data:
                history = location_data["payment_history"]
                if history and history.get("results") and len(history["results"]) > 0:
                    latest = history["results"][0]
                    attrs["date"] = latest.get("date", "")
                    attrs["receipt"] = latest.get("receipt", "")
                    
                    # Add breakdown
                    if latest.get("details"):
                        breakdown = {}
                        for detail in latest["details"]:
                            name = detail.get("name", "Unknown")
                            amount = detail.get("amount", 0)
                            breakdown[name] = amount
                        attrs["breakdown"] = breakdown
        return attrs


class AdminisLocuinteLocationPendingSensor(AdminisLocuinteBaseSensor):
    """Sensor for pending payments of a specific location."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        entry: ConfigEntry,
        location_id: str,
        location_name: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(
            coordinator,
            entry,
            f"pending_{location_id}",
            f"{location_name} Pending",
        )
        self._location_id = location_id
        self._attr_device_class = SensorDeviceClass.MONETARY
        self._attr_state_class = SensorStateClass.TOTAL
        self._attr_native_unit_of_measurement = "RON"
        self._attr_icon = "mdi:cash-clock"

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        if self.coordinator.data and "locations" in self.coordinator.data:
            location_data = self.coordinator.data["locations"].get(self._location_id)
            if location_data and "pending_payments" in location_data:
                pending = location_data["pending_payments"]
                if pending and pending.get("results"):
                    # Calculate total pending from owner and association
                    # Currently API returns null for all values
                    results = pending["results"]
                    total = 0.0
                    if results.get("owner"):
                        # TODO: Parse owner pending when API returns data
                        pass
                    if results.get("assoc"):
                        # TODO: Parse association pending when API returns data
                        pass
                    return total
        return 0.0  # Default to 0 when no pending

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        attrs = {}
        if self.coordinator.data and "locations" in self.coordinator.data:
            location_data = self.coordinator.data["locations"].get(self._location_id)
            
            # Add location info
            if location_data and "info" in location_data:
                info = location_data["info"]
                attrs["location_name"] = info.get("name", "Unknown")
                attrs["location_type"] = info.get("type", "unknown")
            
            # Add pending payment details
            if location_data and "pending_payments" in location_data:
                pending = location_data["pending_payments"]
                if pending:
                    attrs["allow_payments"] = pending.get("allowPayments", False)
                    attrs["error_code"] = pending.get("error", 0)
        return attrs


class AdminisLocuinteLocationLastPaymentSensor(AdminisLocuinteBaseSensor):
    """Sensor for last payment of a specific location."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        entry: ConfigEntry,
        location_id: str,
        location_name: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(
            coordinator,
            entry,
            f"last_payment_{location_id}",
            f"{location_name} Last Payment",
        )
        self._location_id = location_id
        self._attr_device_class = SensorDeviceClass.MONETARY
        self._attr_state_class = SensorStateClass.TOTAL
        self._attr_native_unit_of_measurement = "RON"
        self._attr_icon = "mdi:receipt-text-check"

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        if self.coordinator.data and "locations" in self.coordinator.data:
            location_data = self.coordinator.data["locations"].get(self._location_id)
            if location_data and "payment_history" in location_data:
                history = location_data["payment_history"]
                if history and history.get("results") and len(history["results"]) > 0:
                    latest = history["results"][0]
                    amount_str = latest.get("amount", "0")
                    try:
                        return float(amount_str)
                    except (ValueError, TypeError):
                        return None
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        attrs = {}
        if self.coordinator.data and "locations" in self.coordinator.data:
            location_data = self.coordinator.data["locations"].get(self._location_id)
            
            # Add location info
            if location_data and "info" in location_data:
                info = location_data["info"]
                attrs["location_name"] = info.get("name", "Unknown")
                attrs["location_type"] = info.get("type", "unknown")
            
            # Add last payment details
            if location_data and "payment_history" in location_data:
                history = location_data["payment_history"]
                if history and history.get("results") and len(history["results"]) > 0:
                    latest = history["results"][0]
                    attrs["date"] = latest.get("date", "")
                    attrs["receipt"] = latest.get("receipt", "")
                    attrs["payment_count"] = len(history["results"])
        return attrs


# TODO: Add more sensor classes when needed:
# 
# class AdminisLocuinteLocationPendingSensor(AdminisLocuinteBaseSensor):
#     """Sensor for pending payments of a specific location."""
#     def __init__(self, coordinator, entry, location_id):
#         super().__init__(coordinator, entry, f"pending_{location_id}", f"Pending {location_id}")
#         self._location_id = location_id
#         self._attr_device_class = SensorDeviceClass.MONETARY
#         self._attr_native_unit_of_measurement = "RON"
#
# class AdminisLocuinteCounterSensor(AdminisLocuinteBaseSensor):
#     """Sensor for counter readings."""
#     def __init__(self, coordinator, entry, counter_type):
#         super().__init__(coordinator, entry, f"counter_{counter_type}", f"Counter {counter_type}")
#         self._counter_type = counter_type
#         self._attr_state_class = SensorStateClass.TOTAL_INCREASING
#
# class AdminisLocuinteWaterConsumptionSensor(AdminisLocuinteBaseSensor):
#     """Sensor for water consumption."""
#     def __init__(self, coordinator, entry):
#         super().__init__(coordinator, entry, "water_consumption", "Water Consumption")
#         self._attr_device_class = SensorDeviceClass.WATER
#         self._attr_state_class = SensorStateClass.TOTAL_INCREASING
#         self._attr_native_unit_of_measurement = "L"
#         self._attr_icon = "mdi:water"

