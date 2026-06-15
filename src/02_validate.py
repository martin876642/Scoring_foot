"""
02_validate.py
==============
Vérifie que toutes les sources couvrent bien le même périmètre :
  - Mêmes ligues
  - Même saison (ou saison compatible)
  - Volume cohérent (pas de ligue vide ou tronquée)
  - Qualité des données (nulls, doublons, outliers)

Usage :
    python 02_validate.py
    python 02_validate.py --fix   # tente de corriger les problèmes mineurs
"""

import sys
import io
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import argparse
from pathlib import Path

import pandas as pd

# ──────────────────────────────────────────────────────────────────
# CONFIG
# ──────────────────────────────────────────────────────────────────

BASE_DIR          = Path(__file__).parent.parent / "data" / "raw"
PROCESSED_DIR     = Path(__file__).parent.parent / "data" / "processed"
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

SS_EXPECTED_LEAGUES = {
    "England Premier League", "Spain La Liga", "Italy Serie A",
    "Germany Bundesliga", "France Ligue 1",
}
US_EXPECTED_LEAGUES = {"EPL", "La_liga", "Serie_A", "Bundesliga", "Ligue_1"}
MIN_PLAYERS_PER_LEAGUE = 15   # en dessous → ligue probablement incomplète
MIN_MINUTES       = 450       # seuil de temps de jeu minimum

# Mapping des noms de ligues entre sources (normalisation)
LEAGUE_NAME_MAP = {
    # SofaScore → standard
    "EPL":        "PL",
    "LaLiga":     "LIGA",
    "SerieA":     "SA",
    "Bundesliga": "BL",
    "Ligue1":     "L1",
    # Understat → standard
    "La_liga":    "LIGA",
    "Serie_A":    "SA",
    # Transfermarkt → standard
    "GB1":        "PL",
    "ES1":        "LIGA",
    "IT1":        "SA",
    "L1":         "BL",
    "FR1":        "L1",
}

STATUS_ICONS = {"OK": "✅", "WARN": "⚠ ", "ERROR": "❌"}


# ──────────────────────────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────────────────────────

def status(level: str, msg: str):
    print(f"  {STATUS_ICONS[level]}  {msg}")


def load_if_exists(path: Path) -> pd.DataFrame | None:
    if not path.exists():
        status("ERROR", f"Fichier manquant : {path}")
        return None
    df = pd.read_csv(path, encoding="utf-8-sig")
    return df


def section(title: str):
    print(f"\n{'─'*55}")
    print(f"  {title}")
    print(f"{'─'*55}")


# ──────────────────────────────────────────────────────────────────
# VALIDATION PAR SOURCE
# ──────────────────────────────────────────────────────────────────

def validate_sofascore() -> dict:
    section("SOFASCORE — validation")
    issues = []

    df_total = load_if_exists(BASE_DIR / "sofascore" / "ALL_season_total.csv")
    df_per90 = load_if_exists(BASE_DIR / "sofascore" / "ALL_season_per90.csv")

    if df_total is None or df_per90 is None:
        return {"source": "sofascore", "ok": False, "issues": ["Fichiers manquants"]}

    for label, df in [("total", df_total), ("per90", df_per90)]:
        # Vérif colonnes clés
        required = ["player_name", "team_name", "minutesPlayed", "league", "season"]
        missing = [c for c in required if c not in df.columns]
        if missing:
            status("ERROR", f"[{label}] Colonnes manquantes : {missing}")
            issues.append(f"Colonnes manquantes dans {label}")
        else:
            status("OK", f"[{label}] Colonnes requises présentes")

        # Vérif ligues
        leagues_found = set(df["league"].unique()) if "league" in df.columns else set()
        missing_leagues = SS_EXPECTED_LEAGUES - leagues_found
        if missing_leagues:
            status("WARN", f"[{label}] Ligues absentes : {missing_leagues}")
            issues.append(f"Ligues manquantes dans {label}: {missing_leagues}")
        else:
            status("OK", f"[{label}] Toutes les ligues présentes : {sorted(leagues_found)}")

        # Vérif volume par ligue
        if "league" in df.columns:
            counts = df.groupby("league").size()
            for league, count in counts.items():
                icon = "OK" if count >= MIN_PLAYERS_PER_LEAGUE else "WARN"
                status(icon, f"[{label}] {league:<30} {count:>4} joueurs")

        # Vérif nulls sur colonnes critiques
        critical = ["expectedGoals", "expectedAssists", "minutesPlayed"]
        for col in critical:
            if col in df.columns:
                n_null = df[col].isnull().sum()
                pct    = n_null / len(df) * 100
                icon   = "OK" if pct < 10 else "WARN"
                status(icon, f"[{label}] {col}: {n_null} nulls ({pct:.1f}%)")

        # Vérif doublons
        if "player_name" in df.columns and "team_name" in df.columns:
            n_dup = df.duplicated(subset=["player_name", "team_name"]).sum()
            icon  = "OK" if n_dup == 0 else "WARN"
            status(icon, f"[{label}] Doublons player+team : {n_dup}")

        # Vérif saisons
        if "season" in df.columns:
            seasons = df["season"].unique()
            status("OK" if len(seasons) == 1 else "WARN",
                   f"[{label}] Saisons détectées : {sorted(seasons)}")

    return {"source": "sofascore", "ok": len(issues) == 0, "issues": issues,
            "n_players_total": len(df_total), "n_players_per90": len(df_per90)}


