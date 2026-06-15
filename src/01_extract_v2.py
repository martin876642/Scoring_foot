"""
01_extract_v2.py
================
Extraction ciblée — seules les colonnes définies dans recap_data_raw.xlsx
(feuille Colonnes_par_source) sont conservées.

Sources :
  - SofaScore : stats saison agrégées
  - Understat  : stats joueurs saison (xGChain/xGBuildup) + stats équipes saison
  - Transfermarkt : profil joueur + valeur marchande (désactivé par défaut)

Usage :
    pip install -r requirements.txt
    python 01_extract_v2.py                    # tout extraire
    python 01_extract_v2.py --source sofascore
    python 01_extract_v2.py --source understat
    python 01_extract_v2.py --source transfermarkt
"""

import sys
import io
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import argparse
import time
import warnings
from pathlib import Path

import pandas as pd

warnings.filterwarnings("ignore")

# ──────────────────────────────────────────────────────────────────
# CONFIGURATION
# ──────────────────────────────────────────────────────────────────

LEAGUES_SS = ["England Premier League", "Spain La Liga", "Italy Serie A", "Germany Bundesliga", "France Ligue 1"]

LEAGUES_UNDERSTAT = {
    "EPL":        "ENG-Premier League",
    "La_liga":    "ESP-La Liga",
    "Serie_A":    "ITA-Serie A",
    "Bundesliga": "GER-Bundesliga",
    "Ligue_1":    "FRA-Ligue 1",
}

LEAGUES_TM = {
    "GB1": "England Premier League",
    "ES1": "Spain La Liga",
    "IT1": "Italy Serie A",
    "L1":  "Germany Bundesliga",
    "FR1": "France Ligue 1",
}

SEASON_PRIMARY  = "25/26"
SEASON_FALLBACK = "25/26"
MIN_MINUTES     = 450

BASE_DIR = Path(__file__).parent.parent / "data" / "raw"
for sub in ["sofascore/season", "sofascore/positions",
            "understat/season",
            "transfermarkt/profiles"]:
    (BASE_DIR / sub).mkdir(parents=True, exist_ok=True)

def parse_season(season: str) -> dict:
    """
    Normalise le format de saison pour les différentes APIs.

    Accepte : '25/26', '2025/2026', '2026' (année de fin)
    Retourne :
      ss_year (str) : format court pour SofaScore, ex. '25/26'
      us_year (int) : année de début pour Understat / Transfermarkt, ex. 2025
    """
    if "/" in season:
        start, end = season.split("/")
        if len(start) == 4:
            start = start[2:]
        if len(end) == 4:
            end = end[2:]
        return {"ss_year": f"{start}/{end}", "us_year": 2000 + int(start)}
    else:
        year = int(season)
        if year < 100:
            year += 2000
        start_year = year - 1
        return {"ss_year": f"{str(start_year)[2:]}/{str(year)[2:]}", "us_year": start_year}



def save(df: pd.DataFrame, path: Path, label: str = ""):
    df.to_csv(path, index=False, encoding="utf-8-sig")
    n, c = len(df), len(df.columns)
    print(f"    ✅  {label or path.name:<55} {n:>5} lignes × {c} colonnes")


def check(module: str) -> bool:
    import importlib
    try:
        importlib.import_module(module)
        return True
    except ImportError:
        return False


# ══════════════════════════════════════════════════════════════════
# SOFASCORE
# ══════════════════════════════════════════════════════════════════

