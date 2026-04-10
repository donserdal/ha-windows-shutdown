"""Knop-entiteit om de Windows-computer af te sluiten."""

from __future__ import annotations

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_DELAY,
    CONF_SHUTDOWN_TYPE,
    DEFAULT_DELAY,
    DEFAULT_SHUTDOWN_TYPE,
    DEVICE_MANUFACTURER,
    DEVICE_MODEL,
    DOMAIN,
)
from .coordinator import WindowsShutdownCoordinator

_LOGGER = logging.getLogger(__name__)

# Maximaal 1 gelijktijdig verzoek per platform-entiteit
PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Maak de knop-entiteit aan voor een config-entry."""
    coordinator: WindowsShutdownCoordinator = entry.runtime_data
    async_add_entities([WindowsShutdownButton(coordinator, entry)])


class WindowsShutdownButton(
    CoordinatorEntity[WindowsShutdownCoordinator], ButtonEntity
):
    """Knop om de Windows-client af te sluiten."""

    _attr_has_entity_name = True
    _attr_translation_key = "shutdown"
    _attr_icon = "mdi:power"

    def __init__(
        self,
        coordinator: WindowsShutdownCoordinator,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_shutdown"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer=DEVICE_MANUFACTURER,
            model=DEVICE_MODEL,
            configuration_url=f"http://{entry.data[CONF_HOST]}:{entry.data[CONF_PORT]}/status",
        )

    @property
    def available(self) -> bool:
        """De knop is beschikbaar zolang de PC online is."""
        return bool((self.coordinator.data or {}).get("online", False))

    async def async_press(self) -> None:
        """Stuur de afsluit-opdracht naar de Windows-client."""
        _LOGGER.debug("Shutdown-knop ingedrukt voor %s", self.coordinator.host)

        options = self.coordinator.config_entry.options

        delay = int(options.get(CONF_DELAY, DEFAULT_DELAY))
        shutdown_type = options.get(CONF_SHUTDOWN_TYPE, DEFAULT_SHUTDOWN_TYPE)

        _LOGGER.debug(
            "Uitvoeren shutdown: host=%s, type=%s, delay=%s",
            self.coordinator.host, shutdown_type, delay,
        )

        success = await self.coordinator.async_shutdown(
            delay=delay,
            shutdown_type=shutdown_type,
        )

        if not success:
            raise HomeAssistantError(
                f"Kon shutdown niet versturen naar {self.coordinator.host}. "
                "Controleer de logboeken voor details (mogelijk cooldown actief)."
            )
