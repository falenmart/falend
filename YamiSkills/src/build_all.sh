#!/usr/bin/env bash
# Rebuilds every generated asset. Needs: python 3.13 with `bpy numpy pillow scipy soundfile`, rojo 7.
# Usage: PY=/path/to/python ./build_all.sh
set -euo pipefail
cd "$(dirname "$0")"
PY="${PY:-python3}"
ROOT=..
"$PY" blender/build_vfx.py -- "$ROOT/Blender" "$ROOT/Previews/vfx_meshes.png"
"$PY" blender/build_rig_anims.py -- "$ROOT/Blender" roblox/shared/Animations "$ROOT/Previews"
"$PY" tools/make_sfx.py "$ROOT/Blender/Sounds"
"$PY" tools/make_demo_arena.py roblox/demo
rojo build YamiSkills.project.json -o "$ROOT/Roblox/1_ReplicatedStorage_YamiSkills.rbxm"
rojo build YamiSkillsServer.project.json -o "$ROOT/Roblox/2_ServerScriptService_YamiSkillsServer.rbxm"
rojo build YamiSkillsClient.project.json -o "$ROOT/Roblox/3_StarterPlayerScripts_YamiSkillsClient.rbxm"
rojo build YamiSkillsDemo.project.json -o "$ROOT/Roblox/YamiSkills_Demo.rbxl"
echo "done"
