"""The Adminis Locuințe integration.

Copyright (c) 2026 Emanuel Besliu
Licensed under the MIT License

This integration was developed through reverse engineering of the
adminislocuinte.ro platform and is not affiliated with or endorsed
by Adminis Locuinte.
"""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from .api import AdminisLocuinteAPI
from .const import DOMAIN
from .coordinator import AdminisLocuinteDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Adminis Locuințe from a config entry."""
    api = AdminisLocuinteAPI(
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
    )

    # Create the dedicated aiohttp session with its own cookie jar
    await api.async_init()

    try:
        authenticated = await api.authenticate()
        if not authenticated:
            await api.async_close()
            raise ConfigEntryAuthFailed(
                "Authentication failed. Please reconfigure with valid credentials."
            )
    except ConfigEntryAuthFailed:
        raise
    except Exception as err:
        await api.async_close()
        _LOGGER.error("Failed to authenticate with Adminis Locuințe: %s", err)
        raise ConfigEntryNotReady from err

    coordinator = AdminisLocuinteDataUpdateCoordinator(hass, entry, api)

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "api": api,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        data = hass.data[DOMAIN].pop(entry.entry_id)
        api: AdminisLocuinteAPI = data["api"]
        await api.async_close()

    return unload_ok
