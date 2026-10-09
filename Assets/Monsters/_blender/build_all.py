"""Uc canavari da sirayla uretir: .blend + .fbx + renders/*.png

Gereken:  pip install bpy==5.2.2   (Blender'i Python modulu olarak kurar)
Calistir: python build_all.py [--preview]
Ya da Blender ile: blender -b -P fisilti.py  (her betik tek basina da calisir)
"""

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

for script in ("fisilti.py", "geri_donen.py", "bakan.py"):
    print(f"==> {script}", flush=True)
    subprocess.run([sys.executable, os.path.join(HERE, script), *sys.argv[1:]], check=True)