# Colonnes SofaScore à conserver — noms exacts retournés par l'API SofaScore
# (vérifiés via ss.stat_names — toute divergence entraînerait un drop silencieux)
SS_ALL_COLS = [
    # Identité
    "player_name", "player_id", "team_name", "position",
    "appearances", "minutesPlayed",
    # Buts & tirs
    "goals", "expectedGoals",
    "shotsOnTarget", "totalShots",          # totalShots = tirs totaux (pas "shots")
    "bigChancesMissed", "bigChancesCreated",
    "goalConversionPercentage",
    "headedGoals",                           # buts de la tête
    "shotsFromInsideTheBox",                 # tirs depuis la surface
    # Passes & création
    "assists", "expectedAssists",
    "keyPasses", "totalPasses",
    "accuratePasses", "accuratePassesPercentage",
    "accurateLongBalls", "accurateLongBallsPercentage",
    "accurateCrosses", "accurateCrossesPercentage",
    "totalCross",                            # centres totaux (pas "totalCrosses")
    "accurateFinalThirdPasses",              # passes dans le dernier tiers (pas "passesToFinalThird")
    "passToAssist",                          # avant-dernière passe
    # Possession & dribbles
    "successfulDribbles", "successfulDribblesPercentage",
    "totalContest",                          # dribbles tentés (pas "attemptedDribbles")
    "touches",
    "dispossessed", "possessionLost",
    "possessionWonAttThird",                 # ballons récupérés en zone offensive
    "wasFouled",                             # fautes subies (pas "foulsDrawn")
    "ballRecovery",                          # récupérations de balle
    "offsides",
    "distanceCovered",                       # TEST — distance parcourue (à confirmer API SS)
    "progressiveCarries",                    # TEST — portées progressives (à confirmer API SS)
    # Défensif
    "tackles", "tacklesWon",
    "interceptions", "blockedShots",
    "clearances",
    "outfielderBlocks",                      # contres / dégagements (pas "headedClearances" — absent API)
    "errorLeadToGoal",                       # erreurs → but (pas "errorsLeadingToGoal")
    "errorLeadToShot",                       # erreurs → tir (pas "errorsLeadingToShot")
    "groundDuelsWon", "groundDuelsWonPercentage",
    "aerialDuelsWon", "aerialDuelsWonPercentage",
    "dribbledPast",                          # fois dribblé
    "duelLost",                              # duels perdus
    "fouls",                                 # fautes commises (pas "foulsCommitted")
    "yellowCards", "redCards",
    "penaltyConceded",                       # pénaltys concédés
    "penaltyWon",                            # pénaltys provoqués
    # Gardien
    "saves", "goalsPrevented",
    "cleanSheet",                            # clean sheets (pas "cleanSheets")
    "goalsConceded",                         # xGoalsConceded absent API SS
    "penaltySave", "penaltyFaced",           # pour ratio arrêts sur penalty
                                             # penaltiesSaved absent API SS
    "highClaims", "runsOut", "successfulRunsOut",
    "punches",
                                             # totalKeeperSweeper / accurateKeeperSweeper absents API SS
    "savedShotsFromInsideTheBox",            # (pas "savedShotsFromInsideBox")
    "savedShotsFromOutsideTheBox",           # (pas "savedShotsFromOutsideBox")
    "crossesNotClaimed",                     # centres non interceptés
    # Pénaltys (pour calcul npxG proxy)
    "penaltiesTaken", "penaltyGoals",
    # Note SofaScore (benchmark)
    "rating",
]

# Colonnes Understat joueurs — noms effectivement retournés par soccerdata
US_PLAYER_COLS = [
    "player", "team",
    "goals", "xg", "assists", "xa",
    "shots", "key_passes",
    "xg_chain", "xg_buildup",
]

# Renommage soccerdata → convention camelCase attendue en aval
US_PLAYER_RENAME = {
    "xg": "xG", "xa": "xA",
    "xg_chain": "xGChain",
    "xg_buildup": "xGBuildup",
}

# Colonnes Transfermarkt — noms ScraperFC → noms cibles
TM_COL_RENAME = {
    "Name":                "player",
    "ID":                  "player_id",
    "Value":               "market_value",
    "DOB":                 "date_of_birth",
    "Age":                 "age",
    "Height (m)":          "height",
    "Nationality":         "nationality",
    "Position":            "position",
    "Team":                "team",
    "Last club":           "signed_from",
    "Joined":              "joined",
    "Contract expiration": "contract_expires",
    # Pied préféré et poids — ajoutés pour l'export web
    "Foot":                "foot",
    "foot":                "foot",
    "Weight (kg)":         "weight_kg",
    "weight":              "weight_kg",
}

TM_COLS = [
    "player", "player_id", "team", "position",
    "nationality", "age", "date_of_birth",
    "height", "foot", "weight_kg", "joined", "signed_from",
    "contract_expires", "market_value",
]


