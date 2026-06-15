"""
06_scoring.py
=============
Affichage et ranking des scores par rôle tactique.

Les scores sont calculés par 05_features_v2.py (CHANGEMENT 5).
Ce script lit players_scores.csv et permet d'explorer les résultats.

Usage :
    python 06_scoring.py
    python 06_scoring.py --role gardien_classique
    python 06_scoring.py --role box_to_box --top 15
    python 06_scoring.py --player "Kylian Mbappé"
    python 06_scoring.py --list-roles
"""

import sys
import io
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

SCORES_PATH = Path(__file__).parent.parent / "data" / "master" / "players_scores.csv"

ALL_ROLES = [
    # GK
    "gardien_classique", "gardien_libero", "gardien_relanceur",
    # CB
    "defenseur_central", "stoppeur", "libero_defensif",
    "tour_de_controle", "relanceur",
    # FB
    "lateral_classique", "piston", "defenseur_lateral",
    "lateral_inverse", "lateral_pressing",
    # DM
    "sentinelle", "recuperateur_DM", "meneur_jeu_recule_DM",
    # CM
    "recuperateur_CM", "box_to_box", "meneur_jeu_offensif_CM", "meneur_jeu_recule_CM",
    # AM
    "electron_libre", "meneur_jeu_offensif_AM",
    # W
    "interieur", "profondeur_W", "percuteur", "excentre", "ailier_defensif",
    # CF
    "profondeur_CF", "pivot", "faux_9", "renard_surfaces", "attaquant_pressing",
]

ROLE_TO_POSTE = {
    "gardien_classique": "GK", "gardien_libero": "GK", "gardien_relanceur": "GK",
    "defenseur_central": "CB", "stoppeur": "CB", "libero_defensif": "CB",
    "tour_de_controle": "CB", "relanceur": "CB",
    "lateral_classique": "FB", "piston": "FB", "defenseur_lateral": "FB",
    "lateral_inverse": "FB", "lateral_pressing": "FB",
    "sentinelle": "DM", "recuperateur_DM": "DM", "meneur_jeu_recule_DM": "DM",
    "recuperateur_CM": "CM", "box_to_box": "CM",
    "meneur_jeu_offensif_CM": "CM", "meneur_jeu_recule_CM": "CM",
    "electron_libre": "AM", "meneur_jeu_offensif_AM": "AM",
    "interieur": "W", "profondeur_W": "W", "percuteur": "W",
    "excentre": "W", "ailier_defensif": "W",
    "profondeur_CF": "CF", "pivot": "CF", "faux_9": "CF",
    "renard_surfaces": "CF", "attaquant_pressing": "CF",
}



def print_top(df: pd.DataFrame, role: str, top_n: int = 20):
    col = f"score_{role}"
    if col not in df.columns:
        print(f"  ❌  Colonne '{col}' absente — relancer 05_features_v2.py")
        return

    sub = df[df[col].notna()].sort_values(col, ascending=False)
    if sub.empty:
        print(f"  Aucun joueur scoré pour le rôle '{role}'")
        return

    top = sub.head(top_n)
    poste = ROLE_TO_POSTE.get(role, "?")
    print(f"\n  TOP {top_n} — {role}  (poste: {poste})  [{len(sub)} joueurs éligibles]\n")
    print(f"  {'#':<4} {'Joueur':<28} {'Équipe':<24} {'Ligue':<24} {'Score':>6}")
    print("  " + "─" * 90)
    for i, (_, r) in enumerate(top.iterrows(), 1):
        league = str(r.get("league", ""))[:22]
        team   = str(r.get("team_name", ""))[:22]
        name   = str(r.get("player_name", ""))[:26]
        score  = f"{r[col]:.1f}"
        print(f"  {i:<4} {name:<28} {team:<24} {league:<24} {score:>6}")


