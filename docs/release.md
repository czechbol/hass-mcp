# Release process

How `hass-mcp` versions, tags, and ships.

## Versioning

[Semantic Versioning 2.0.0](https://semver.org/):

- **MAJOR** — breaking changes to the tool surface, the on-the-wire MCP
  envelope, or the integration option schema.
- **MINOR** — new tool, new option, new field in an existing response,
  new transport behavior (additive).
- **PATCH** — bug fix that doesn't change the public surface.

Pre-1.0 we still bump MINOR for occasional breaking changes (call it out
loudly in the changelog).

## CHANGELOG discipline

Every PR adds a line under `## [Unreleased]` in `CHANGELOG.md` in one of:

- `### Added` — new functionality.
- `### Changed` — backwards-compatible improvements / behavior changes.
- `### Fixed` — bug fix.
- `### Removed` — feature removed.
- `### Security` — vulnerability fix.
- `### Deprecated` — feature marked for future removal.

Lines should be brief but specific:

> ✅ `ha_call_service` auto-detects `return_response` from `Service.supports_response`.
> ❌ Fixed some service call bugs.

## Release steps

When we decide a version is shippable:

1. **Move `[Unreleased]` to a version section**:

   ```diff
    ## [Unreleased]
   +
   +## [0.6.0] - 2026-05-17

   - … entries …

   +[0.6.0]: https://github.com/czechbol/hass-mcp/releases/tag/v0.6.0
    [0.5.2]: https://github.com/czechbol/hass-mcp/releases/tag/v0.5.2
   ```

   Also update the `[Unreleased]` compare link to point at the new tag.

2. **Bump version in two places**:
   - `custom_components/hass_mcp/manifest.json` → `"version": "0.6.0"`
   - `custom_components/hass_mcp/const.py` → `SERVER_VERSION = "0.6.0"`

3. **Commit**:

   ```sh
   git commit -m "chore: release 0.6.0"
   git push
   ```

4. **Wait for CI to pass** (hassfest, HACS validate, ruff, pytest).

5. **Tag and create the GitHub release**:

   ```sh
   gh release create v0.6.0 \
     --title "0.6.0" \
     --notes-from-tag        # or --notes "$(awk '/## \[0.6.0\]/,/## \[0.5/' CHANGELOG.md | sed '$d')"
   ```

   Alternatively in the UI: **Releases → Draft a new release → tag v0.6.0**,
   target `main`, paste the CHANGELOG section as body.

## How HACS picks up the release

HACS tracks GitHub releases for custom repositories. After the tag exists:

- The HACS frontend shows an update prompt within the next poll cycle
  (~30 min). Users can force-refresh via `hacs/repository/refresh`.
- `ha_hacs op=download repository=<id>` installs the latest release tag.

Until 1.0.0 the project also publishes off `main` HEAD — HACS users can
opt into either tagged releases or main-branch HEAD.

After 1.0.0 we plan to set `hide_default_branch: true` in `hacs.json` to
force HACS users onto tagged releases.

## CI gates

Every push to `main` and every PR runs:

| Job | What it checks |
|---|---|
| `hassfest` | manifest sorted, deps declared, services valid, config schema |
| `hacs validate` | `hacs.json` shape, repo description, manifest (`topics` ignored — set them on GitHub) |
| `ruff lint + format` | `pyproject.toml` rules (`E`, `F`, `W`, `I`, `B`, `UP`, `RUF`, `BLE`, `SLF`) + format check |
| `pytest` | Fast unit tests for `protocol`, `registry`, `rate_limit` |

A release shouldn't go out unless all four are green on the commit the
tag points to. Tag pushes don't currently re-run CI — verify before
tagging.

## Hotfix path

For an urgent fix on a released version:

1. Cherry-pick or land the fix on `main`.
2. Bump PATCH (`0.6.0` → `0.6.1`).
3. Move only the relevant lines to a new version section in CHANGELOG.
4. Tag + release as above.

There is no `release/x.y` branch yet — the rate of breakage hasn't called
for one. If we ever need to backport into an older line, we'll add the
branch then.

## Pre-release / beta tags

Use `-beta.N` suffixes:

```sh
gh release create v0.6.0-beta.1 --prerelease ...
```

`hacs.json` doesn't currently allow pre-releases by default; users who
want betas can switch the integration to "Show beta versions" in HACS.