def extract_sofascore_season(season: str):
    """Stats agrégées saison."""
    if not check("ScraperFC"):
        print("  ❌  pip install ScraperFC")
        return

    import ScraperFC as sfc
    ss = sfc.Sofascore()

    ss_year = parse_season(season)["ss_year"]
    fallback_ss_year = parse_season(SEASON_FALLBACK)["ss_year"]

    positions = ["Goalkeepers", "Defenders", "Midfielders", "Forwards"]

    def _scrape_with_retry(year: str, league: str, acc: str, max_retries: int = 3):
        """Scrape une ligue/accumulation avec retry exponentiel sur erreur réseau."""
        for attempt in range(max_retries):
            try:
                df = ss.scrape_player_league_stats(
                    year=year, league=league, accumulation=acc,
                    selected_positions=positions,
                )
                if df is not None and not df.empty:
                    return df
            except Exception as e:
                if attempt < max_retries - 1:
                    wait = 30 * (attempt + 1)   # 30s → 60s → 90s
                    print(f"    ⏳ [{league} {acc}] erreur ({e.__class__.__name__}), "
                          f"retry {attempt+1}/{max_retries} dans {wait}s...")
                    time.sleep(wait)
                else:
                    raise
        return None

    print(f"\n  SofaScore — stats saison (season={season})")
    for i, league in enumerate(LEAGUES_SS):
        if i > 0:
            print(f"    ⏳ pause 15s avant {league}...")
            time.sleep(15)
        for acc in ["total", "per90", "perMatch"]:
            try:
                df = _scrape_with_retry(ss_year, league, acc)
                if df is None or df.empty:
                    df = _scrape_with_retry(fallback_ss_year, league, acc)
                if df is not None and not df.empty:
                    df = df.reset_index()
                    # Normaliser les colonnes d'identité — ScraperFC peut varier
                    _IDENTITY_MAP = {
                        "player_name": ["name", "playerName", "player", "fullName",
                                        "Player Name", "player name"],
                        "team_name":   ["teamName", "team", "Team", "club",
                                        "Team Name", "team name"],
                        "player_id":   ["id", "playerId", "player_id"],
                        "position":    ["Position", "pos"],
                    }
                    for target, aliases in _IDENTITY_MAP.items():
                        if target not in df.columns:
                            for alias in aliases:
                                if alias in df.columns:
                                    df = df.rename(columns={alias: target})
                                    break
                    # Diagnostic si colonnes d'identité toujours manquantes
                    still_missing = [c for c in ["player_name", "team_name"]
                                     if c not in df.columns]
                    if still_missing:
                        print(f"    ⚠  [{league}] colonnes identité absentes : {still_missing}")
                        print(f"    ℹ  Colonnes dispo (toutes) : {df.columns.tolist()}")
                        diag_path = BASE_DIR / f"sofascore/season/_diag_{league}_{acc}.csv"
                        df.to_csv(diag_path, index=True, encoding="utf-8-sig")
                        print(f"    ℹ  Dump diagnostic : {diag_path.name}")
                    # ── Diagnostic colonnes GK + passes progressives (EPL total uniquement) ──
                    if league == "England Premier League" and acc == "total":
                        gk_df = df[df["position"] == "G"] if "position" in df.columns else df.head(3)
                        print("Colonnes GK disponibles :", sorted(gk_df.columns.tolist()))
                        print("crossesNotClaimed présent :", "crossesNotClaimed" in df.columns)
                        prog_cols = [c for c in df.columns if "progress" in c.lower() or "prgp" in c.lower()]
                        print("Colonnes progressives disponibles :", prog_cols)
                    df["league"] = league
                    df["accumulation"] = acc
                    df["season"] = season
                    cols = [c for c in SS_ALL_COLS if c in df.columns]
                    missing_cols = [c for c in SS_ALL_COLS
                                    if c not in df.columns
                                    and c not in ("player_name","team_name","position","player_id")]
                    if missing_cols and acc == "total":
                        print(f"    ⚠  [{league}] colonnes absentes de l'API : {missing_cols}")
                    extra = ["league", "accumulation", "season"]
                    out_path = BASE_DIR / f"sofascore/season/{league}_{acc}.csv"
                    save(df[cols + extra], out_path, f"SS {league} [{acc}]")
                time.sleep(5)
            except Exception as e:
                print(f"    ⚠  {league} [{acc}] : {e}")



