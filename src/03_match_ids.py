"""
03_match_ids.py
===============
Résout le problème central : un même joueur a des noms différents
selon les sources (ex: "Kylian Mbappe" vs "K. Mbappé" vs "Kylian Mbappé").

Stratégie en 3 passes :
  1. Jointure exacte  : player_name + team (lowercase, strip)
  2. Fuzzy matching   : rapidfuzz sur le nom seul, avec confirmation par équipe
  3. Jointure manuelle: fichier CSV de corrections pour les cas résiduels

Produit : data/processed/id_mapping.csv
    player_name_ss  | player_name_us  | player_name_tm  | master_id
    (SofaScore)     | (Understat)     | (Transfermarkt)  | (UUID unifié)

Usage :
    pip install rapidfuzz
    python 03_match_ids.py
    python 03_match_ids.py --threshold 85   # seuil fuzzy (défaut: 88)
    python 03_match_ids.py --export-unmatched  # exporter les non-matchés
"""

import sys
import io
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import argparse
import hashlib
import re
import unicodedata
from pathlib import Path

import pandas as pd

# ──────────────────────────────────────────────────────────────────
# CONFIG
# ──────────────────────────────────────────────────────────────────

BASE_DIR      = Path(__file__).parent.parent / "data" / "raw"
PROCESSED_DIR = Path(__file__).parent.parent / "data" / "processed"
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

FUZZY_THRESHOLD = 88   # score minimum (0-100) pour accepter un match flou
MANUAL_FILE     = Path("data/manual_corrections.csv")


# ──────────────────────────────────────────────────────────────────
# NORMALISATION DES NOMS
# ──────────────────────────────────────────────────────────────────

def normalize_name(name: str) -> str:
    """
    Normalise un nom de joueur pour la comparaison :
    - Supprime les accents
    - Minuscules
    - Supprime la ponctuation et les tirets
    - Supprime les points après initiales (K. → k)
    - Strip
    """
    if not isinstance(name, str):
        return ""
    # Décomposer les caractères accentués
    nfkd = unicodedata.normalize("NFKD", name)
    ascii_str = "".join(c for c in nfkd if not unicodedata.combining(c))
    # Minuscules
    s = ascii_str.lower()
    # Supprimer les points, tirets → espace
    s = re.sub(r"[.\-']", " ", s)
    # Supprimer la ponctuation restante
    s = re.sub(r"[^a-z0-9 ]", "", s)
    # Normaliser les espaces
    s = re.sub(r"\s+", " ", s).strip()
    return s


def normalize_team(team: str) -> str:
    """Normalise un nom d'équipe pour la comparaison."""
    if not isinstance(team, str):
        return ""
    s = team.lower()
    # Supprimer les articles et préfixes courants
    for prefix in ["fc ", "ac ", "as ", "ss ", "sc ", "rc ", "vfb ",
                   "rb ", "bsc ", "afc ", "cf ", "cd ", "ud "]:
        s = s.replace(prefix, "")
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def make_master_id(name_normalized: str, team_normalized: str) -> str:
    """Génère un ID unique déterministe à partir du nom + équipe normalisés."""
    key = f"{name_normalized}|{team_normalized}"
    return hashlib.md5(key.encode()).hexdigest()[:12]


# ──────────────────────────────────────────────────────────────────
# CHARGEMENT DES SOURCES
# ──────────────────────────────────────────────────────────────────

