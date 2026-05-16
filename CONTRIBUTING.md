# Contributing

Thanks for the interest. This integration is small, opinionated, and aims to
ship — the contribution loop is short.

For the full developer reference (architecture, adding tools, WebSocket
dispatch, style notes), read **[docs/developer-guide.md](docs/developer-guide.md)**.

For the release process (versioning, CHANGELOG, tags, HACS pickup), read
**[docs/release.md](docs/release.md)**.

## Quick development setup

```sh
git clone git@github.com:czechbol/hass-mcp.git
cd hass-mcp

# Symlink into a dev HA config dir so HA loads your working copy
ln -s "$PWD/custom_components/hass_mcp" /path/to/ha-config/custom_components/hass_mcp

# Install dev dependencies (in a venv or with --system)
pip install -r requirements_test.txt
```

## Run checks locally

```sh
ruff check .
ruff format --check .
pytest -v
```

CI runs the same plus `hassfest` and `hacs/action` on every push — see
[`.github/workflows/ci.yml`](.github/workflows/ci.yml).

## Commit messages

[Conventional Commits](https://www.conventionalcommits.org/):

- `feat: …` — new tool, new capability
- `fix: …` — bug, regression
- `docs: …` — README / CHANGELOG / CONTRIBUTING
- `refactor:` / `chore:` / `test:` / `ci:` — as appropriate

Subject line ≤ 70 chars. Body only for breaking changes (a `BREAKING
CHANGE:` footer is required if there is one).

## Reporting bugs

Open an issue with:

1. HA version (`ha_get_config` → `version`).
2. hass_mcp version (`manifest.json` → `version`).
3. The tool call + arguments that misbehaved.
4. The response (or error).
5. Anything from `home-assistant.log` that looks related.