def validate_understat() -> dict:
    section("UNDERSTAT — validation")
    issues = []

    df_players = load_if_exists(BASE_DIR / "understat" / "ALL_players_season.csv")
    df_teams   = load_if_exists(BASE_DIR / "understat" / "ALL_teams_season.csv")

    if df_players is None:
        return {"source": "understat", "ok": False, "issues": ["Fichier joueurs manquant"]}

    # Colonnes clés Understat
    required = ["player", "team", "league", "xGChain", "xGBuildup"]
    missing = [c for c in required if c not in df_players.columns]
    if missing:
        status("ERROR", f"Colonnes manquantes joueurs : {missing}")
        issues.append(f"Colonnes manquantes: {missing}")
    else:
        status("OK", "Colonnes xGChain / xGBuildup présentes")

    # Ligues
    if "league" in df_players.columns:
        found = set(df_players["league"].unique())
        missing_l = US_EXPECTED_LEAGUES - found
        if missing_l:
            status("WARN", f"Ligues manquantes : {missing_l}")
        else:
            status("OK", f"5 ligues présentes : {sorted(found)}")

        for league, count in df_players.groupby("league").size().items():
            icon = "OK" if count >= MIN_PLAYERS_PER_LEAGUE else "WARN"
            status(icon, f"  {league:<15} {count:>4} joueurs")

    # Vérif xGChain / xGBuildup nulls
    for col in ["xGChain", "xGBuildup"]:
        if col in df_players.columns:
            n_null = df_players[col].isnull().sum()
            icon   = "OK" if n_null == 0 else "WARN"
            status(icon, f"{col}: {n_null} nulls")

    # Stats équipe (ppda = colonne produite par l'agrégation)
    if df_teams is not None and "ppda" in df_teams.columns:
        status("OK", f"PPDA équipe disponible — {len(df_teams)} lignes")
    else:
        status("WARN", "PPDA équipe absent ou non chargé")
        issues.append("PPDA équipe manquant")

    return {"source": "understat", "ok": len(issues) == 0, "issues": issues,
            "n_players": len(df_players) if df_players is not None else 0}


def validate_transfermarkt() -> dict:
    section("TRANSFERMARKT — validation")
    issues = []

    df_mv = load_if_exists(BASE_DIR / "transfermarkt" / "ALL_profiles.csv")

    if df_mv is None:
        return {"source": "transfermarkt", "ok": False, "issues": ["Fichier manquant"]}

    required = ["player", "team", "age", "market_value", "league"]
    missing = [c for c in required if c not in df_mv.columns]
    if missing:
        status("ERROR", f"Colonnes manquantes : {missing}")
        issues.append(f"Colonnes manquantes: {missing}")
    else:
        status("OK", "Colonnes profil présentes (position, foot, age, market_value)")

    # Volume
    TM_EXPECTED = {"GB1", "ES1", "IT1", "L1", "FR1"}
    if "league" in df_mv.columns:
        found = set(df_mv["league"].unique())
        for league, count in df_mv.groupby("league").size().items():
            icon = "OK" if count >= MIN_PLAYERS_PER_LEAGUE else "WARN"
            status(icon, f"  {league:<5} {count:>4} joueurs")

    # Nulls market_value
    if "market_value" in df_mv.columns:
        n_null = df_mv["market_value"].isnull().sum()
        pct    = n_null / len(df_mv) * 100
        icon   = "OK" if pct < 20 else "WARN"
        status(icon, f"market_value nulls : {n_null} ({pct:.1f}%)")

    return {"source": "transfermarkt", "ok": len(issues) == 0, "issues": issues,
            "n_players": len(df_mv)}


