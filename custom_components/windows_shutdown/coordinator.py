"""Data-update-coordinator voor de Windows Shutdown-integratie."""

from __future__ import annotations

import asyncio
import json as _json
import logging
import time
from datetime import timedelta
from typing import Any

import aiohttp

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    DEFAULT_SHUTDOWN_TYPE,
    DEFAULT_TIMEOUT,
    DEVICE_MANUFACTURER,
    DEVICE_MODEL,
    DOMAIN,
    POLL_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

# Minimale tijd (seconden) tussen twee shutdown-opdrachten
_SHUTDOWN_COOLDOWN = 5


class WindowsShutdownCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """
    Coördinator die periodiek de status van de Windows-client ophaalt.

    Gooit nooit UpdateFailed zodat entiteiten nooit 'unavailable' worden.
    Bij een authenticatiefout (401/403) wordt automatisch de reauth-flow gestart.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        host: str,
        port: int,
        api_key: str,
        config_entry: ConfigEntry,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{host}",
            update_interval=timedelta(seconds=POLL_INTERVAL),
            config_entry=config_entry,
        )
        self.host = host
        self.port = port
        self._api_key = api_key
        self.base_url = f"http://{host}:{port}"
        self._session = async_get_clientsession(hass)
        self._timeout = aiohttp.ClientTimeout(total=DEFAULT_TIMEOUT)
        self._last_success: float = 0.0
        self._last_shutdown: float = 0.0

    @property
    def device_info(self) -> DeviceInfo:
        """DeviceInfo voor alle entiteiten van dit apparaat."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.config_entry.entry_id)},
            name=self.config_entry.title,
            manufacturer=DEVICE_MANUFACTURER,
            model=DEVICE_MODEL,
            configuration_url=f"http://{self.host}:{self.port}/status",
        )

    # ------------------------------------------------------------------
    # Gedeelde HTTP-helper
    # ------------------------------------------------------------------
    async def _async_request(
        self,
        method: str,
        path: str,
        *,
        auth: bool = False,
        json: dict[str, Any] | None = None,
    ) -> tuple[int, bytes] | None:
        """
        Voer een HTTP-verzoek uit naar de client.

        Geeft (status_code, body_bytes) terug, of None bij een verbindingsfout.
        """
        url = f"{self.base_url}{path}"
        headers = {"X-API-Key": self._api_key} if auth else {}
        try:
            async with self._session.request(
                method,
                url,
                headers=headers,
                json=json,
                timeout=self._timeout,
            ) as resp:
                body = await resp.read()
                return resp.status, body
        except (aiohttp.ClientError, asyncio.TimeoutError, OSError) as err:
            _LOGGER.debug("HTTP %s %s mislukt: %s", method.upper(), url, err)
            return None

    # ------------------------------------------------------------------
    # Status update
    # ------------------------------------------------------------------
    async def _async_update_data(self) -> dict[str, Any]:
        """Haal de status op van de Windows-client."""
        result = await self._async_request("get", "/status")

        if result is not None:
            status, body = result
            if status == 200:
                try:
                    payload = _json.loads(body)
                except (_json.JSONDecodeError, ValueError):
                    payload = {}
                self._last_success = time.monotonic()
                return {"online": True, **payload}
            elif status in (401, 403):
                _LOGGER.warning(
                    "Authenticatiefout bij statuscheck voor %s: HTTP %d - reauth gestart",
                    self.host, status,
                )
                raise ConfigEntryAuthFailed(
                    translation_domain=DOMAIN,
                    translation_key="auth_failed",
                    translation_placeholders={
                        "host": self.host,
                        "status": str(status),
                    },
                )
            else:
                _LOGGER.warning(
                    "Onverwachte HTTP-status van %s bij statuscheck: %d",
                    self.host, status,
                )

        # Grace period om flapping te voorkomen
        if time.monotonic() - self._last_success < 30:
            return {"online": True}

        return {"online": False}

    # ------------------------------------------------------------------
    # Shutdown acties
    # ------------------------------------------------------------------
    async def async_send_shutdown(
        self,
        *,
        delay: int | None = None,
        shutdown_type: str | None = None,
    ) -> bool:
        """Stuur een shutdown-opdracht naar de client."""
        now = time.monotonic()

        # Weiger shutdown als de entry niet in geladen staat is.
        # Dit onderschept aanroepen tijdens reload, reconfigure en reauth —
        # HA's DataUpdateCoordinator registreert intern async_on_unload-callbacks
        # die anders onze shutdown-methode zouden aanroepen.
        if (
            self.config_entry is None
            or self.config_entry.state is not ConfigEntryState.LOADED
        ):
            _LOGGER.warning(
                "Shutdown geweigerd voor %s: entry staat niet in LOADED-staat (state=%s)",
                self.host,
                self.config_entry.state if self.config_entry else "None",
            )
            return False

        elapsed = now - self._last_shutdown
        if self._last_shutdown > 0 and elapsed < _SHUTDOWN_COOLDOWN:
            _LOGGER.warning(
                "Shutdown geweigerd voor %s: vorige opdracht was %.1fs geleden (cooldown: %ds)",
                self.host, elapsed, _SHUTDOWN_COOLDOWN,
            )
            return False

        payload: dict[str, Any] = {}
        if delay is not None:
            payload["delay"] = int(delay)
        if shutdown_type is not None:
            payload["type"] = shutdown_type

        _LOGGER.debug("Stuur shutdown payload naar %s: %s", self.host, payload)

        result = await self._async_request("post", "/shutdown", auth=True, json=payload)
        if result is None:
            _LOGGER.error("Shutdown request mislukt voor %s: verbindingsfout", self.host)
            return False

        status, body = result
        if status == 200:
            self._last_shutdown = time.monotonic()
            _LOGGER.info(
                "Shutdown succesvol gestuurd naar %s (type=%s, delay=%s)",
                self.host,
                shutdown_type or DEFAULT_SHUTDOWN_TYPE,
                delay,
            )
            return True

        error_text = body.decode(errors="replace")[:300]
        _LOGGER.error("Shutdown mislukt voor %s: HTTP %d - %s", self.host, status, error_text)
        return False

    # ------------------------------------------------------------------
    # Notificatie
    # ------------------------------------------------------------------
    async def async_notify(
        self,
        *,
        title: str,
        message: str,
    ) -> bool:
        """Stuur een notificatie naar de Windows-client (POST /notify)."""
        if (
            self.config_entry is None
            or self.config_entry.state is not ConfigEntryState.LOADED
        ):
            _LOGGER.warning(
                "Notificatie geweigerd voor %s: entry staat niet in LOADED-staat",
                self.host,
            )
            return False
        payload: dict[str, Any] = {
            "title": title,
            "message": message,
        }

        _LOGGER.debug("Stuur notificatie naar %s: %s", self.host, payload)

        result = await self._async_request("post", "/notify", auth=True, json=payload)
        if result is None:
            _LOGGER.error(
                "Notificatie mislukt voor %s: verbindingsfout", self.host
            )
            return False

        status, body = result
        if status == 200:
            _LOGGER.info("Notificatie succesvol verstuurd naar %s", self.host)
            return True

        error_text = body.decode(errors="replace")[:300]
        _LOGGER.error(
            "Notificatie mislukt voor %s: HTTP %d - %s", self.host, status, error_text
        )
        return False

