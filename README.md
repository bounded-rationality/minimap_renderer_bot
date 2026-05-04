# Minimap Renderer Bot

A community-maintained Discord bot for rendering World of Warships replay files into minimap videos.

> **Based on** [WoWs-Builder-Team/minimap_renderer_bot](https://github.com/WoWs-Builder-Team/minimap_renderer_bot) — updated for 15.x compatibility, migrated to discord.py, and containerised for Azure deployment.

---

## How it works

A user uploads a `.wowsreplay` file via the `/render` slash command. The bot queues the job in Redis, a worker container picks it up, renders the minimap video, and the bot posts the `.mp4` back to Discord.

```
Discord user
    │
    ▼
[Bot container]  ──── Redis queue ────  [Worker container]
    │                                         │
    └──── polls job status ◄──────────────────┘
    │
    ▼
Posts .mp4 to Discord
```

---

## Local development

### Prerequisites
- Docker Desktop
- A Discord bot token (from [Discord Developer Portal](https://discord.com/developers/applications))

### Setup

1. Clone the repo:
   ```bash
   git clone https://github.com/bounded-rationality/minimap_renderer_bot.git
   cd minimap_renderer_bot
   ```

2. Create your `.env` file:
   ```bash
   cp .env.example .env
   # Edit .env and add your DISCORD_TOKEN
   ```

3. Build and run:
   ```bash
   docker compose up --build
   ```

The bot and worker will start automatically. Redis runs as a local container — no password needed for local dev.

---

## Azure deployment

### Prerequisites
- Azure Container Registry (ACR)
- Azure Container Apps environment
- Azure Cache for Redis (Basic tier)
- Azure Key Vault (for secrets)

### One-time setup

1. Push your image to ACR:
   ```bash
   az acr build --registry <your-acr> --image mmr-bot:latest .
   ```

2. Store secrets in Azure Key Vault:
   ```bash
   az keyvault secret set --vault-name <your-kv> --name DISCORD-TOKEN --value "<token>"
   az keyvault secret set --vault-name <your-kv> --name REDIS-PASSWORD --value "<password>"
   ```

3. Update `azure-container-apps.yml` with your ACR name, Redis host, and Key Vault URL.

4. Add these secrets to your GitHub repo (Settings → Secrets):
   - `ACR_LOGIN_SERVER`
   - `ACR_USERNAME`
   - `ACR_PASSWORD`
   - `ACR_NAME`
   - `AZURE_CREDENTIALS`
   - `AZURE_RESOURCE_GROUP`

### Deploying

Push to `master` — GitHub Actions will build the image, push to ACR, and redeploy both containers automatically.

### Updating for a new WoWS version

1. On your local Windows machine, run the update scripts from your renderer repo
2. Commit and push the updated game data to the renderer repo
3. Push a new commit to this repo to trigger a redeploy (or use workflow_dispatch in GitHub Actions)

---

## Commands

| Command | Description |
|---------|-------------|
| `/render` | Renders a `.wowsreplay` file |

### `/render` options

| Option | Default | Description |
|--------|---------|-------------|
| `attachment` | required | Your `.wowsreplay` file |
| `fps` | 30 | Frames per second (20-30) |
| `quality` | 7 | Video quality (1-9, higher = larger file) |
| `logs` | True | Show event log overlay |
| `chat` | True | Show chat in log overlay |
| `anon` | False | Hide player names |

---

## Security

- All secrets are injected as environment variables at runtime — never stored in code or images
- Azure deployment uses Key Vault references — secrets never touch GitHub
- Containers run as a non-root user
- Redis uses TLS in production (Azure Cache for Redis)
- No inbound ports exposed — bot connects outbound to Discord only

---

## Credits

- Original bot by `@notyourfather#7816` and `@Trackpad#1234` — [WoWs-Builder-Team/minimap_renderer_bot](https://github.com/WoWs-Builder-Team/minimap_renderer_bot)
- Renderer fork — [bounded-rationality/minimap_renderer](https://github.com/bounded-rationality/minimap_renderer)
- Replay parsing by Monstrofil — [replays_unpack](https://github.com/Monstrofil/replays_unpack)

---

## License

GNU AGPLv3 — see [LICENSE](LICENSE)