# ══════════════════════════════════════════════════════════════════
# UNDERSTAT
# ══════════════════════════════════════════════════════════════════

def extract_understat(season: str):
    """Stats joueurs saison (xGChain/xGBuildup) + stats équipes saison."""
    if not check("soccerdata"):
        print("  ❌  pip install soccerdata")
        return

    import soccerdata as sd

    print(f"\n  Understat — stats saison joueurs + équipes (season={season})")

    for us_key, sd_league in LEAGUES_UNDERSTAT.items():
        season_int = parse_season(season)["us_year"]
        try:
            us = sd.Understat(leagues=sd_league, seasons=season_int)

            # ── Stats joueurs par saison
            try:
                df = us.read_player_season_stats().reset_index()
                df["league"] = us_key
                df["season"] = season
                cols = [c for c in US_PLAYER_COLS if c in df.columns]
                df_out = df[cols + ["league", "season"]].rename(columns=US_PLAYER_RENAME)
                save(df_out,
                     BASE_DIR / f"understat/season/{us_key}_players_season.csv",
                     f"Understat {us_key} [joueurs saison]")
            except Exception as e:
                print(f"    ⚠  {us_key} joueurs saison : {e}")

            time.sleep(1)

            # ── Stats équipes saison (ppda + xG contexte)
            try:
                df_tm = us.read_team_match_stats()

                # Agrégation home/away → une ligne par équipe
                raw = df_tm.reset_index()
                home = raw[["league_id", "season_id", "home_team", "home_team_code",
                            "home_points", "home_expected_points", "home_goals",
                            "home_xg", "home_np_xg", "home_ppda", "home_deep_completions",
                            "away_goals", "away_xg", "away_np_xg",
                            "away_ppda", "away_deep_completions"]].copy()
                home.columns = ["league_id", "season_id", "team", "team_code",
                                "points", "xp", "goals_for",
                                "xg", "np_xg", "ppda", "deep",
                                "goals_against", "xg_against", "np_xg_against",
                                "oppda", "odc"]
                away = raw[["league_id", "season_id", "away_team", "away_team_code",
                            "away_points", "away_expected_points", "away_goals",
                            "away_xg", "away_np_xg", "away_ppda", "away_deep_completions",
                            "home_goals", "home_xg", "home_np_xg",
                            "home_ppda", "home_deep_completions"]].copy()
                away.columns = home.columns
                long = pd.concat([home, away], ignore_index=True)
                df_ts = long.groupby(["league_id", "season_id", "team", "team_code"]).agg(
                    xg           =("xg",          "sum"),
                    xg_against   =("xg_against",  "sum"),
                    np_xg        =("np_xg",       "sum"),
                    np_xg_against=("np_xg_against","sum"),
                    ppda         =("ppda",         "mean"),
                    oppda        =("oppda",        "mean"),
                    deep         =("deep",         "sum"),
                    odc          =("odc",          "sum"),
                    xp           =("xp",          "sum"),
                ).reset_index()
                df_ts["league"] = us_key
                df_ts["season"] = season
                save(df_ts, BASE_DIR / f"understat/season/{us_key}_teams_season.csv",
                     f"Understat {us_key} [équipes saison]")
            except Exception as e:
                print(f"    ⚠  {us_key} équipes saison : {e}")

            time.sleep(2)

        except Exception as e:
            print(f"    ❌  {us_key} : {e}")


# ══════════════════════════════════════════════════════════════════
# TRANSFERMARKT
# ══════════════════════════════════════════════════════════════════

