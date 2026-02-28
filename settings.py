import json
import os

# Pronalazi apsolutnu putanju foldera u kojem se nalazi settings.py
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_PATH = os.path.join(BASE_DIR, 'settings.json')

def load_settings(filePath=DEFAULT_PATH):
    try:
        with open(filePath, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Greška: Fajl nije pronađen na putanji {filePath}")
        # Možeš vratiti prazan dikt ili podrazumevana podešavanja da program ne pukne
        return {}