#!/usr/bin/env python3
"""
apply_patches.py
Applies all necessary patches to the installed minimap_renderer packages
to make them compatible with WoWs 15.x replays.

Run this once after installing the renderer:
    python apply_patches.py
"""
import os
import sys
import site
import glob

def find_package(name):
    for path in site.getsitepackages():
        candidate = os.path.join(path, name)
        if os.path.exists(candidate):
            return candidate
    raise FileNotFoundError(f"Could not find package: {name}")

def patch_file(path, old, new, description):
    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    if old not in content:
        if new in content:
            print(f"  ALREADY APPLIED: {description}")
        else:
            print(f"  WARNING: Could not find patch target in {os.path.basename(path)}: {description}")
        return False
    content = content.replace(old, new, 1)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"  OK: {description}")
    return True

def main():
    print("Applying patches to minimap_renderer packages...\n")

    try:
        replay_unpack = find_package('replay_unpack')
        renderer = find_package('renderer')
    except FileNotFoundError as e:
        print(f"ERROR: {e}")
        print("Make sure you have activated the venv and installed the renderer first.")
        sys.exit(1)

    print(f"replay_unpack: {replay_unpack}")
    print(f"renderer: {renderer}")
    print()

    # -------------------------------------------------------------------------
    # Patch 1: replay_reader.py - skip zero-size blocks
    # -------------------------------------------------------------------------
    print("Patching replay_reader.py...")
    patch_file(
        os.path.join(replay_unpack, 'replay_reader.py'),
        old=(
            'for i in range(blocks_count - 1):\n'
            '                block_size = struct.unpack("i", f.read(4))[0]\n'
            '                data = json.loads(f.read(block_size))\n'
            '                extra_data.append(data)'
        ),
        new=(
            'for i in range(blocks_count - 1):\n'
            '                block_size = struct.unpack("i", f.read(4))[0]\n'
            '                if block_size == 0:\n'
            '                    continue\n'
            '                data = json.loads(f.read(block_size))\n'
            '                extra_data.append(data)'
        ),
        description="Skip zero-size blocks in 15.x replay format"
    )
    print()

    # -------------------------------------------------------------------------
    # Patch 2: renderer/layers/ship.py - graceful abilities fallback
    # -------------------------------------------------------------------------
    print("Patching renderer/layers/ship.py...")
    ship_py = os.path.join(renderer, 'layers', 'ship.py')

    patch_file(
        ship_py,
        old='abilities = self._abilities[params_id]',
        new='abilities = self._abilities.get(params_id)',
        description="Graceful abilities lookup for unknown ships"
    )
    patch_file(
        ship_py,
        old=(
            '                for aid, _ in ac.items():\n'
            '                    abilities = self._abilities.get(params_id)\n'
            '                    try:\n'
            '                        index = abilities["id_to_index"][aid]\n'
            '                    except KeyError:\n'
            '                        try:\n'
            '                            index = self._abilities["clan"][aid]\n'
            '                        except KeyError:\n'
            '                            continue'
        ),
        new=(
            '                for aid, _ in ac.items():\n'
            '                    abilities = self._abilities.get(params_id)\n'
            '                    if abilities is None: continue\n'
            '                    try:\n'
            '                        index = abilities["id_to_index"][aid]\n'
            '                    except KeyError:\n'
            '                        try:\n'
            '                            index = self._abilities["clan"][aid]\n'
            '                        except KeyError:\n'
            '                            continue'
        ),
        description="Skip consumable rendering for unknown ships"
    )
    print()

    # -------------------------------------------------------------------------
    # Patch 3: renderer/layers/health.py - graceful abilities fallback
    # -------------------------------------------------------------------------
    print("Patching renderer/layers/health.py...")
    health_py = os.path.join(renderer, 'layers', 'health.py')
    patch_file(
        health_py,
        old='ability = self._abilities[self._player.ship_params_id]',
        new='ability = self._abilities.get(self._player.ship_params_id)',
        description="Graceful abilities lookup"
    )
    patch_file(
        health_py,
        old=(
            '        if (flags := bin(ship.burn_flags)[2:][::-1]) != "0":\n'
            '            burn_nodes, flood_nodes = info["hulls"][self._player.hull]'
        ),
        new=(
            '        if (flags := bin(ship.burn_flags)[2:][::-1]) != "0":\n'
            '            if ability is None:\n'
            '                return\n'
            '            burn_nodes, flood_nodes = info["hulls"][self._player.hull]'
        ),
        description="Guard abilities usage in burn/flood nodes"
    )
    print()

    # -------------------------------------------------------------------------
    # Patch 4: renderer/layers/markers.py - graceful abilities fallback
    # -------------------------------------------------------------------------
    print("Patching renderer/layers/markers.py...")
    patch_file(
        os.path.join(renderer, 'layers', 'markers.py'),
        old='abilities = self._abilities[player.ship_params_id]',
        new=(
            'abilities = self._abilities.get(player.ship_params_id)\n'
            '            if abilities is None:\n'
            '                continue'
        ),
        description="Graceful abilities lookup for unknown ships"
    )
    patch_file(
        os.path.join(renderer, 'layers', 'markers.py'),
        old=(
            '                for aid in {11, 13}.intersection(ac):\n'
            '                    name = f"{id_to_index[aid]}.{id_to_subtype[aid]}"'
        ),
        new=(
            '                for aid in {11, 13}.intersection(ac):\n'
            '                    if aid not in id_to_index or aid not in id_to_subtype:\n'
            '                        continue\n'
            '                    name = f"{id_to_index[aid]}.{id_to_subtype[aid]}"'
        ),
        description="Skip unknown sonar/radar slot IDs gracefully"
    )
    print()

    # -------------------------------------------------------------------------
    # Patch 5: battle_controller.py - fix consumableUsageParams signature
    # -------------------------------------------------------------------------
    print("Patching battle_controller.py (consumable signature)...")
    controllers = glob.glob(os.path.join(replay_unpack, 'clients', 'wows', 'versions', '*', 'battle_controller.py'))
    for bc_path in controllers:
        patch_file(
            bc_path,
            old='def _on_consumable_used(self, entity: Entity, consumableType, workTimeLeft):',
            new='def _on_consumable_used(self, entity: Entity, consumableType=None, workTimeLeft=None, consumableUsageParams=None, **kwargs):',
            description="Fix consumableUsageParams signature"
        )
    print()

    # -------------------------------------------------------------------------
    # Patch 6: battle_controller.py - fix ribbon tracking ID
    # -------------------------------------------------------------------------
    print("Patching battle_controller.py (ribbon tracking)...")
    for bc_path in controllers:
        patch_file(
            bc_path,
            old='self._ribbons.setdefault(avatar.id,',
            new='self._ribbons.setdefault(self._owner.get("shipId", avatar.id),',
            description="Fix ribbon tracking to use shipId instead of avatar.id"
        )
    print()

    # -------------------------------------------------------------------------
    # Patch 7: renderer/render.py - remove watermark
    # -------------------------------------------------------------------------
    print("Patching renderer/render.py...")
    render_py = os.path.join(renderer, 'render.py')
    with open(render_py, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()

    if 'Minimap Renderer' in content or 'github.com/WoWs-Builder-Team' in content:
        import re
        content = re.sub(
            r'    def _draw_header\(self, image: Image\.Image\):.*?(?=\n    def |\nclass |\Z)',
            '    def _draw_header(self, image: Image.Image):\n        pass',
            content,
            flags=re.DOTALL
        )
        with open(render_py, 'w', encoding='utf-8') as f:
            f.write(content)
        print("  OK: Watermark removal")
    else:
        print("  ALREADY APPLIED: Watermark removal")
    print()

    print("All patches applied successfully!")
    print()
    print("Next step: run update_version.py to set up game data for your current WoWs version.")

if __name__ == '__main__':
    main()
