"""Home Assistant-integratie: Windows Shutdown."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv

from .const import (
    CONF_API_KEY,
    CONF_DELAY,
    CONF_SHUTDOWN_TYPE,
    DOMAIN,
    SHUTDOWN_TYPES,
)
from .coordinator import WindowsShutdownCoordinator

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.BUTTON]

_SHUTDOWN_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_DELAY): vol.All(vol.Coerce(int), vol.Range(min=0, max=3600)),
        vol.Optional(CONF_SHUTDOWN_TYPE): vol.In(SHUTDOWN_TYPES),
        vol.Optional("entry_id"): cv.string,
    }
)

_NOTIFY_SCHEMA = vol.Schema(
    {
        vol.Optional("title"): cv.string,
        vol.Required("message"): cv.string,
        vol.Optional("entry_id"): cv.string,
    }
)


def _get_targets(
    hass: HomeAssistant,
    target_entry_id: str | None,
) -> list[WindowsShutdownCoordinator]:
    """Geef de lijst van te bereiken coordinators terug, of gooi een fout."""
    if target_entry_id:
        entry = hass.config_entries.async_get_entry(target_entry_id)
        if entry is None or entry.domain != DOMAIN:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="unknown_entry_id",
                translation_placeholders={"entry_id": target_entry_id},
            )
        if entry.state is not ConfigEntryState.LOADED:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="entry_not_loaded",
                translation_placeholders={"title": entry.title},
            )
        return [entry.runtime_data]

    return [
        e.runtime_data
        for e in hass.config_entries.async_entries(DOMAIN)
        if e.state is ConfigEntryState.LOADED
    ]


def _register_services(hass: HomeAssistant) -> None:
    """Registreer domain-brede services (éénmalig bij eerste entry)."""

    async def handle_shutdown(call: ServiceCall) -> None:
        """Service call voor shutdown via HA services."""
        for coordinator in _get_targets(hass, call.data.get("entry_id")):
            await coordinator.async_send_shutdown(
                delay=call.data.get(CONF_DELAY),
                shutdown_type=call.data.get(CONF_SHUTDOWN_TYPE),
            )

    async def handle_notify(call: ServiceCall) -> None:
        """Service call om een notificatie te sturen naar de Windows-client."""
        for coordinator in _get_targets(hass, call.data.get("entry_id")):
            await coordinator.async_notify(
                title=call.data.get("title", "Home Assistant"),
                message=call.data["message"],
            )

    hass.services.async_register(
        DOMAIN, "shutdown", handle_shutdown, schema=_SHUTDOWN_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, "notify", handle_notify, schema=_NOTIFY_SCHEMA
    )


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Stel een config-entry in en start de coordinator."""
    coordinator = WindowsShutdownCoordinator(
        hass=hass,
        host=entry.data[CONF_HOST],
        port=entry.data[CONF_PORT],
        api_key=entry.data[CONF_API_KEY],
        config_entry=entry,
    )

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Registreer services de eerste keer dat een entry wordt geladen
    if not hass.services.has_service(DOMAIN, "shutdown"):
        _register_services(hass)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Verwijder een config-entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    # Verwijder services wanneer er geen geladen entries meer zijn.
    # Op dit punt is de huidige entry al UNLOADING (niet LOADED),
    # dus de check op LOADED sluit haar correct uit.
    if unload_ok and not any(
        e.state is ConfigEntryState.LOADED
        for e in hass.config_entries.async_entries(DOMAIN)
    ):
        hass.services.async_remove(DOMAIN, "shutdown")
        hass.services.async_remove(DOMAIN, "notify")

    return unload_ok