def print_player(df: pd.DataFrame, player_name: str):
    mask = df["player_name"].str.contains(player_name, case=False, na=False)
    sub  = df[mask]
    if sub.empty:
        print(f"  Joueur '{player_name}' non trouvé.")
        return

    for _, r in sub.iterrows():
        postes = r.get("postes_list", "[]")
        if isinstance(postes, str):
            postes = json.loads(postes)

        print(f"\n  {r['player_name']} — {r.get('team_name', '?')} ({r.get('league', '?')})")
        print(f"  Postes : {postes}  |  fm_role_primary : {r.get('fm_role', '?')}")
        print(f"  Minutes: {r.get('minutesPlayed', '?')}")
        print(f"\n  Scores par rôle :")

        scores = []
        for role in ALL_ROLES:
            col = f"score_{role}"
            val = r.get(col, np.nan)
            if pd.notna(val):
                scores.append((role, val))

        scores.sort(key=lambda x: x[1], reverse=True)
        for role, val in scores:
            bar = "▓" * int(val / 10)
            print(f"    {role:<32} {val:>5.1f}  {bar}")


def main():
    parser = argparse.ArgumentParser(description="Affichage scores rôles FM v2")
    parser.add_argument("--role",       type=str,   default=None,
                        help="Afficher le top d'un rôle (ex: box_to_box)")
    parser.add_argument("--top",        type=int,   default=20,
                        help="Nombre de joueurs (défaut: 20)")
    parser.add_argument("--player",     type=str,   default=None,
                        help="Détail d'un joueur")
    parser.add_argument("--list-roles", action="store_true",
                        help="Lister tous les rôles disponibles")
    args = parser.parse_args()

    print("\n" + "═" * 65)
    print("  SCORING v2 — Football Scoring Project")
    print("═" * 65)

    if args.list_roles:
        print("\n  Rôles disponibles (35 rôles) :\n")
        current_poste = None
        for role in ALL_ROLES:
            poste = ROLE_TO_POSTE.get(role, "?")
            if poste != current_poste:
                print(f"\n  [{poste}]")
                current_poste = poste
            print(f"    {role}")
        print()
        return

    if not SCORES_PATH.exists():
        print(f"  ❌  Fichier manquant : {SCORES_PATH}")
        print("      Relancer : python 05_features_v2.py")
        return

    df = pd.read_csv(SCORES_PATH, encoding="utf-8-sig")
    print(f"  Chargement : {len(df)} joueurs × {len(df.columns)} colonnes")

    score_cols = [c for c in df.columns if c.startswith("score_")]
    print(f"  Colonnes de scores : {len(score_cols)} rôles")

    # Stats globales
    print(f"\n  {'Rôle':<32} {'Éligibles':>10} {'Score moy':>10} {'Score med':>10}")
    print("  " + "─" * 66)
    for role in ALL_ROLES:
        col = f"score_{role}"
        if col not in df.columns:
            continue
        sub = df[col].dropna()
        if sub.empty:
            continue
        print(f"  {role:<32} {len(sub):>10} {sub.mean():>10.1f} {sub.median():>10.1f}")

    if args.role:
        print_top(df, args.role.lower(), args.top)

    if args.player:
        print_player(df, args.player)

    if not args.role and not args.player:
        print("\n  TOP 3 par rôle :")
        for role in ALL_ROLES:
            col = f"score_{role}"
            if col not in df.columns:
                continue
            sub = df[col].dropna()
            if sub.empty:
                continue
            top3 = df.nlargest(3, col)[["player_name", "team_name", col]]
            names = ", ".join(
                f"{r['player_name']} ({r[col]:.0f})"
                for _, r in top3.iterrows()
            )
            print(f"  {role:<32} {names}")

    print("\n" + "═" * 65)
    print("  Commandes utiles :")
    print("    python 06_scoring.py --list-roles")
    print("    python 06_scoring.py --role box_to_box")
    print("    python 06_scoring.py --role gardien_classique --top 10")
    print('    python 06_scoring.py --player "Mbappé"')
    print("═" * 65 + "\n")


if __name__ == "__main__":
    main()
