"""src/ klasöründeki scriptlerden CharacterPack.rbxmx üretir (Studio: Insert from File)."""
import os, glob
here = os.path.dirname(os.path.abspath(__file__))
root = os.path.dirname(here)
def cls(fn):
    if fn.endswith('.server.lua'): return 'Script'
    if fn.endswith('.client.lua'): return 'LocalScript'
    return 'ModuleScript'
ref = [0]
def item(c, n, src=None, ch=''):
    ref[0] += 1
    s = f'<Item class="{c}" referent="RBX{ref[0]}"><Properties><string name="Name">{n}</string>'
    if src is not None:
        assert ']]>' not in src
        s += f'<ProtectedString name="Source"><![CDATA[{src}]]></ProtectedString>'
    return s + '</Properties>' + ch + '</Item>'
inner = ''
for g, l in [('ReplicatedStorage', 'ReplicatedStorage içine taşı'), ('ServerScriptService', 'ServerScriptService içine taşı'), ('StarterPlayerScripts', 'StarterPlayer > StarterPlayerScripts içine taşı')]:
    kids = ''.join(item(cls(f), os.path.basename(f).split('.')[0], open(f).read()) for f in sorted(glob.glob(f'{root}/src/{g}/*.lua')))
    inner += item('Folder', f'{g}  ->  {l}', None, kids)
open(f'{root}/CharacterPack.rbxmx', 'w').write('<roblox xmlns:xmime="http://www.w3.org/2005/05/xmlmime" version="4">' + item('Folder', 'CharacterPack', None, inner) + '</roblox>')
print('CharacterPack.rbxmx yazıldı')
