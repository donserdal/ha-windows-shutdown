# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [Unreleased]

### Added
<!-- New features -->

### Changed
<!-- Changes to existing features -->

### Fixed
<!-- Bug fixes -->

---

## [1.2.0] — 2024-12-01

### Added
- Reauthentication flow: renew the API key via the UI without reinstalling the integration
- Diagnostics: downloadable debug information for troubleshooting
- Reconfigure flow: adjust delay and action type via the **Configure** button
- mDNS scan is now thread-safe via `threading.Lock`
- Port range validation (1–65535) for manual entry
- `PARALLEL_UPDATES = 1` on both platforms
- `ConfigEntryState.LOADED` check for service calls

### Changed
- Service registration now uses the modern `runtime_data` approach
- HTTP logic centralized in a single `_async_request` helper
- API key is now private (`self._api_key`)
- `SHUTDOWN_TYPES` changed from `list` to `tuple`
- JSON parse error refined to `JSONDecodeError`
- Button is greyed out when the PC is offline

### Fixed
- `async_get_options_flow` was in the wrong class
- Duplicate definition of `CONF_API_KEY` in `const.py`
- Port number used string literal `'port'` instead of `CONF_PORT`
- CRLF line endings in `services.yaml`

---

## [1.1.0] — 2024-06-01

### Added
- Automatic device discovery via mDNS/Zeroconf
- Support for multiple Windows computers
- Selectable action type: `shutdown`, `restart`, `logoff`
- Cooldown protection (5 seconds) between shutdown commands

### Changed
- Coordinator uses a 30-second grace period on connection loss

---

## [1.0.0] — 2024-01-01

### Added
- First release
- Shutdown button entity
- Online/offline sensor
- Manual configuration via the UI