import json, sys
sys.path.insert(0, '.')
from report_parser import parse_synthesis_json

path = r'uploads\runs\758f8e73-3ce8-4484-8747-a93e9c94c2b7\synth.json'

with open(path, 'r', encoding='utf-8', errors='replace') as f:
    data = json.load(f)

print('Modules found:', list(data.get('modules', {}).keys()))
for mod_name, mod_data in data.get('modules', {}).items():
    cells = mod_data.get('cells', {})
    print(f'  {mod_name}: {len(cells)} cells, {len(mod_data.get("netnames",{}))} wires')
    for cell_name, cell_data in list(cells.items())[:5]:
        print(f'    type={cell_data.get("type")}')

print()
print('parse_synthesis_json result:', json.dumps(parse_synthesis_json(path), indent=2))