def extract_transfermarkt(season: str):
    """Profils joueurs + valeur marchande via ScraperFC."""
    if not check("ScraperFC"):
        print("  ❌  pip install ScraperFC")
        return

    import ScraperFC as sfc
    import cloudscraper as _cs_mod
    import requests as _req
    import botasaurus.beep_utils as _bu

    # Désactive la pause interactive de botasaurus sur erreur réseau
    _bu.beep_input = lambda *a, **kw: None

    tm = sfc.Transfermarkt()
    ss_year = parse_season(season)["ss_year"]
    # TM utilise l'année de début comme saison_id (ex. "2025" pour "25/26").
    # On patche get_valid_seasons pour éviter l'appel botasaurus vers TM
    # qui se fait bloquer après un scraping intensif.
    saison_id = str(parse_season(season)["us_year"])
    tm.get_valid_seasons = lambda league: {ss_year: saison_id}

    print(f"\n  Transfermarkt — profils + MV (season={season})")

    # "Other positions" n'est plus dropé — on le parse pour enrichir position_tm
    NESTED_COLS = {"Market value history", "Transfer history"}

    def parse_other_positions(val) -> str:
        """
        Transforme le champ 'Other positions' de TM (liste/dict/str) en chaîne
        de positions secondaires séparées par ' / ', prête à être concaténée
        à position_tm. Ex: [{"position":"Defensive Midfield"}] → "Defensive Midfield"
        """
        if not val or (isinstance(val, float)):
            return ""
        if isinstance(val, list):
            parts = []
            for item in val:
                if isinstance(item, dict):
                    parts.append(item.get("position", item.get("name", "")))
                elif isinstance(item, str):
                    parts.append(item)
            return " / ".join(p for p in parts if p)
        if isinstance(val, str):
            return val.strip()
        return ""

    for i, (tm_key, league) in enumerate(LEAGUES_TM.items()):
        # Pause entre ligues : TM rate-limite l'IP après scraping intensif
        if i > 0:
            print(f"    ⏳ pause 60s anti-rate-limit avant {tm_key}…")
            time.sleep(60)

        try:
            player_links = tm.get_player_links(year=ss_year, league=league)

            # scrape_player utilise requests.get (bloqué par TM) ;
            # on le remplace temporairement par cloudscraper qui gère le TLS.
            _cs_session = _cs_mod.create_scraper(browser="chrome")
            _orig_get = _req.get
            _req.get = _cs_session.get

            rows = []
            n_links = len(player_links)
            try:
                for j, link in enumerate(player_links, 1):
                    for attempt in range(2):   # 2 tentatives max (pas 3)
                        try:
                            rows.append(tm.scrape_player(link))
                            time.sleep(0.8)
                            break
                        except Exception as e_inner:
                            if attempt < 1:
                                time.sleep(4)
                            else:
                                print(f"    ⚠  [{j}/{n_links}] {link.split('/')[-1][:30]} : {e_inner}")
                    if j % 10 == 0:
                        print(f"    ✓  [{j}/{n_links}] profils scrapés")
            finally:
                _req.get = _orig_get  # toujours restaurer requests.get

            if rows:
                df = pd.concat(rows, ignore_index=True)

                # ── DEBUG : afficher toutes les colonnes ScraperFC (1ère ligue seulement)
                if i == 0:
                    print(f"    [DEBUG] Colonnes ScraperFC scrape_player() : {sorted(df.columns.tolist())}")
                    # Chercher toute colonne qui ressemble à "position" ou "other"
                    pos_cols = [c for c in df.columns if any(k in c.lower() for k in ['position','other','second','poste'])]
                    print(f"    [DEBUG] Colonnes liées aux postes : {pos_cols}")
                    for col in pos_cols:
                        sample = df[col].dropna().head(3).tolist()
                        print(f"    [DEBUG]   {col!r}: {sample}")

                # Détecter la colonne des postes secondaires (plusieurs noms possibles)
                OTHER_POS_CANDIDATES = [
                    "Other positions", "Other position", "other_positions",
                    "Secondary Position", "secondary_position",
                    "Position(s)", "Positions",
                ]
                for col_name in OTHER_POS_CANDIDATES:
                    if col_name in df.columns:
                        df["Position"] = df.apply(
                            lambda r, c=col_name: (
                                str(r.get("Position", "") or "").strip()
                                + ((" / " + parse_other_positions(r[c]))
                                   if parse_other_positions(r[c]) else "")
                            ),
                            axis=1,
                        )
                        print(f"    [INFO] Postes secondaires capturés depuis la colonne {col_name!r}")
                        break

                df = df.drop(columns=[c for c in NESTED_COLS if c in df.columns])
                df = df.rename(columns=TM_COL_RENAME)
                df["league"] = tm_key
                df["season"] = season
                cols = [c for c in TM_COLS if c in df.columns]
                save(df[cols + ["league", "season"]],
                     BASE_DIR / f"transfermarkt/profiles/{tm_key}_profiles.csv",
                     f"TM {tm_key} [profils + MV]")
        except Exception as e:
            print(f"    ❌  {tm_key} : {e}")


