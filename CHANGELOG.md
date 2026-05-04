# Changelog

## [Community Fork] — 2026-05-03

Initial community fork based on the original WoWs-Builder-Team/minimap_renderer_bot project.

### Changed

- **Discord library**: Migrated from `nextcord` to `discord.py` — nextcord is a stale fork, discord.py is the actively maintained library
- **Redis client**: Replaced abandoned `aioredis` library with `redis.asyncio`, which is now built into `redis-py` itself
- **Parameter name**: `anonymous` renamed to `anon` to match the actual `Renderer` class signature in the updated renderer
- **Error messages**: Now distinguish between parsing failures, rendering failures, and unknown errors rather than showing a generic message
- **Queue position**: Users are now shown their position in the queue while waiting
- **Cooldown message**: Now shows the user exactly how many seconds remain on their cooldown

### Added

- **TLS support for Redis**: `REDIS_TLS=true` environment variable enables SSL — required for Azure Cache for Redis
- **Dockerfile**: Single image used for both bot and worker containers, runs as non-root user for security
- **docker-compose.yml**: Local development setup with Redis, bot, and worker containers
- **azure-container-apps.yml**: Azure Container Apps deployment configuration with Key Vault secret references
- **.github/workflows/deploy.yml**: GitHub Actions CI/CD pipeline — push to master automatically builds and redeploys
- **.env.example**: Template for required environment variables
- **apply_patches.py**: Copied from renderer repo — applied during Docker image build to fix 15.x compatibility

### Removed

- `nextcord` dependency
- `aioredis` dependency
- `helpers.py` — unused in this fork
- WoWs ShipBuilder build URL integration — not relevant to this fork
