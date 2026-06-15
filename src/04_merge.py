"""
04_merge.py
===========
Construit la table maître unifiée en joignant toutes les sources
via la table de mapping produite par 03_match_ids.py.

Produit : data/master/players_master.csv
    Une ligne par joueur, toutes les features de toutes les sources.

Usage :
    python 04_merge.py
"""

import sys
import io
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import json
from pathlib import Path
import pandas as pd

# ──────────────────────────────────────────────────────────────────
BASE_DIR      = Path(__file__).parent.parent / "data" / "raw"
PROCESSED_DIR = Path(__file__).parent.parent / "data" / "processed"
MASTER_DIR    = Path(__file__).parent.parent / "data" / "master"
MASTER_DIR.mkdir(parents=True, exist_ok=True)

MIN_MINUTES = 450

# ──────────────────────────────────────────────────────────────────
# MAPPING POSITIONS → 8 GROUPES STANDARDISÉS (CHANGEMENT 1)
# ──────────────────────────────────────────────────────────────────

TM_POSITION_MAP: dict[str, list[str]] = {
    # Gardien
    "Goalkeeper":              ["GK"],
    "Sweeper Keeper":          ["GK"],
    # Défenseurs
    "Centre-Back":             ["CB"],
    "Left-Back":               ["FB"],
    "Right-Back":              ["FB"],
    "Wing-Back":               ["FB"],
    "Left Wing-Back":          ["FB"],
    "Right Wing-Back":         ["FB"],
    "Sweeper":                 ["CB"],
    # Milieux défensifs
    "Defensive Midfield":      ["DM"],
    # Milieux centraux
    "Central Midfield":        ["CM"],
    # Milieux offensifs
    "Attacking Midfield":      ["AM"],
    "Shadow Striker":          ["AM"],
    # Ailiers
    "Left Winger":             ["W"],
    "Right Winger":            ["W"],
    "Left Midfield":           ["W"],   # milieu-ailier gauche
    "Right Midfield":          ["W"],   # milieu-ailier droit
    # Attaquants
    "Centre-Forward":          ["CF"],
    "Second Striker":          ["CF"],
    "False 9":                 ["CF"],
    "Target Man":              ["CF"],
    # Positions génériques TM (fallback)
    "Midfielder":              ["CM"],
    "Defender":                ["CB"],
    "Forward":                 ["CF"],
    "Striker":                 ["CF"],
    "Winger":                  ["W"],
    "Fullback":                ["FB"],
}

SS_POSITION_FALLBACK: dict[str, list[str]] = {
    "GK": ["GK"], "G": ["GK"],
    "D":  ["CB"], "CB": ["CB"],
    "LB": ["FB"], "RB": ["FB"], "WB": ["FB"],
    "DM": ["DM"], "CDM": ["DM"],
    "CM": ["CM"], "M":   ["CM"],
    "AM": ["AM"], "CAM": ["AM"],
    "LW": ["W"],  "RW":  ["W"],
    "F":  ["CF"], "ST":  ["CF"], "CF": ["CF"], "Forward": ["CF"],
}


def build_postes_list(row) -> str:
    """
    Construit postes_list (JSON) depuis la position TM (avec fallback SofaScore).
    TM peut retourner "Central Midfield / Defensive Midfield" — on parse chaque partie.
    Retourne une liste JSON des codes de postes standardisés (GK/CB/FB/DM/CM/AM/W/CF).
    """
    postes: list[str] = []

    pos_tm = row.get("position_tm", "")
    if isinstance(pos_tm, str) and pos_tm.strip():
        for part in pos_tm.split("/"):
            part = part.strip()
            for p in TM_POSITION_MAP.get(part, []):
                if p not in postes:
                    postes.append(p)

    if not postes:
        pos_ss = row.get("position", "")
        if isinstance(pos_ss, str) and pos_ss.strip():
            for p in SS_POSITION_FALLBACK.get(pos_ss.strip(), []):
                if p not in postes:
                    postes.append(p)

    return json.dumps(postes if postes else ["CM"])