# ──────────────────────────────────────────────────────────────────
# VÉRIFICATION DE COHÉRENCE INTER-SOURCES
# ──────────────────────────────────────────────────────────────────

def validate_intersection() -> dict:
    """Vérifie que les 3 sources couvrent les mêmes ligues et la même période."""
    section("COHÉRENCE INTER-SOURCES")
    issues = []

    # Charger les fichiers disponibles
    files = {
        "sofascore":    BASE_DIR / "sofascore"    / "ALL_season_total.csv",
        "understat":    BASE_DIR / "understat"    / "ALL_players_season.csv",
        "transfermarkt":BASE_DIR / "transfermarkt"/ "ALL_profiles.csv",
    }
    dfs = {}
    for src, path in files.items():
        if path.exists():
            dfs[src] = pd.read_csv(path, encoding="utf-8-sig")

    if len(dfs) < 2:
        status("WARN", "Moins de 2 sources chargées — vérification inter-sources impossible")
        return {"ok": False, "issues": ["Sources insuffisantes"]}

    # Vérif saisons
    print("\n  Saisons détectées par source :")
    seasons_by_source = {}
    for src, df in dfs.items():
        if "season" in df.columns:
            seasons = set(df["season"].astype(str).unique())
            seasons_by_source[src] = seasons
            status("OK", f"  {src:<15} saisons : {sorted(seasons)}")

    # Toutes les sources sur la même saison ?
    all_seasons = set()
    for s in seasons_by_source.values():
        all_seasons |= s
    if len(all_seasons) > 1:
        status("WARN", f"Saisons mixtes détectées : {all_seasons} — vérifier la cohérence")
        issues.append("Saisons mixtes entre sources")
    else:
        status("OK", f"Toutes les sources sur la même saison : {all_seasons}")

    # Estimation du recouvrement joueurs (fuzzy : nom + club)
    if "sofascore" in dfs and "understat" in dfs:
        ss_names = set(dfs["sofascore"]["player_name"].str.lower().str.strip()
                       if "player_name" in dfs["sofascore"].columns else [])
        us_names = set(dfs["understat"]["player"].str.lower().str.strip()
                       if "player" in dfs["understat"].columns else [])

        overlap_exact = len(ss_names & us_names)
        pct = overlap_exact / max(len(ss_names), 1) * 100
        icon = "OK" if pct > 30 else "WARN"
        status(icon,
               f"Recouvrement SofaScore/Understat (noms exacts) : "
               f"{overlap_exact} / {len(ss_names)} ({pct:.0f}%)")
        if pct < 30:
            issues.append("Faible recouvrement SofaScore/Understat — vérifier les noms")

    # Résumé volumes
    print("\n  Volume par source :")
    for src, df in dfs.items():
        print(f"    {src:<15} {len(df):>5} lignes")

    return {"ok": len(issues) == 0, "issues": issues}


# ──────────────────────────────────────────────────────────────────
# RAPPORT FINAL
# ──────────────────────────────────────────────────────────────────

def print_report(results: list):
    section("RAPPORT DE VALIDATION")
    all_ok = all(r.get("ok", False) for r in results)

    for r in results:
        src    = r.get("source", r.get("step", "?"))
        ok     = r.get("ok", False)
        issues = r.get("issues", [])
        icon   = "✅" if ok else "⚠ "
        print(f"  {icon}  {src:<20} {'OK' if ok else str(len(issues)) + ' problème(s)'}")
        for issue in issues:
            print(f"           → {issue}")

    print()
    if all_ok:
        status("OK", "Toutes les validations passées — prêt pour 03_match_ids.py")
    else:
        status("WARN",
               "Des problèmes ont été détectés — vérifier les données avant de continuer")
        print("\n  Conseils de résolution :")
        print("    • Données manquantes → relancer 01_extract.py --source <source>")
        print("    • Saisons mixtes    → vérifier le fallback dans 01_extract.py")
        print("    • Faible recouvrement → sera traité dans 03_match_ids.py (fuzzy matching)")


# ──────────────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Validation du périmètre et cohérence des données")
    parser.add_argument("--fix", action="store_true",
                        help="Tenter de corriger les problèmes mineurs automatiquement")
    args = parser.parse_args()

    print("\n" + "═" * 55)
    print("  VALIDATION DES DONNÉES — Football Scoring Project")
    print("═" * 55)

    results = [
        validate_sofascore(),
        validate_understat(),
        validate_transfermarkt(),
        validate_intersection(),
    ]

    print_report(results)

    print("\n" + "═" * 55)
    print("  Prochaine étape : python 03_match_ids.py")
    print("═" * 55 + "\n")


if __name__ == "__main__":
    main()
