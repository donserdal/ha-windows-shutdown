"""Config-flow voor de Windows Shutdown-integratie."""

from __future__ import annotations

import asyncio
import logging
import socket
import threading
from typing import Any

import aiohttp
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import zeroconf as zc_component
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import (
    CONF_API_KEY,
    CONF_DELAY,
    CONF_SHUTDOWN_TYPE,
    DEFAULT_DELAY,
    DEFAULT_PORT,
    DEFAULT_SHUTDOWN_TYPE,
    DEFAULT_TIMEOUT,
    DOMAIN,
    SERVICE_TYPE,
    SHUTDOWN_TYPES,
)

_LOGGER = logging.getLogger(__name__)

_OPT_MANUAL = "__manual__"


class WindowsShutdownConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config-flow met automatische ontdekking via mDNS of handmatige invoer."""

    VERSION = 1
    MINOR_VERSION = 1

    def __init__(self) -> None:
        self._discovered: dict[str, dict[str, Any]] = {}
        self._host: str | None = None
        self._port: int = DEFAULT_PORT
        self._name: str | None = None
        self._timeout = aiohttp.ClientTimeout(total=DEFAULT_TIMEOUT)

    # ------------------------------------------------------------------
    # Stap 0 – Startmenu
    # ------------------------------------------------------------------
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Toon het startmenu."""
        return self.async_show_menu(
            step_id="user",
            menu_options=["discover", "manual"],
        )

    # ------------------------------------------------------------------
    # Stap 1a – Automatisch ontdekken via mDNS
    # ------------------------------------------------------------------
    async def async_step_discover(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Scan het netwerk op HA-Shutdown-clients via mDNS."""

        if user_input is not None:
            key = user_input["device"]
            if key == _OPT_MANUAL:
                return await self.async_step_manual()
            device = self._discovered[key]
            self._host = device["host"]
            self._port = device["port"]
            self._name = device["name"]
            return await self.async_step_credentials()

        # Scan uitvoeren
        self._discovered = await self._async_scan_mdns()

        if not self._discovered:
            return await self.async_step_manual(errors={"base": "no_devices_found"})

        choices: dict[str, str] = {
            key: f"{dev['name']}  ({dev['host']}:{dev['port']})"
            for key, dev in self._discovered.items()
        }
        choices[_OPT_MANUAL] = "Enter manually…"

        return self.async_show_form(
            step_id="discover",
            data_schema=vol.Schema(
                {
                    vol.Required("device"): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                SelectOptionDict(value=k, label=v)
                                for k, v in choices.items()
                            ],
                            mode=SelectSelectorMode.LIST,
                        )
                    )
                }
            ),
            description_placeholders={"count": str(len(self._discovered))},
        )

    async def _async_scan_mdns(self) -> dict[str, dict[str, Any]]:
        """Gebruik Zeroconf om _ha-shutdown._tcp.local.-services te zoeken."""
        from zeroconf import ServiceBrowser, ServiceStateChange

        results: dict[str, dict[str, Any]] = {}
        lock = threading.Lock()

        def on_change(zeroconf_obj, service_type, name, state_change):
            if state_change is not ServiceStateChange.Added:
                return
            try:
                info = zeroconf_obj.get_service_info(service_type, name)
                if not info or not info.addresses:
                    return
                host = socket.inet_ntoa(info.addresses[0])
                props = info.properties or {}

                def _decode(val):
                    return val.decode("utf-8", errors="replace") if isinstance(val, bytes) else (val or "")

                hostname = _decode(props.get(b"hostname")) or name.split(".")[0]
                hostname = hostname.removesuffix(".local")
                key = f"{host}:{info.port}"
                with lock:
                    results[key] = {"name": hostname, "host": host, "port": info.port}
            except Exception as exc:  # noqa: BLE001
                _LOGGER.debug("Fout bij verwerken mDNS-service %s: %s", name, exc)

        try:
            ha_zc = await zc_component.async_get_instance(self.hass)
            browser = ServiceBrowser(ha_zc, SERVICE_TYPE, handlers=[on_change])
            await asyncio.sleep(5)
            await self.hass.async_add_executor_job(browser.cancel)
        except Exception as exc:  # noqa: BLE001
            _LOGGER.debug("mDNS-scan mislukt: %s", exc)

        with lock:
            return dict(results)

    # ------------------------------------------------------------------
    # Stap 1b – Handmatige invoer
    # ------------------------------------------------------------------
    async def async_step_manual(
        self,
        user_input: dict[str, Any] | None = None,
        errors: dict[str, str] | None = None,
    ) -> ConfigFlowResult:
        """Voer host en poort handmatig in."""
        errors = errors or {}

        if user_input is not None:
            self._host = user_input[CONF_HOST].strip()
            try:
                port = int(user_input.get(CONF_PORT, DEFAULT_PORT))
                if not (1 <= port <= 65535):
                    raise ValueError
                self._port = port
            except (TypeError, ValueError):
                errors["base"] = "invalid_port"
                return self.async_show_form(
                    step_id="manual",
                    data_schema=self._manual_schema(),
                    errors=errors,
                )

            self._name = self._host

            ok = await self._async_test_connection(self._host, self._port)
            if not ok:
                errors["base"] = "cannot_connect"
            else:
                return await self.async_step_credentials()

        return self.async_show_form(
            step_id="manual",
            data_schema=self._manual_schema(),
            errors=errors,
        )

    def _manual_schema(self) -> vol.Schema:
        """Bouw het schema voor de handmatige invoerstap."""
        return vol.Schema(
            {
                vol.Required(
                    CONF_HOST,
                    description={"suggested_value": self._host or ""},
                ): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.TEXT)
                ),
                vol.Optional(CONF_PORT, default=self._port): NumberSelector(
                    NumberSelectorConfig(
                        min=1,
                        max=65535,
                        step=1,
                        mode=NumberSelectorMode.BOX,
                    )
                ),
            }
        )

    # ------------------------------------------------------------------
    # Stap 2 – API-sleutel invoeren
    # ------------------------------------------------------------------
    async def async_step_credentials(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Voer de API-sleutel van de Windows-client in."""

        errors: dict[str, str] = {}

        if user_input is not None:
            api_key = user_input[CONF_API_KEY].strip()
            ok = await self._async_test_auth(self._host, self._port, api_key)

            if not ok:
                errors["base"] = "invalid_auth"
            else:
                title = self._name or self._host or "Windows PC"
                await self.async_set_unique_id(f"{self._host}:{self._port}")
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=title,
                    data={
                        CONF_HOST: self._host,
                        CONF_PORT: self._port,
                        CONF_API_KEY: api_key,
                    },
                )

        return self.async_show_form(
            step_id="credentials",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_API_KEY): TextSelector(
                        TextSelectorConfig(type=TextSelectorType.PASSWORD)
                    )
                }
            ),
            description_placeholders={
                "host": str(self._host),
                "port": str(self._port),
            },
            errors=errors,
        )

    # ------------------------------------------------------------------
    # Zeroconf (automatische ontdekking)
    # ------------------------------------------------------------------
    async def async_step_zeroconf(
        self, discovery_info: zc_component.ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Wordt aangeroepen bij mDNS-ontdekking."""
        self._host = discovery_info.host
        self._port = discovery_info.port
        # Strip trailing dot en .local suffix voor een schone apparaatnaam
        raw = discovery_info.hostname.rstrip(".")
        self._name = raw.removesuffix(".local")

        await self.async_set_unique_id(f"{self._host}:{self._port}")
        self._abort_if_unique_id_configured()

        self.context["title_placeholders"] = {"name": self._name}
        return await self.async_step_zeroconf_confirm()

    async def async_step_zeroconf_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Bevestiging voor zeroconf-ontdekte client."""
        if user_input is not None:
            return await self.async_step_credentials()

        return self.async_show_form(
            step_id="zeroconf_confirm",
            description_placeholders={
                "name": self._name,
                "host": self._host,
                "port": str(self._port),
            },
        )

    # ------------------------------------------------------------------
    # Reconfigure Flow – Per device instellingen (Delay + Shutdown Type)
    # ------------------------------------------------------------------
    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Laat de gebruiker per apparaat delay en shutdown_type aanpassen."""
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        if entry is None:
            return self.async_abort(reason="unknown")

        if user_input is not None:
            # Update alleen de options, data (host/port/api_key) blijft hetzelfde
            return self.async_update_reload_and_abort(
                entry,
                data=entry.data,
                options=user_input,
            )

        # Toon formulier met huidige waarden
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_DELAY,
                        default=entry.options.get(CONF_DELAY, DEFAULT_DELAY),
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=0,
                            max=3600,
                            step=1,
                            unit_of_measurement="seconds",
                        )
                    ),
                    vol.Optional(
                        CONF_SHUTDOWN_TYPE,
                        default=entry.options.get(CONF_SHUTDOWN_TYPE, DEFAULT_SHUTDOWN_TYPE),
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                SelectOptionDict(value=o, label=o.capitalize())
                                for o in SHUTDOWN_TYPES
                            ],
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                }
            ),
            description_placeholders={"name": entry.title},
        )

    # ------------------------------------------------------------------
    # Hulpfuncties
    # ------------------------------------------------------------------
    async def _async_test_connection(self, host: str, port: int) -> bool:
        """Controleer of de client bereikbaar is via GET /status."""
        try:
            async with async_get_clientsession(self.hass).get(
                f"http://{host}:{port}/status",
                timeout=self._timeout,
            ) as resp:
                return resp.status == 200
        except (aiohttp.ClientError, asyncio.TimeoutError, OSError):
            return False

    async def _async_test_auth(
        self, host: str, port: int, api_key: str
    ) -> bool:
        """Verifieer de API-sleutel via GET /verify."""
        try:
            async with async_get_clientsession(self.hass).get(
                f"http://{host}:{port}/verify",
                headers={"X-API-Key": api_key},
                timeout=self._timeout,
            ) as resp:
                return resp.status == 200
        except (aiohttp.ClientError, asyncio.TimeoutError, OSError):
            return False


    # ------------------------------------------------------------------
    # Reauth Flow – Wordt gestart bij ongeldige API-sleutel (401/403)
    # ------------------------------------------------------------------
    async def async_step_reauth(
        self, entry_data: dict[str, Any]
    ) -> ConfigFlowResult:
        """Start de reauth-flow vanuit een bestaande config entry."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Laat de gebruiker een nieuwe API-sleutel invoeren."""
        errors: dict[str, str] = {}
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])

        if entry is None:
            return self.async_abort(reason="unknown")

        if user_input is not None:
            api_key = user_input[CONF_API_KEY].strip()

            if await self._async_test_auth(entry.data[CONF_HOST], entry.data[CONF_PORT], api_key):
                return self.async_update_reload_and_abort(
                    entry,
                    data={**entry.data, CONF_API_KEY: api_key},
                )
            errors["base"] = "invalid_auth"

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_API_KEY): TextSelector(
                        TextSelectorConfig(type=TextSelectorType.PASSWORD)
                    )
                }
            ),
            description_placeholders={
                "host": str(entry.data[CONF_HOST]),
            },
            errors=errors,
        )

