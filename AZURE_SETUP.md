# Azure Setup & Operations Guide

This document covers the Azure infrastructure for the Minimap Renderer Bot, day-to-day operational commands, and how to update for a new WoWS version.

---

## Infrastructure overview

All resources are in a single resource group in the Azure Australia East region.

| Resource | Purpose |
|----------|---------|
| Container Registry | Stores Docker images |
| Key Vault | Stores Discord token and Redis password |
| Redis Cache | Job queue, cooldowns, progress tracking |
| Container Apps environment | Hosts both containers |
| Container App: bot | Runs the Discord bot (always on, 1 replica) |
| Container App: worker | Runs the render worker (scales 0–3 replicas) |
| Managed Identity: bot | Bot pulls from ACR, reads Key Vault |
| Managed Identity: worker | Worker pulls from ACR, reads Key Vault |

---

## GitHub secrets required

These must be set in the repo under Settings → Secrets and variables → Actions:

| Secret | Description |
|--------|-------------|
| `AZURE_CREDENTIALS` | Service principal JSON created via `az ad sp create-for-rbac` |
| `AZURE_SUBSCRIPTION_ID` | Azure subscription ID |
| `ACR_LOGIN_SERVER` | Container registry login server |
| `ACR_NAME` | Container registry name |
| `BOT_IDENTITY_ID` | Full resource ID of the bot managed identity |
| `WORKER_IDENTITY_ID` | Full resource ID of the worker managed identity |

---

## Worker scaling

The worker is configured to scale to zero replicas when idle, and scale up automatically when jobs arrive in the Redis queue. This means:

- No cost is incurred when no renders are being processed
- The first render after a period of inactivity will take an extra 30–60 seconds for the worker to cold-start
- Up to 3 worker replicas can run concurrently under load

The worker uses a KEDA Redis scaler watching the `rq:queue:single` queue. It is configured with:

- Min replicas: 0
- Max replicas: 3
- CPU: 0.25 vCPU
- Memory: 0.5Gi

To update the worker scaling configuration use the Azure CLI — do not paste sensitive values into chat or commit them to the repo. Resource names and IDs are stored in GitHub Secrets only.

---

## Day-to-day operations

All commands require the Azure CLI (`az`) to be installed and logged in via `az login`.

### Check container logs

```powershell
az containerapp logs show --name mmr-bot --resource-group <your-resource-group> --tail 50
az containerapp logs show --name mmr-worker --resource-group <your-resource-group> --tail 50
```

### Check current worker replica count

```powershell
az containerapp replica list --name mmr-worker --resource-group <your-resource-group> --output table
```

### Restart a container

```powershell
az containerapp revision list --name mmr-bot --resource-group <your-resource-group> --query "[?properties.active].name" -o tsv
```

Then restart the active revision:

```powershell
az containerapp revision restart --name mmr-bot --resource-group <your-resource-group> --revision <revision-name>
```

### Force redeploy without a code change

```powershell
git commit --allow-empty -m "Trigger rebuild"
git push origin master
```

### Check Redis status

```powershell
az redis show --name <your-redis> --resource-group <your-resource-group> --query "{host:hostName, port:sslPort, state:provisioningState}"
```

### Update a Key Vault secret (e.g. new Discord token)

```powershell
az keyvault secret set --vault-name <your-keyvault> --name "discord-token" --value "<new-token>"
```

Then restart the bot container to pick up the new value.

---

## Updating for a new WoWS version

When a new WoWS patch is released, the renderer repo needs new version data before the bot can parse those replays.

### Prerequisites
- World of Warships installed locally and updated to the new version
- `wowsunpack.exe` in the `minimap_renderer` repo root directory (download from https://github.com/landaire/wowsunpack/releases)
- Python venv set up in the renderer repo

### Steps

1. Activate the renderer repo venv and run the update script:
   ```powershell
   cd D:\Dev\minimap_renderer
   venv\Scripts\activate
   python update_version.py --game "D:\Games\World_of_Warships" --version X.X --region ASIA
   ```

2. Commit and push the generated assets to the renderer repo:
   ```powershell
   git add generated/ maps/ resources/ src/
   git commit -m "Update assets for WoWs X.X"
   git push
   ```

3. Trigger a rebuild of the bot image:
   ```powershell
   cd D:\Dev\MMR_bot
   git commit --allow-empty -m "Rebuild for WoWs X.X"
   git push origin master
   ```

4. Once GitHub Actions completes, verify the worker picked up the new image:
   ```powershell
   az containerapp revision list --name mmr-worker --resource-group <your-resource-group> --output table
   ```

5. Test with a replay from the new version using `/minimap` in Discord.

---

## Secrets management

Secrets are stored in Azure Key Vault and injected into containers at runtime via Managed Identity. They are never stored in code, Docker images, GitHub, or chat logs.

| Secret | Used by |
|--------|---------|
| `discord-token` | Bot container |
| `redis-password` | Bot and worker containers |

To rotate a secret, update it in Key Vault and restart the relevant container(s).

**Important:** When running Azure CLI commands or pasting command output, be aware that subscription IDs, resource names, and IP addresses may appear in output. Avoid sharing this output in unsecured channels or with AI tools. Use `--query` to extract only the specific values you need.

---

## Cost notes

Approximate monthly costs (Australia East, pay-as-you-go):

| Resource | Tier | Approx. monthly cost |
|----------|------|----------------------|
| Redis Cache | Basic C0 | ~$16 AUD |
| Container Apps (bot) | Consumption | ~$1–3 AUD |
| Container Apps (worker) | Consumption | ~$0 AUD idle, small cost per render |
| Container Registry | Basic | ~$6 AUD |
| Key Vault | Standard | ~$1 AUD |

The worker scales to zero when idle so incurs no cost between renders. Redis is the main fixed ongoing cost.