def load(path: Path) -> pd.DataFrame:
    if not path.exists():
        print(f"  ⚠  Fichier manquant : {path}")
        return pd.DataFrame()
    return pd.read_csv(path, encoding="utf-8-sig")


def main():
    print("\n" + "═" * 55)
    print("  MERGE MASTER TABLE — Football Scoring Project")
    print("═" * 55)

    # ── Charger les sources
    mapping    = load(PROCESSED_DIR / "id_mapping.csv")
    df_ss_tot  = load(BASE_DIR / "sofascore"    / "ALL_season_total.csv")
    df_ss_p90  = load(BASE_DIR / "sofascore"    / "ALL_season_per90.csv")
    df_us      = load(BASE_DIR / "understat"    / "ALL_players_season.csv")
    df_us_team = load(BASE_DIR / "understat"    / "ALL_teams_season.csv")
    df_tm      = load(BASE_DIR / "transfermarkt"/ "ALL_profiles.csv")

    if mapping.empty or df_ss_tot.empty:
        print("  ❌  Mapping ou SofaScore manquants — relancer 03_match_ids.py")
        return

    # ── Base : SofaScore total (stats brutes)
    master = df_ss_tot.copy()

    # Ajouter master_id via mapping
    if "player_name" in master.columns and "player_name" in mapping.columns:
        master = master.merge(
            mapping[["player_name", "master_id", "player_name_us", "player_name_tm", "player_id_tm"]],
            on="player_name", how="left"
        )
        print(f"  ✅  Base SofaScore : {len(master)} joueurs")

    # ── Ajouter les stats per90 SofaScore (suffixe _p90)
    if not df_ss_p90.empty and "player_name" in df_ss_p90.columns:
        stat_cols = [c for c in df_ss_p90.columns
                     if c not in ("player_name", "team_name", "position", "league",
                                   "season", "appearances", "minutesPlayed")]
        df_ss_p90_join = df_ss_p90[["player_name", "league"] + stat_cols].copy()
        df_ss_p90_join = df_ss_p90_join.rename(
            columns={c: f"{c}_p90" for c in stat_cols}
        )
        master = master.merge(df_ss_p90_join, on=["player_name", "league"], how="left")
        print(f"  ✅  Stats per90 ajoutées ({len(stat_cols)} colonnes)")

    # ── Ajouter les features Understat (xGChain, xGBuildup, shots, xA)
    if not df_us.empty and "player" in df_us.columns and "player_name_us" in master.columns:
        us_cols = [c for c in ["player", "shots", "xGChain", "xGBuildup", "xA"]
                   if c in df_us.columns]
        df_us_join = df_us[us_cols].drop_duplicates(subset=["player"])
        df_us_join = df_us_join.rename(columns={
            "player": "player_name_us",
            "shots":  "shots_us",
            "xA":     "xA_us",
        })
        rename_map = {c: f"{c}_us" for c in ["xGChain", "xGBuildup"]
                      if c in df_us_join.columns}
        df_us_join = df_us_join.rename(columns=rename_map)

        master = master.merge(df_us_join, on="player_name_us", how="left")
        n_matched = master["xGChain_us"].notna().sum() if "xGChain_us" in master.columns else 0
        print(f"  ✅  Understat joint : {n_matched}/{len(master)} joueurs avec xGChain/xGBuildup/shots")

    # ── Ajouter le contexte équipe Understat (PPDA, xG équipe)
    if not df_us_team.empty and "team" in df_us_team.columns and "team_name" in master.columns:
        ppda_cols = [c for c in ["team", "ppda", "oppda", "deep", "odc",
                                  "xg", "xg_against", "np_xg", "xp"]
                     if c in df_us_team.columns]
        df_ppda = df_us_team[ppda_cols].drop_duplicates(subset=["team"])
        df_ppda = df_ppda.rename(columns={"team": "team_name"})
        team_merge_cols = [c for c in df_ppda.columns if c != "team_name"]
        master = master.merge(df_ppda[["team_name"] + team_merge_cols], on="team_name", how="left")
        n_ppda = master["ppda"].notna().sum() if "ppda" in master.columns else 0
        print(f"  ✅  PPDA équipe joint : {n_ppda}/{len(master)} joueurs")

    # ── Ajouter le profil Transfermarkt (poste, pied, valeur)
    if not df_tm.empty and "player" in df_tm.columns and "player_name_tm" in master.columns:
        tm_cols = [c for c in ["player", "position", "age", "height",
                                "nationality", "market_value", "contract_expires",
                                "date_of_birth", "joined", "signed_from"]
                   if c in df_tm.columns]
        df_tm_join = df_tm[tm_cols].drop_duplicates(subset=["player"])
        df_tm_join = df_tm_join.rename(columns={
            "player":   "player_name_tm",
            "position": "position_tm",
            "age":      "age_tm",
        })
        master = master.merge(df_tm_join, on="player_name_tm", how="left")
        n_tm = master["market_value"].notna().sum() if "market_value" in master.columns else 0
        print(f"  ✅  Transfermarkt joint : {n_tm}/{len(master)} joueurs avec valeur marchande")

    # ── Construire postes_list (8 groupes standardisés, CHANGEMENT 1)
    master["postes_list"] = master.apply(build_postes_list, axis=1)
    n_multi = (master["postes_list"]
               .apply(json.loads)
               .apply(len)
               .gt(1)
               .sum())
    n_tm = master["postes_list"].apply(
        lambda x: json.loads(x) != ["CM"]
    ).sum()
    print(f"  ✅  postes_list : {n_tm}/{len(master)} joueurs avec poste TM/SS identifié")
    print(f"                   {n_multi} joueurs avec plusieurs postes")

    # ── Ajouter les positions moyennes SofaScore (averageX / averageY)
    pos_files = list((BASE_DIR / "sofascore" / "positions").glob("*_avg_positions.csv"))
    if pos_files:
        df_pos = pd.concat([load(f) for f in pos_files], ignore_index=True)
        if not df_pos.empty and "player_name" in df_pos.columns:
            df_pos_agg = (
                df_pos.groupby("player_name")[["averageX", "averageY"]]
                .mean()
                .reset_index()
            )
            master = master.merge(df_pos_agg, on="player_name", how="left")
            n_pos = master["averageX"].notna().sum()
            print(f"  ✅  Positions moyennes jointées : {n_pos}/{len(master)} joueurs")

    # ── Filtre temps de jeu
    if "minutesPlayed" in master.columns:
        before = len(master)
        master = master[master["minutesPlayed"] >= MIN_MINUTES]
        print(f"  ✅  Filtre ≥{MIN_MINUTES} min : {before} → {len(master)} joueurs")

    # ── Supprimer les colonnes internes de matching
    internal_cols = [c for c in master.columns if c.startswith("_")]
    master = master.drop(columns=internal_cols, errors="ignore")

    # ── Dédupliquer
    before = len(master)
    # 1. Supprimer les lignes strictement identiques (bug de join TM/mapping)
    master = master.drop_duplicates(subset=["player_name", "team_name", "minutesPlayed"])
    # 2. Pour les joueurs transférés (plusieurs clubs), garder le club avec le + de minutes
    master = (
        master
        .sort_values("minutesPlayed", ascending=False)
        .drop_duplicates(subset=["player_name"], keep="first")
        .sort_index()
    )
    after = len(master)
    print(f"  ✅  Déduplication : {before} → {after} joueurs "
          f"({before - after} doublons supprimés)")

    # ── Sauvegarder
    out_path = MASTER_DIR / "players_master.csv"
    master.to_csv(out_path, index=False, encoding="utf-8-sig")

    print(f"\n  ✅  Table maître : {out_path}")
    print(f"     {len(master)} joueurs  ×  {len(master.columns)} colonnes")
    print(f"\n  Ligues : {sorted(master['league'].unique()) if 'league' in master.columns else 'N/A'}")
    if "postes_list" in master.columns:
        from collections import Counter
        all_postes = [p for pl in master["postes_list"].apply(json.loads) for p in pl]
        print(f"  Distribution postes_list : {dict(Counter(all_postes))}")

    print("\n" + "═" * 55)
    print("  Prochaine étape : python 05_features.py")
    print("═" * 55 + "\n")


if __name__ == "__main__":
    main()
