# Minimap Renderer

A community-maintained fork of [WoWs-Builder-Team/minimap_renderer](https://github.com/WoWs-Builder-Team/minimap_renderer), updated to support World of Warships 15.x replays.

> **Original project notice:** The upstream project is no longer maintained. This fork restores compatibility with current WoWs versions. Full attribution to the original authors is preserved — see [Credits](#credits).

---

## What's different in this fork

- Support for WoWs 15.2, 15.3 and 15.4 replay formats
- Patch system (`apply_patches.py`) to fix compatibility issues in the installed package
- Version updater (`update_version.py`) to extract game data for new versions
- Dual render support (`render_dual.py`) for side-by-side battle renders
- Graceful handling of ships and consumables added after 14.11

---

## Requirements

- Windows (required for `wowsunpack.exe` during version updates)
- Python 3.10
- World of Warships installed locally (for version updates only)
- [wowsunpack.exe](https://github.com/landaire/wowsunpack/releases) placed in the repo root

---

## Installation

### 1. Clone the repo

```powershell
git clone https://github.com/bounded-rationality/minimap_renderer.git
cd minimap_renderer
```

### 2. Create and activate a virtual environment

```powershell
py -3.10 -m venv venv
venv\Scripts\Activate.ps1
```

> If you get a scripts blocked error, run this first:
> ```powershell
> Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
> ```

### 3. Install dependencies

```powershell
pip install langdetect hanzidentifier
pip install --upgrade --force-reinstall git+https://github.com/WoWs-Builder-Team/minimap_renderer.git
```

### 4. Apply patches

```powershell
python apply_patches.py
```

### 5. Set up game data for your current WoWs version

```powershell
python update_version.py --game "C:\Games\World_of_Warships" --version 15.4
```

> Replace the path with your actual WoWs installation folder and the version with the current game version.

---

## Usage

### Single render

```powershell
python -m render --replay path\to\your.wowsreplay
```

This produces a `.mp4` file in the same folder as the replay.

### Dual render

```powershell
python render_dual.py --replay1 team1.wowsreplay --replay2 team2.wowsreplay --green-tag "Green Team" --red-tag "Red Team"
```

---

## Keeping up to date

When WoWs releases a new update:

1. Download the latest ship bar images:
   ```powershell
   python extract.py
   Copy-Item -Path "res_extract\gui\ship_bars\*" -Destination "renderer\resources\ship_bars" -Recurse -Force
   ```

2. Update game data for the new version:
   ```powershell
   python update_version.py --game "C:\Games\World_of_Warships" --version X.X
   ```

3. Re-apply patches if needed:
   ```powershell
   python apply_patches.py
   ```

---

## Known limitations

- **abilities.json not updated** — consumable icons for ships using slot IDs 4, 6, or 8 (added after 14.11) will not display. Renders will not crash but those consumable indicators will be missing.
- **ship_bars images** — silhouette images for ships added after 14.11 must be manually extracted and committed after each update.

---

## Credits

- Original project by [@notyourfather#7816](https://github.com/WoWs-Builder-Team) and [@Trackpad#1234](https://github.com/WoWs-Builder-Team) — [WoWs-Builder-Team/minimap_renderer](https://github.com/WoWs-Builder-Team/minimap_renderer)
- Replay parsing by Monstrofil — [replays_unpack](https://github.com/Monstrofil/replays_unpack)
- Unpack tool by landaire — [wowsunpack](https://github.com/landaire/wowsunpack)

---

## License

GNU AGPLv3 — see [LICENSE](LICENSE)
