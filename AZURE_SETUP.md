# Azure Setup & Operations Guide

This document covers the Azure infrastructure for the Minimap Renderer Bot, day-to-day operational commands, and how to update for a new WoWS version.

---

## Infrastructure overview

All resources are in the `rg-mmr` resource group, Azure Australia East region.

| Resource | Name | Purpose |
|----------|------|---------|
| Container Registry | `acrminimapreducer` | Stores Docker images |
| Key Vault | `kv-mmr` | Stores Discord token and Redis password |
| Redis Cache | `redis-mmr` | Job queue, cooldowns, progress tracking |
| Container Apps environment | `env-mmr` | Hosts both containers |
| Container App | `mmr-bot` | Runs the Discord bot (always on, 1 replica) |
| Container App | `mmr-worker` | Runs the render worker (scales 1–5 replicas) |
| Managed Identity | `id-mmr-bot` | Bot pulls from ACR, reads Key Vault |
| Managed Identity | `id-mmr-worker` | Worker pulls from ACR, reads Key Vault |

---

## GitHub secrets required

These must be set in the repo under Settings → Secrets and variables → Actions:

| Secret | Description |
|--------|-------------|
| `AZURE_CREDENTIALS` | Service principal JSON created via `az ad sp create-for-rbac` |
| `AZURE_SUBSCRIPTION_ID` | Azure subscription ID |
| `ACR_LOGIN_SERVER` | `acrminimapreducer.azurecr.io` |
| `ACR_NAME` | `acrminimapreducer` |
| `BOT_IDENTITY_ID` | Full resource ID of `id-mmr-bot` |
| `WORKER_IDENTITY_ID` | Full resource ID of `id-mmr-worker` |

---

## Day-to-day operations

All commands require the Azure CLI (`az`) to be installed and logged in via `az login`.

### Check container logs

```powershell
az containerapp logs show --name mmr-bot --resource-group rg-mmr --tail 50
az containerapp logs show --name mmr-worker --resource-group rg-mmr --tail 50
```

### Restart a container

```powershell
az containerapp revision restart --name mmr-bot --resource-group rg-mmr --revision mmr-bot--0000001
az containerapp revision restart --name mmr-worker --resource-group rg-mmr --revision mmr-worker--0000001
```

> Note: the revision name increments each time the container is redeployed. If the above fails, check the current revision name with:
> ```powershell
> az containerapp revision list --name mmr-bot --resource-group rg-mmr --query "[].{name:name, active:properties.active}" -o table
> ```

### Force redeploy without a code change

```powershell
git commit --allow-empty -m "Trigger rebuild"
git push origin master
```

### Check Redis connection

```powershell
az redis show --name redis-mmr --resource-group rg-mmr --query "{host:hostName, port:sslPort, state:provisioningState}"
```

### Update a Key Vault secret (e.g. new Discord token)

```powershell
az keyvault secret set --vault-name kv-mmr --name "discord-token" --value "<new-token>"
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
   cd D:\MMR_bot\minimap_renderer
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
   cd D:\MMR_bot\minimap_renderer_bot
   git commit --allow-empty -m "Rebuild for WoWs X.X"
   git push origin master
   ```

4. Once GitHub Actions completes, restart the worker:
   ```powershell
   az containerapp revision restart --name mmr-worker --resource-group rg-mmr --revision mmr-worker--0000001
   ```

5. Test with a replay from the new version using `/minimap` in Discord.

---

## Secrets management

Secrets are stored in Azure Key Vault (`kv-mmr`) and injected into containers at runtime via Managed Identity. They are never stored in code, Docker images, or GitHub.

| Secret name in Key Vault | Used by |
|--------------------------|---------|
| `discord-token` | Bot container |
| `redis-password` | Bot and worker containers |

To rotate a secret, update it in Key Vault and restart the relevant container(s).

---

## Cost notes

Running costs on Azure free trial / pay-as-you-go (approximate):

| Resource | Tier | Approx. monthly cost |
|----------|------|----------------------|
| Redis Cache | Basic C0 | ~$16 AUD |
| Container Apps | Consumption | ~$0–5 AUD (depends on usage) |
| Container Registry | Basic | ~$6 AUD |
| Key Vault | Standard | ~$1 AUD |

Redis is the main ongoing cost. The containers only cost when actively running jobs.
