"""Diagnostics voor de Windows Shutdown-integratie."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.redact import async_redact_data

from .const import CONF_API_KEY

# Velden die gevoelige informatie bevatten en niet gedeeld mogen worden
TO_REDACT = {CONF_API_KEY}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> dict[str, Any]:
    """Geef diagnostische informatie terug voor een config-entry."""
    coordinator = entry.runtime_data

    return {
        "entry": {
            "title": entry.title,
            "version": entry.version,
            "data": async_redact_data(entry.data, TO_REDACT),
            "options": entry.options,
        },
        "coordinator": {
            "host": coordinator.host,
            "port": coordinator.port,
            "last_update_success": coordinator.last_update_success,
            "data": coordinator.data,
        },
    }
