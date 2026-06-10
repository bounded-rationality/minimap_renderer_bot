# Changelog

## [Community Fork] — 2026-06-10

### Changed

- **Worker scaling** (`azure-container-apps.yml`): Worker min replicas reduced from 1 to 0. Worker now scales to zero when idle and spins up automatically via KEDA Redis scaler when jobs arrive in the queue. Eliminates idle compute cost.
- **Worker resources** (`azure-container-apps.yml`): Worker CPU reduced from 1.0 to 0.25 vCPU, memory reduced from 2Gi to 0.5Gi. Sufficient for rendering workloads based on observed utilisation.

### Added

- **File validation** (`bot/cogs/render.py`, `bot/cogs/dual_render.py`): Replay files are now validated before being queued:
  - Maximum file size: 5 MB (based on observed real-world replay sizes)
  - Extension check (case-insensitive)
  - Minimum size check to reject empty files
  - Header check to reject zero-byte or corrupt files
  - Size is checked before download where possible for fast rejection

---

## [Community Fork] — 2026-05-21

### Fixed

- **Regen tuple unpack** (`renderer/layers/health.py`): In 15.4 the regen consumable state tuple was reduced from 4 values to 2. Changed unpack from `_, count, _, _ = regen` to `_, count, *_ = regen` so it handles both old and new formats.
- **Consumable icon `None` aid** (`renderer/layers/ship.py`): In 15.4 some consumable slot IDs are `None`, causing `KeyError: None` in both the `id_to_index` and `clan` lookups. Both except clauses now catch `TypeError` as well as `KeyError`, and advance `x_pos` before continuing so the icon layout isn't shifted.

---

## [Community Fork] — 2026-05-03

### Fixed

- **Consumable patch signature** (`apply_patches.py`): The `_on_consumable_used` patch was targeting the wrong function signature. Corrected to match the actual installed signature `entity: Entity, consumableType, workTimeLeft`.
- **Ribbon tracking** (`battle_controller.py`): Ribbons were being stored under `avatar.id` but the renderer looks them up by `vehicle.shipId`. Fixed `_update_ribbons` to use `self._owner.get("shipId", avatar.id)`.
- **Ship abilities guard** (`renderer/layers/ship.py`): The `if abilities is None: continue` guard was being inserted inside the `try` block causing a `SyntaxError`. Now correctly placed before the `try` block.

---

## [Community Fork] — 2026-03-22

Initial community fork based on the original WoWs-Builder-Team/minimap_renderer project, last supported at WoWs 14.11.

### Added

- Support for WoWs 15.2 and 15.3 replay formats
- `scripts/extract_gameparams.py` — decoder for the new `%bin` GameParams format introduced in 15.3
- `scripts/generate_data.py` — generates `ships.json`, `projectiles.json`, `planes.json` from game installation
- `update_version.py` — single-command version updater
- `apply_patches.py` — applies all code patches to installed packages
- `render_dual.py` — side-by-side dual replay renderer

### Fixed

- **Replay reader** (`replay_unpack/replay_reader.py`): Skip zero-size blocks in the 3-block replay format introduced in WoWs 15.x
- **Consumable tracking** (`battle_controller.py`): `_on_consumable_used` now accepts `consumableUsageParams` keyword argument introduced in 15.2+
- **Ribbon display** (`battle_controller.py`): Ribbons now stored under `shipId` instead of `avatar.id` so the renderer can find them
- **Abilities fallback** (`renderer/layers/ship.py`, `health.py`, `markers.py`): Ships not in the abilities database now fail gracefully instead of crashing
- **Consumable icon fallback** (`renderer/layers/ship.py`): Unknown consumable slot IDs now skipped instead of crashing

### Changed

- Watermark removed from renders
- Ship display names sourced from the game's localization files (`global.mo`)
- Data generation updated for the new GameParams region-based structure in 15.3

### Known Issues

- `abilities.json` not regenerated from current game data — consumable icons for slot IDs 4, 6, 8 will not display
- `ship_bars` images for ships added after 14.11 must be manually extracted after each game update