def load_sources() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Charge les 3 sources et retourne les DataFrames avec colonnes normalisées."""

    # SofaScore — source principale
    ss_path = BASE_DIR / "sofascore" / "ALL_season_total.csv"
    df_ss = pd.read_csv(ss_path, encoding="utf-8-sig") if ss_path.exists() else pd.DataFrame()
    if not df_ss.empty:
        # Trouver la colonne nom joueur (ScraperFC peut varier selon la version)
        _ss_name = next(
            (c for c in ["player_name", "name", "playerName", "player", "fullName"]
             if c in df_ss.columns), None
        )
        _ss_team = next(
            (c for c in ["team_name", "teamName", "team", "Team"] if c in df_ss.columns),
            None
        )
        if _ss_name is None:
            print(f"  ❌  SofaScore : colonne nom introuvable.")
            print(f"     Colonnes disponibles : {list(df_ss.columns)}")
            print("     → Consulter data/raw/sofascore/season/_diag_*.csv pour voir la structure brute")
            df_ss = pd.DataFrame()
        else:
            if _ss_name != "player_name":
                df_ss = df_ss.rename(columns={_ss_name: "player_name"})
            if _ss_team and _ss_team != "team_name":
                df_ss = df_ss.rename(columns={_ss_team: "team_name"})
            df_ss["_name_norm"] = df_ss["player_name"].apply(normalize_name)
            df_ss["_team_norm"] = df_ss.get("team_name", pd.Series(dtype=str)).apply(normalize_team)
            df_ss["_league"]    = df_ss.get("league", "")
            print(f"  SofaScore     : {len(df_ss):>5} joueurs chargés  (col nom='{_ss_name}')")

    # Understat
    us_path = BASE_DIR / "understat" / "ALL_players_season.csv"
    df_us = pd.read_csv(us_path, encoding="utf-8-sig") if us_path.exists() else pd.DataFrame()
    if not df_us.empty:
        df_us["_name_norm"] = df_us["player"].apply(normalize_name)
        df_us["_team_norm"] = df_us.get("team", pd.Series(dtype=str)).apply(normalize_team)
        df_us["_league"]    = df_us.get("league", "")
        print(f"  Understat     : {len(df_us):>5} joueurs chargés")

    # Transfermarkt
    tm_path = BASE_DIR / "transfermarkt" / "ALL_profiles.csv"
    df_tm = pd.read_csv(tm_path, encoding="utf-8-sig") if tm_path.exists() else pd.DataFrame()
    if not df_tm.empty:
        _tm_name = next(
            (c for c in ["player", "Name", "name", "playerName"] if c in df_tm.columns), None
        )
        _tm_team = next(
            (c for c in ["team", "Team", "teamName", "club"] if c in df_tm.columns), None
        )
        if _tm_name is None:
            print(f"  ⚠  Transfermarkt : colonne nom introuvable — colonnes : {list(df_tm.columns)}")
            df_tm = pd.DataFrame()
        else:
            if _tm_name != "player":
                df_tm = df_tm.rename(columns={_tm_name: "player"})
            if _tm_team and _tm_team != "team":
                df_tm = df_tm.rename(columns={_tm_team: "team"})
            df_tm["_name_norm"] = df_tm["player"].apply(normalize_name)
            df_tm["_team_norm"] = df_tm.get("team", pd.Series(dtype=str)).apply(normalize_team)
            df_tm["_league"]    = df_tm.get("league", "")
            print(f"  Transfermarkt : {len(df_tm):>5} joueurs chargés  (col nom='{_tm_name}')")

    return df_ss, df_us, df_tm


# ──────────────────────────────────────────────────────────────────
# PASSE 1 — JOINTURE EXACTE
# ──────────────────────────────────────────────────────────────────

def pass1_exact(df_ss: pd.DataFrame, df_us: pd.DataFrame,
                df_tm: pd.DataFrame) -> pd.DataFrame:
    """Jointure exacte sur nom normalisé + équipe normalisée."""
    print("\n  Passe 1 : jointure exacte (nom + équipe)...")

    if df_ss.empty:
        return pd.DataFrame()

    # Base = SofaScore (source principale)
    base = df_ss[["player_name", "_name_norm", "_team_norm", "_league"]].copy()
    base = base.drop_duplicates(subset=["_name_norm", "_team_norm"])

    # Jointure SS → Understat
    if not df_us.empty:
        us_dedup = df_us[["player", "_name_norm", "_team_norm"]].drop_duplicates(
            subset=["_name_norm", "_team_norm"])
        base = base.merge(
            us_dedup.rename(columns={"player": "player_name_us"}),
            on=["_name_norm", "_team_norm"], how="left"
        )
    else:
        base["player_name_us"] = None

    # Jointure SS → Transfermarkt
    if not df_tm.empty:
        tm_dedup = df_tm[["player", "_name_norm", "_team_norm", "player_id"]].drop_duplicates(
            subset=["_name_norm", "_team_norm"])
        base = base.merge(
            tm_dedup.rename(columns={"player": "player_name_tm",
                                      "player_id": "player_id_tm"}),
            on=["_name_norm", "_team_norm"], how="left"
        )
    else:
        base["player_name_tm"] = None
        base["player_id_tm"]   = None

    n_matched_us = base["player_name_us"].notna().sum()
    n_matched_tm = base["player_name_tm"].notna().sum()
    print(f"    SS→Understat    : {n_matched_us}/{len(base)} matchés ({n_matched_us/len(base)*100:.0f}%)")
    print(f"    SS→Transfermarkt: {n_matched_tm}/{len(base)} matchés ({n_matched_tm/len(base)*100:.0f}%)")

    return base


# ──────────────────────────────────────────────────────────────────
# PASSE 2 — FUZZY MATCHING MULTI-STRATÉGIE
# ──────────────────────────────────────────────────────────────────

def extract_lastname(name_norm: str) -> str:
    """Extrait le nom de famille (dernier mot du nom normalisé)."""
    parts = name_norm.split()
    return parts[-1] if parts else name_norm


def best_fuzzy_match(query: str, candidates: list[str],
                     threshold: int, fuzz) -> tuple[int | None, float, str]:
    """
    Essaie 3 métriques et retourne le meilleur match.

    Stratégies :
    1. token_sort_ratio  : robuste aux inversions prénom/nom
    2. partial_ratio     : capture les noms allongés ("Ortega" dans "Ortega Moreno")
    3. token_set_ratio   : capture les noms tronqués ("Gabriel" dans "Gabriel Magalhaes")

    Retourne (index_candidat, score, stratégie) ou (None, 0, "")
    """
    from rapidfuzz import process

    best_idx, best_score, best_strat = None, 0.0, ""

    for scorer, name, cutoff in [
        (fuzz.token_sort_ratio, "token_sort", threshold),
        (fuzz.partial_ratio,    "partial",    max(threshold, 92)),  # plus strict car moins discriminant
        (fuzz.token_set_ratio,  "token_set",  max(threshold, 90)),
    ]:
        result = process.extractOne(query, candidates, scorer=scorer, score_cutoff=cutoff)
        if result and result[1] > best_score:
            best_idx, best_score, best_strat = result[2], result[1], name

    return best_idx, best_score, best_strat


def pass2_fuzzy(base: pd.DataFrame, df_us: pd.DataFrame,
                df_tm: pd.DataFrame, threshold: int = FUZZY_THRESHOLD) -> pd.DataFrame:
    """
    Pour les joueurs non-matchés en passe 1, fuzzy matching multi-stratégie.

    Stratégies dans l'ordre :
    1. token_sort_ratio  (original) — robuste aux inversions prénom/nom
    2. partial_ratio     — capture "Stefan Ortega" dans "Stefan Ortega Moreno"
    3. token_set_ratio   — capture "Gabriel" dans "Gabriel Magalhaes"
    4. Nom de famille uniquement dans la même ligue — capture "Rayan" vs "Mathis" Cherki
    """
    try:
        from rapidfuzz import fuzz
    except ImportError:
        print("  ⚠  rapidfuzz non installé (pip install rapidfuzz) — passe 2 ignorée")
        return base

    print(f"\n  Passe 2 : fuzzy matching multi-stratégie (seuil={threshold})...")

    unmatched_us = base["player_name_us"].isna()
    unmatched_tm = base["player_name_tm"].isna()
    print(f"    Non-matchés US : {unmatched_us.sum()}  |  Non-matchés TM : {unmatched_tm.sum()}")

    # ── SS → Understat ───────────────────────────────────────────────
    if not df_us.empty and unmatched_us.sum() > 0:
        us_names     = df_us["_name_norm"].tolist()
        us_name_orig = df_us["player"].tolist()
        us_teams     = df_us["_team_norm"].tolist()
        us_lastnames = [extract_lastname(n) for n in us_names]

        strat_counts = {"token_sort": 0, "partial": 0, "token_set": 0, "lastname": 0}

        for idx in base[unmatched_us].index:
            query_name   = base.at[idx, "_name_norm"]
            query_team   = base.at[idx, "_team_norm"]
            query_league = base.at[idx, "_league"]

            # Stratégies 1-3 : fuzzy multi-métrique
            best_idx, best_score, best_strat = best_fuzzy_match(
                query_name, us_names, threshold, fuzz
            )

            # Stratégie 4 : nom de famille uniquement dans la même ligue
            if best_idx is None:
                query_lastname = extract_lastname(query_name)
                if len(query_lastname) >= 4:  # éviter les faux positifs sur prénoms courts
                    lastname_hits = [
                        i for i, (ln, team) in enumerate(zip(us_lastnames, us_teams))
                        if ln == query_lastname and (
                            team == query_team or           # même équipe exacte
                            fuzz.partial_ratio(team, query_team) >= 80  # ou équipe proche
                        )
                    ]
                    if len(lastname_hits) == 1:
                        best_idx   = lastname_hits[0]
                        best_score = 90.0
                        best_strat = "lastname"

            if best_idx is not None:
                base.at[idx, "player_name_us"]     = us_name_orig[best_idx]
                base.at[idx, "_fuzzy_score_us"]    = round(best_score, 1)
                base.at[idx, "_matched_via_fuzzy"] = True
                strat_counts[best_strat] = strat_counts.get(best_strat, 0) + 1

        total = sum(strat_counts.values())
        print(f"    Fuzzy US résolus : {total}  "
              f"(token_sort={strat_counts['token_sort']} | "
              f"partial={strat_counts['partial']} | "
              f"token_set={strat_counts['token_set']} | "
              f"lastname={strat_counts['lastname']})")

    # ── SS → Transfermarkt ───────────────────────────────────────────
    if not df_tm.empty and unmatched_tm.sum() > 0:
        tm_names     = df_tm["_name_norm"].tolist()
        tm_name_orig = df_tm["player"].tolist()
        tm_ids       = df_tm.get("player_id", pd.Series(dtype=str)).tolist()
        tm_teams     = df_tm["_team_norm"].tolist()
        tm_lastnames = [extract_lastname(n) for n in tm_names]

        strat_counts = {"token_sort": 0, "partial": 0, "token_set": 0, "lastname": 0}

        for idx in base[unmatched_tm].index:
            query_name = base.at[idx, "_name_norm"]
            query_team = base.at[idx, "_team_norm"]

            best_idx, best_score, best_strat = best_fuzzy_match(
                query_name, tm_names, threshold, fuzz
            )

            if best_idx is None:
                query_lastname = extract_lastname(query_name)
                if len(query_lastname) >= 4:
                    lastname_hits = [
                        i for i, (ln, team) in enumerate(zip(tm_lastnames, tm_teams))
                        if ln == query_lastname and (
                            team == query_team or
                            fuzz.partial_ratio(team, query_team) >= 80
                        )
                    ]
                    if len(lastname_hits) == 1:
                        best_idx   = lastname_hits[0]
                        best_score = 90.0
                        best_strat = "lastname"

            if best_idx is not None:
                base.at[idx, "player_name_tm"]     = tm_name_orig[best_idx]
                base.at[idx, "player_id_tm"]       = tm_ids[best_idx] if best_idx < len(tm_ids) else None
                base.at[idx, "_fuzzy_score_tm"]    = round(best_score, 1)
                base.at[idx, "_matched_via_fuzzy"] = True
                strat_counts[best_strat] = strat_counts.get(best_strat, 0) + 1

        total = sum(strat_counts.values())
        print(f"    Fuzzy TM résolus : {total}  "
              f"(token_sort={strat_counts['token_sort']} | "
              f"partial={strat_counts['partial']} | "
              f"token_set={strat_counts['token_set']} | "
              f"lastname={strat_counts['lastname']})")

    return base


# ──────────────────────────────────────────────────────────────────
# PASSE 3 — CORRECTIONS MANUELLES
# ──────────────────────────────────────────────────────────────────

def pass3_manual(base: pd.DataFrame) -> pd.DataFrame:
    """Applique un fichier CSV de corrections manuelles si disponible."""
    if not MANUAL_FILE.exists():
        print(f"\n  Passe 3 : pas de fichier de corrections manuelles ({MANUAL_FILE})")
        print("    → Créer ce fichier avec les colonnes :")
        print("      player_name_ss, player_name_us_correct, player_name_tm_correct")
        return base

    corrections = pd.read_csv(MANUAL_FILE)
    print(f"\n  Passe 3 : {len(corrections)} corrections manuelles appliquées")

    for _, row in corrections.iterrows():
        mask = base["player_name"] == row["player_name_ss"]
        if mask.any():
            if pd.notna(row.get("player_name_us_correct")):
                base.loc[mask, "player_name_us"] = row["player_name_us_correct"]
            if pd.notna(row.get("player_name_tm_correct")):
                base.loc[mask, "player_name_tm"] = row["player_name_tm_correct"]

    return base


# ──────────────────────────────────────────────────────────────────
# GÉNÉRATION DU MASTER ID
# ──────────────────────────────────────────────────────────────────

def generate_master_ids(base: pd.DataFrame) -> pd.DataFrame:
    """Génère un identifiant unique stable pour chaque joueur."""
    base["master_id"] = base.apply(
        lambda r: make_master_id(r["_name_norm"], r["_team_norm"]),
        axis=1
    )
    # Vérif unicité
    n_dup = base["master_id"].duplicated().sum()
    if n_dup > 0:
        print(f"  ⚠  {n_dup} master_id dupliqués — collision possible (noms/équipes trop similaires)")
    else:
        print(f"  ✅  {len(base)} master_id uniques générés")
    return base


# ──────────────────────────────────────────────────────────────────
# EXPORT
# ──────────────────────────────────────────────────────────────────

def export_mapping(base: pd.DataFrame, export_unmatched: bool = False):
    """Exporte la table de mapping et les non-matchés."""

    # Colonnes de sortie
    output_cols = [
        "master_id", "player_name", "player_name_us", "player_name_tm",
        "player_id_tm", "_name_norm", "_team_norm", "_league",
        "_fuzzy_score_us", "_fuzzy_score_tm", "_matched_via_fuzzy",
    ]
    output_cols_present = [c for c in output_cols if c in base.columns]
    df_out = base[output_cols_present].copy()

    out_path = PROCESSED_DIR / "id_mapping.csv"
    df_out.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"\n  ✅  Mapping sauvegardé : {out_path}  ({len(df_out)} joueurs)")

    # Stats finales
    if "player_name_us" in df_out.columns:
        n = df_out["player_name_us"].notna().sum()
        print(f"     Matchés avec Understat    : {n}/{len(df_out)} ({n/len(df_out)*100:.0f}%)")
    if "player_name_tm" in df_out.columns:
        n = df_out["player_name_tm"].notna().sum()
        print(f"     Matchés avec Transfermarkt: {n}/{len(df_out)} ({n/len(df_out)*100:.0f}%)")

    if export_unmatched:
        unmatched = df_out[
            df_out.get("player_name_us", pd.Series(dtype=str)).isna() |
            df_out.get("player_name_tm", pd.Series(dtype=str)).isna()
        ]
        um_path = PROCESSED_DIR / "unmatched_players.csv"
        unmatched.to_csv(um_path, index=False, encoding="utf-8-sig")
        print(f"  ⚠  Non-matchés exportés : {um_path}  ({len(unmatched)} joueurs)")
        print("     → Compléter data/manual_corrections.csv puis relancer 03_match_ids.py")


# ──────────────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Matching des identités inter-sources")
    parser.add_argument("--threshold",        type=int, default=FUZZY_THRESHOLD,
                        help=f"Seuil fuzzy matching (défaut: {FUZZY_THRESHOLD})")
    parser.add_argument("--export-unmatched", action="store_true",
                        help="Exporter les joueurs non-matchés dans un CSV")
    args = parser.parse_args()

    print("\n" + "═" * 55)
    print("  MATCHING DES IDENTITÉS — Football Scoring Project")
    print("═" * 55)

    df_ss, df_us, df_tm = load_sources()

    if df_ss.empty:
        print("  ❌  SofaScore vide — relancer 01_extract.py")
        return

    base = pass1_exact(df_ss, df_us, df_tm)
    base = pass2_fuzzy(base, df_us, df_tm, threshold=args.threshold)
    base = pass3_manual(base)
    base = generate_master_ids(base)

    export_mapping(base, export_unmatched=args.export_unmatched)

    print("\n" + "═" * 55)
    print("  Prochaine étape : python 04_merge.py")
    print("═" * 55 + "\n")


if __name__ == "__main__":
    main()
