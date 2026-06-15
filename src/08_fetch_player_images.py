"""
08_fetch_player_images.py
=========================
Télécharge les photos des joueurs depuis Transfermarkt (via player_id_tm)
et les sauvegarde localement dans maquette_site/img/players/.

Pourquoi local :
  • Transfermarkt et SofaScore bloquent le hotlinking (Referer check)
  • Les images locales fonctionnent sans dépendance réseau après le 1er run
  • Aucune API key requise

Usage :
    python 08_fetch_player_images.py            # télécharger tout
    python 08_fetch_player_images.py --limit 50 # tester sur 50 joueurs
    python 08_fetch_player_images.py --reset     # retélécharger même si déjà présent
"""

import sys
import io
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import argparse
import json
import time
from pathlib import Path

import pandas as pd
import requests

SCORES_PATH = Path(__file__).parent.parent / "data" / "master" / "players_scores.csv"
MASTER_PATH = Path(__file__).parent.parent / "data" / "master" / "players_master.csv"
OUTPUT_JSON = Path(__file__).parent.parent / "data" / "player_images.json"
IMAGES_DIR  = Path(__file__).parent.parent / "maquette_site" / "img" / "players"

IMAGES_DIR.mkdir(parents=True, exist_ok=True)

DELAY = 0.5   # secondes entre requêtes

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                  " (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Referer":    "https://www.transfermarkt.com/",   # indispensable pour TM
    "Accept":     "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
})


def tm_image_url(tm_id: int) -> str:
    """URL Transfermarkt portrait big (200×200)."""
    return f"https://img.transfermarkt.com/portrait/big/{tm_id}.jpg"


def download_image(tm_id: int, force: bool = False) -> str | None:
    """
    Télécharge l'image TM et la sauvegarde localement.
    Retourne le chemin relatif pour le navigateur (ex: 'img/players/240306.jpg')
    ou None si l'image n'existe pas / n'est pas valide.
    """
    local_file = IMAGES_DIR / f"{tm_id}.jpg"

    # Déjà téléchargé et valide (> 2 Ko = vraie image, pas placeholder)
    if not force and local_file.exists() and local_file.stat().st_size > 2_000:
        return f"img/players/{tm_id}.jpg"

    url = tm_image_url(tm_id)
    try:
        r = SESSION.get(url, timeout=12)
        if r.status_code == 200 and len(r.content) > 2_000:
            local_file.write_bytes(r.content)
            return f"img/players/{tm_id}.jpg"
        # Image placeholder TM (< 2 Ko) ou 404 → pas de photo pour ce joueur
        return None
    except Exception:
        return None


def main():
    parser = argparse.ArgumentParser(description="Télécharge les photos joueurs depuis TM")
    parser.add_argument("--limit", type=int,   default=None, help="Nb max de joueurs")
    parser.add_argument("--reset", action="store_true",     help="Re-télécharger même si déjà présent")
    args = parser.parse_args()

    print("\n  FootScout — Téléchargement des photos joueurs")
    print("  Source : Transfermarkt (player_id_tm)")
    print("  Destination : maquette_site/img/players/\n")

    if not SCORES_PATH.exists():
        print(f"  ERREUR : {SCORES_PATH} manquant")
        return
    if not MASTER_PATH.exists():
        print(f"  ERREUR : {MASTER_PATH} manquant")
        return

    # Charger les données
    scores = pd.read_csv(SCORES_PATH, encoding="utf-8-sig")[["master_id", "player_name"]].drop_duplicates()
    master = pd.read_csv(MASTER_PATH, encoding="utf-8-sig")[["master_id", "player_id_tm"]].drop_duplicates("master_id")
    df = scores.merge(master, on="master_id", how="left")
    df = df[df["player_id_tm"].notna()].copy()
    df["player_id_tm"] = df["player_id_tm"].astype(int)

    print(f"  Joueurs avec player_id_tm : {len(df)}/{len(scores)}")

    # Charger le cache existant
    cache: dict[str, str | None] = {}
    if OUTPUT_JSON.exists():
        with open(OUTPUT_JSON, encoding="utf-8") as f:
            cache = json.load(f)
        already = sum(1 for v in cache.values() if v)
        print(f"  Cache existant : {len(cache)} entrées ({already} photos)\n")

    # Filtrer les joueurs à traiter
    # On ne skippe que ceux qui ont déjà une image locale valide ("img/players/...")
    # Les null (échecs anciens) et les URLs http (ancien run SofaScore) sont retentés
    if not args.reset:
        done = {name for name, path in cache.items()
                if path and path.startswith("img/")}
        df = df[~df["player_name"].isin(done)]
    if args.limit:
        df = df.head(args.limit)

    print(f"  A télécharger : {len(df)} joueurs\n")
    if df.empty:
        print("  Rien à faire — tout est déjà téléchargé.")
        return

    found = 0
    for i, (_, row) in enumerate(df.iterrows(), 1):
        name   = row["player_name"]
        tm_id  = row["player_id_tm"]

        local_path = download_image(tm_id, force=args.reset)

        if local_path:
            cache[name] = local_path
            found += 1
            print(f"  [{i:4d}] OK  {name:<35} id={tm_id}")
        else:
            cache[name] = None
            print(f"  [{i:4d}] --  {name:<35} id={tm_id} (pas d'image TM)")

        # Sauvegarde intermédiaire toutes les 50 images
        if i % 50 == 0:
            _save_cache(cache)

        time.sleep(DELAY)

    _save_cache(cache)

    total_photos = sum(1 for v in cache.values() if v)
    print(f"\n  Photos téléchargées : {total_photos}/{len(cache)} joueurs")
    print(f"  Fichier : {OUTPUT_JSON}")
    print(f"  Images  : {IMAGES_DIR}")
    print("\n  Relancer 07_export_web.py pour inclure les photos dans players-data.js\n")


def _save_cache(cache: dict):
    with open(OUTPUT_JSON, "w", encoding="utf-8", newline="\n") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
