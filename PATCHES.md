# Patch Documentation

This document describes every modification made to the original upstream bot code and the reason for each change.

---

## bot/cogs/render.py

### Patch 1: Migrate from nextcord to discord.py

**Why:** `nextcord` is a stale fork of discord.py that is no longer actively maintained. `discord.py` is the canonical library and receives regular updates.

**Change:** All `nextcord` imports replaced with `discord` and `discord.ext.commands`. `SlashOption` replaced with `app_commands.describe` and `app_commands.Range`.

### Patch 2: Fix anonymous parameter name

**Why:** The original bot passed `anonymous=anonymous` to `render_single`, but the `Renderer` class uses `anon` not `anonymous`. This caused a `TypeError` at render time.

**Change:** Parameter renamed from `anonymous` to `anon` throughout the command handler and task.

### Patch 3: Improved error handling

**Why:** The original code showed a generic "Unknown error" for all failure modes. This made it impossible to tell whether the replay file was corrupt, an unsupported version, or a rendering bug.

**Change:** Result handling now distinguishes between `ReplayParsingError`, `ReplayRenderingError`, and unexpected exceptions, with a specific message for each.

### Patch 4: Queue position display

**Why:** Users had no feedback about how long they would wait when the queue had multiple jobs ahead of them.

**Change:** When a job is in `queued` state, the embed now shows the user's position in the queue.

### Patch 5: Cooldown message improvement

**Why:** The original code just said "You're on cooldown!" with no indication of how long to wait.

**Change:** The cooldown message now includes the remaining seconds from the Redis TTL.

### Patch 6: File validation before queuing

**Why:** Without validation, any file could be uploaded and passed to the renderer, including files that are too large, not actually replay files, or deliberately malformed. The renderer treats input as trusted which creates unnecessary risk.

**Change:** Added `validate_replay()` function and `MAX_FILE_SIZE_MB = 5` constant. Validation checks:
- File extension (case-insensitive, must be `.wowsreplay`)
- File size (maximum 5 MB, checked against attachment metadata before download where possible)
- Minimum file size (rejects empty files)
- Header bytes (rejects zero-byte or corrupt files)

Validation runs at two points: against attachment metadata before downloading (fast rejection), and against file content after downloading (catches renamed or corrupt files).

---

## bot/cogs/dual_render.py

### Patch 1: New file (not in upstream)

**Why:** The upstream bot only supported single replay rendering. Dual render support was added to this fork to allow side-by-side comparison of both teams' perspectives from the same battle.

**Change:** New cog implementing `/minimap_dual` command, mirroring the structure of `render.py` but accepting two replay files and passing them to `tasks/dual.py`.

### Patch 2: File validation before queuing

**Why:** Same as render.py Patch 6. Both replay files are validated independently with clear per-file error messages.

**Change:** Same `validate_replay()` function and constants as render.py. Validation applied to both attachments before either is queued.

---

## utils/connection.py

### Patch 1: Replace aioredis with redis.asyncio

**Why:** The `aioredis` library was abandoned by its maintainer and is no longer maintained. Its functionality has been merged into `redis-py` as `redis.asyncio`.

**Change:** `import aioredis` replaced with `import redis.asyncio as aioredis`. The API is identical so no other changes were needed.

### Patch 2: TLS support for Azure

**Why:** Azure Cache for Redis requires TLS connections on port 6380. The original code had no TLS support.

**Change:** Added `REDIS_TLS` environment variable. When set to `true`, connections use `ssl=True` and `ssl_cert_reqs="required"`. Local development uses `REDIS_TLS=false` with plain connections.

---

## tasks/single.py

### Patch 1: Fix anonymous parameter name

**Why:** Same as bot/cogs/render.py Patch 2 — the `Renderer` class uses `anon`, not `anonymous`.

**Change:** `anonymous` parameter renamed to `anon` and passed as `anon=anon` to `Renderer`.

### Patch 2: Remove get_player_build()

**Why:** The original task returned a tuple of `(video_bytes, builds)` where `builds` came from `renderer.get_player_build()`. This method is not present in the current renderer version and the build URL feature has been removed from this fork.

**Change:** Task now returns `video_bytes` only as a plain `bytes` object.

---

## bot/bot.py

### Patch 1: Migrate from nextcord to discord.py

**Why:** Same as render.py Patch 1.

**Change:** `nextcord.ext.commands` replaced with `discord.ext.commands`. Cog registration updated to use `await BOT.add_cog()` which is the discord.py async pattern.

### Patch 2: Add Message Content Intent

**Why:** discord.py requires explicit intent declarations. Without `message_content` intent the bot cannot read attachment filenames.

**Change:** Added `intents = discord.Intents.default()` with `intents.message_content = True`.

---

## Dockerfile (new file)

**Why:** Containerisation for Azure deployment. Key security decisions:

- Based on `python:3.10-slim` — minimal attack surface
- Runs as non-root user `mmr` — container cannot modify system files even if compromised
- `apply_patches.py` runs at build time — renderer is patched into the image, not at runtime
- No secrets in the image — all credentials injected at runtime via environment variables
- Single image for both bot and worker — `MODE` environment variable selects which process to run

---

## azure-container-apps.yml

### Patch 1: Worker scale-to-zero

**Why:** The worker was configured with `minReplicas: 1`, meaning it ran continuously even when no render jobs were queued. At 1.0 vCPU / 2Gi RAM this was the largest idle cost in the system despite near-zero CPU utilisation.

**Change:** `minReplicas` set to 0. KEDA Redis scaler added watching `rq:queue:single` — worker spins up when jobs arrive and scales back to zero after the cooldown period (300 seconds). Max replicas reduced from 5 to 3.

### Patch 2: Worker resource reduction

**Why:** Observed CPU utilisation never exceeded 0.5% of the 1.0 vCPU allocation at idle. Even during renders the workload does not justify 1.0 vCPU / 2Gi.

**Change:** Worker resources reduced to `cpu: 0.25, memory: 0.5Gi`. Monitor render performance and increase if needed.

---

## apply_patches.py (copied from renderer repo)

This file is copied from the [minimap_renderer](https://github.com/bounded-rationality/minimap_renderer) repo and is not modified here. It patches the installed renderer package for 15.x compatibility. See PATCHES.md in the renderer repo for full documentation of what it does.

It is run during the Docker image build so that the container image already contains the patched renderer — patches do not need to be re-applied at container startup.
