# Contributing to Windows Shutdown

Thank you for your interest in contributing to this integration!

## How can you contribute?

- **Report bugs** via an [issue](https://github.com/donserdal/ha-windows-shutdown/issues/new?template=bug_report.yaml)
- **Propose features** via a [feature request](https://github.com/donserdal/ha-windows-shutdown/issues/new?template=feature_request.yaml)
- **Contribute code** via a pull request

## Submitting a Pull Request

1. Fork the repository
2. Create a branch: `git checkout -b feature/my-improvement`
3. Make your changes
4. Manually test in a Home Assistant installation
5. Update `CHANGELOG.md` under an `[Unreleased]` section
6. Submit a pull request to `main`

## Code Style

- Follow the [HA Integration Guidelines](https://developers.home-assistant.io/docs/creating_component_index)
- Use type annotations
- Write docstrings for classes and public methods
- Adhere to the existing project structure

## Releasing a New Version

For administrators only:

1. Update `CHANGELOG.md`: replace `[Unreleased]` with the new version number and date
2. Commit: `git commit -m "Release v1.3.0"`
3. Tag: `git tag v1.3.0`
4. Push: `git push origin main --tags`

The release workflow automatically creates a GitHub Release, updates `manifest.json`, and adds the release zip file.