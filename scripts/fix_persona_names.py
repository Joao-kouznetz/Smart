import csv
import json
from pathlib import Path

ROOT = Path('/Users/joaobresser/Documents/Insper/PFE/Smart')
CATALOG_PATH = ROOT / 'mock_supermercado/catalog.csv'
PERSONAS_PATH = ROOT / 'mock_supermercado/simulation/personas.py'

def fix_persona_names():
    with open(CATALOG_PATH, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        catalog = {row['barcode']: row['name'] for row in reader}

    with open(PERSONAS_PATH, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    for i, line in enumerate(lines):
        if '"barcode":' in line and '"name":' in line:
            # simple parse
            parts = line.split('"barcode": "')
            if len(parts) > 1:
                bc = parts[1].split('"')[0]
                if bc in catalog:
                    correct_name = catalog[bc]
                    # replace name
                    import re
                    lines[i] = re.sub(r'"name":\s*"[^"]+"', f'"name": "{correct_name}"', line)

    with open(PERSONAS_PATH, 'w', encoding='utf-8') as f:
        f.writelines(lines)
        
if __name__ == '__main__':
    fix_persona_names()
