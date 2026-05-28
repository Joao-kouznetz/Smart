import csv
from pathlib import Path

ROOT = Path('/Users/joaobresser/Documents/Insper/PFE/Smart')
CATALOG_PATH = ROOT / 'mock_supermercado/catalog.csv'
PROMO_PATH = ROOT / 'mock_supermercado/promotions.csv'

def normalize_name(name):
    return name.strip().lower()

def update_promos():
    # Unfortunately I overwrote catalog.csv, so I don't have the original map. 
    # But wait, in dedup_catalog.py, I can recreate the map from git diff or just 
    # use the script logic again? 
    # Wait, dedup_catalog.py already overwrote catalog.csv, so catalog.csv only has the KEPT barcodes.
    pass

if __name__ == '__main__':
    update_promos()