# ══════════════════════════════════════════════════════════════════
# CONSOLIDATION PAR SOURCE
# ══════════════════════════════════════════════════════════════════

def consolidate():
    """
    Concatène tous les fichiers par source en un seul CSV par type.
    Produit :
      data/raw/sofascore/ALL_season_total.csv
      data/raw/sofascore/ALL_season_per90.csv
      data/raw/sofascore/ALL_season_perMatch.csv
      data/raw/understat/ALL_players_season.csv
      data/raw/understat/ALL_teams_season.csv
      data/raw/transfermarkt/ALL_profiles.csv
    """
    print("\n  Consolidation...")

    # SofaScore saison
    for acc in ["total", "per90", "perMatch"]:
        files = list((BASE_DIR / "sofascore/season").glob(f"*_{acc}.csv"))
        if files:
            df = pd.concat([pd.read_csv(f, encoding="utf-8-sig") for f in files],
                           ignore_index=True)
            out = BASE_DIR / f"sofascore/ALL_season_{acc}.csv"
            save(df, out, f"CONSOLIDATED SS saison [{acc}]")

    # Understat joueurs saison
    files = list((BASE_DIR / "understat/season").glob("*_players_season.csv"))
    if files:
        df = pd.concat([pd.read_csv(f, encoding="utf-8-sig") for f in files],
                       ignore_index=True)
        save(df, BASE_DIR / "understat/ALL_players_season.csv",
             "CONSOLIDATED Understat joueurs saison")

    # Understat équipes saison
    files = list((BASE_DIR / "understat/season").glob("*_teams_season.csv"))
    if files:
        df = pd.concat([pd.read_csv(f, encoding="utf-8-sig") for f in files],
                       ignore_index=True)
        save(df, BASE_DIR / "understat/ALL_teams_season.csv",
             "CONSOLIDATED Understat équipes")

    # Transfermarkt profils
    files = list((BASE_DIR / "transfermarkt/profiles").glob("*_profiles.csv"))
    if files:
        df = pd.concat([pd.read_csv(f, encoding="utf-8-sig") for f in files],
                       ignore_index=True)
        save(df, BASE_DIR / "transfermarkt/ALL_profiles.csv",
             "CONSOLIDATED TM profils")


# ══════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Extraction ciblée des données football (colonnes définies dans recap_data_raw.xlsx)"
    )
    parser.add_argument("--source",
                        choices=["sofascore", "understat", "transfermarkt", "all"],
                        default="all")
    parser.add_argument("--season",  default=SEASON_PRIMARY)
    parser.add_argument("--no-consolidate", action="store_true",
                        help="Sauter la consolidation finale")
    args = parser.parse_args()

    print("\n" + "═" * 60)
    print("  EXTRACTION CIBLÉE — Football Scoring Project v2")
    print("═" * 60)
    print(f"  Saison        : {args.season}")
    print(f"  Ligues        : Big 5 (PL / Liga / SA / BL / L1)")
    print(f"  Source        : {args.source}")
    print("═" * 60)

    if args.source in ("sofascore", "all"):
        extract_sofascore_season(args.season)

    if args.source in ("understat", "all"):
        extract_understat(args.season)

    if args.source in ("transfermarkt", "all"):
        extract_transfermarkt(args.season)

    if not args.no_consolidate:
        consolidate()

    print("\n" + "═" * 60)
    print("  Extraction terminée.")
    print("  Structure : data/raw/{source}/{league}_{type}.csv")
    print("  Fichiers consolidés : data/raw/{source}/ALL_*.csv")
    print("  Prochaine étape : python 02_validate.py")
    print("═" * 60 + "\n")


if __name__ == "__main__":
    main()
