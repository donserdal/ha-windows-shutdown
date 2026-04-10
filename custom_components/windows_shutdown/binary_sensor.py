"""Binaire sensor: geeft aan of de Windows-client online is."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEVICE_MANUFACTURER, DEVICE_MODEL, DOMAIN
from .coordinator import WindowsShutdownCoordinator

# Maximaal 1 gelijktijdig polling-verzoek per platform
PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Maak de binaire sensor aan voor een config-entry."""
    coordinator: WindowsShutdownCoordinator = entry.runtime_data
    async_add_entities([WindowsOnlineSensor(coordinator, entry)])


class WindowsOnlineSensor(
    CoordinatorEntity[WindowsShutdownCoordinator], BinarySensorEntity
):
    """
    Binaire sensor die aangeeft of de Windows-client online is.

    De sensor is NOOIT 'niet beschikbaar' (unavailable):
    - als de client bereikbaar is → aan (True)
    - als de client niet bereikbaar is → uit (False)
    """

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_has_entity_name = True
    _attr_translation_key = "online"

    def __init__(
        self,
        coordinator: WindowsShutdownCoordinator,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_online"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer=DEVICE_MANUFACTURER,
            model=DEVICE_MODEL,
            configuration_url=f"http://{entry.data[CONF_HOST]}:{entry.data[CONF_PORT]}/status",
        )

    @property
    def is_on(self) -> bool:
        """Geeft True terug als de Windows-client bereikbaar is."""
        data = self.coordinator.data or {}
        return bool(data.get("online", False))

    @property
    def available(self) -> bool:
        """
        Altijd True: we maken de entiteit nooit onbeschikbaar,
        ook niet als de client offline is.
        """
        return True

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Extra status-attributen vanuit de client."""
        data = self.coordinator.data or {}
        attrs: dict[str, Any] = {}
        if data.get("hostname"):
            attrs["hostname"] = data["hostname"]
        if data.get("version"):
            attrs["client_version"] = data["version"]
        if data.get("uptime"):
            attrs["uptime"] = str(data["uptime"])
        return attrs
