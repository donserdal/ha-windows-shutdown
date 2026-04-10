"""Home Assistant-integratie: Windows Shutdown."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError

from .const import (
    CONF_API_KEY,
    DOMAIN,
)
from .coordinator import WindowsShutdownCoordinator

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.BUTTON]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Setup domain (één keer voor de hele integratie)."""

    async def handle_shutdown(call: ServiceCall) -> None:
        """Service call voor shutdown via HA services."""
        delay = call.data.get("delay")
        shutdown_type = call.data.get("shutdown_type")
        target_entry_id = call.data.get("entry_id")

        if target_entry_id:
            entry = hass.config_entries.async_get_entry(target_entry_id)
            if entry is None or entry.domain != DOMAIN:
                raise ServiceValidationError(
                    f"Onbekend entry_id opgegeven in service-aanroep: {target_entry_id}"
                )
            if entry.state is not ConfigEntryState.LOADED:
                raise ServiceValidationError(
                    f"Apparaat '{entry.title}' is momenteel niet geladen."
                )
            targets = [entry.runtime_data]
        else:
            targets = [
                e.runtime_data
                for e in hass.config_entries.async_entries(DOMAIN)
                if e.state is ConfigEntryState.LOADED
            ]

        for coordinator in targets:
            await coordinator.async_shutdown(
                delay=delay,
                shutdown_type=shutdown_type,
            )

    hass.services.async_register(DOMAIN, "shutdown", handle_shutdown)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Stel een config-entry in en start de coordinator."""
    coordinator = WindowsShutdownCoordinator(
        hass=hass,
        host=entry.data[CONF_HOST],
        port=entry.data[CONF_PORT],
        api_key=entry.data[CONF_API_KEY],
    )

    # Eerste status poll
    await coordinator.async_config_entry_first_refresh()

    # Sla coordinator op via het moderne runtime_data patroon
    entry.runtime_data = coordinator

    # Laad de platforms (binary_sensor + button)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Verwijder een config-entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
