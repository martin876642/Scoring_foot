"""
Récupération des données :
  - Understat (équipes) : API JSON officieuse getLeagueData/{league}/{season}
  - Possession : ScraperFC/SofaScore (best-effort) ou possession_override.csv
"""

import logging
from pathlib import Path

import requests
import pandas as pd

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "X-Requested-With": "XMLHttpRequest",
}
# API JSON officieuse : league.min.js → $.ajax({url:"getLeagueData/"+league+"/"+season})
_UNDERSTAT_API = "https://understat.com/getLeagueData/{league}/{season}"


def _f(val, default: float = 0.0) -> float:
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def _i(val, default: int = 0) -> int:
    try:
        return int(val)
    except (TypeError, ValueError):
        return default


def fetch_understat(league: str, season: str) -> pd.DataFrame:
    url = _UNDERSTAT_API.format(league=league, season=season)
    referer = f"https://understat.com/league/{league}/{season}"
    headers = {**_HEADERS, "Referer": referer}
    logger.info(f"Understat API → {url}")
    r = requests.get(url, headers=headers, timeout=30)
    r.raise_for_status()

    data = r.json()
    raw = data.get("teams", data)   # {"id": {...}} ou directement le dict
    # raw peut être un dict {"id": {...}} ou une liste selon la version du site
    teams_iter = raw.items() if isinstance(raw, dict) else enumerate(raw)

    rows = []
    for _, team_data in teams_iter:
        title   = team_data.get("title", "Unknown")
        history = team_data.get("history", [])
        if not history:
            logger.warning(f"Aucun historique pour '{title}' — ignoré")
            continue

        ppda_att  = sum(_i(m["ppda"]["att"])         for m in history)
        ppda_def  = sum(_i(m["ppda"]["def"])         for m in history)
        oppda_att = sum(_i(m["ppda_allowed"]["att"]) for m in history)
        oppda_def = sum(_i(m["ppda_allowed"]["def"]) for m in history)

        xg   = sum(_f(m.get("xG",   m.get("xg",   0))) for m in history)
        xga  = sum(_f(m.get("xGA",  m.get("xga",  0))) for m in history)
        npxg = sum(_f(m.get("npxG", m.get("npxg", 0))) for m in history)
        npxga= sum(_f(m.get("npxGA",m.get("npxga",0))) for m in history)
        xpts = sum(_f(m.get("xpts", m.get("xPts", 0))) for m in history)

        rows.append({
            "Team":  title,
            "G":     sum(_i(m.get("scored", 0)) for m in history),
            "GA":    sum(_i(m.get("missed", 0)) for m in history),
            "PTS":   sum(_i(m.get("pts",    0)) for m in history),
            "xG":    xg,
            "NPxG":  npxg,
            "xGA":   xga,
            "NPxGA": npxga,
            "NPxGD": npxg - npxga,
            "DC":    sum(_i(m.get("deep",         0)) for m in history),
            "ODC":   sum(_i(m.get("deep_allowed", 0)) for m in history),
            "xPTS":  xpts,
            "PPDA":  ppda_att  / ppda_def  if ppda_def  > 0 else None,
            "OPPDA": oppda_att / oppda_def if oppda_def > 0 else None,
        })

    df = pd.DataFrame(rows)
    df.insert(0, "League", league)
    logger.info(f"Understat [{league}] : {len(df)} équipes récupérées")
    return df


def _try_sofascore() -> dict[str, float]:
    """Tente ScraperFC → dict {team_name: possession_pct}. Retourne {} si indisponible."""
    try:
        from ScraperFC import SofaScore  # noqa: F401
        logger.warning(
            "ScraperFC détecté mais fetch possession SofaScore non implémenté "
            "(API instable) — utilisez possession_override.csv"
        )
        return {}
    except ImportError:
        logger.info("ScraperFC non installé — skip SofaScore possession")
        return {}
    except Exception as exc:
        logger.warning(f"ScraperFC erreur : {exc} — skip")
        return {}


def _load_override(path: str) -> dict[str, float]:
    p = Path(path)
    if not p.exists():
        return {}
    df = pd.read_csv(p, encoding="utf-8")
    if "team" not in df.columns or "possession_pct" not in df.columns:
        logger.warning("possession_override.csv : colonnes attendues = team, possession_pct")
        return {}
    result = dict(zip(df["team"].str.strip(), df["possession_pct"]))
    logger.info(f"possession_override.csv : {len(result)} équipes chargées")
    return result


def _merge_possession(df: pd.DataFrame, possession: dict[str, float]) -> pd.DataFrame:
    df = df.copy()
    vals = []
    for team in df["Team"]:
        v = possession.get(team)
        if v is None:
            # fuzzy : sous-chaîne
            matches = [k for k in possession if team.lower() in k.lower() or k.lower() in team.lower()]
            if matches:
                v = possession[matches[0]]
                logger.debug(f"Possession fuzzy '{team}' → '{matches[0]}'")
            else:
                logger.warning(f"Pas de possession pour '{team}' — sera exclu du bloc offensif si nécessaire")
        vals.append(v)
    df["possession_pct"] = vals
    return df


def fetch_all(leagues, season: str, possession_override_path: str) -> pd.DataFrame:
    """leagues : str ou list[str]. Concatène toutes les ligues en un seul DataFrame."""
    if isinstance(leagues, str):
        leagues = [leagues]

    frames = [fetch_understat(lg, season) for lg in leagues]
    df = pd.concat(frames, ignore_index=True)
    logger.info(f"Total : {len(df)} équipes — {len(leagues)} ligues")

    possession = _try_sofascore() or _load_override(possession_override_path)

    if possession:
        df = _merge_possession(df, possession)
        logger.info(f"possession_pct disponible pour {df['possession_pct'].notna().sum()}/{len(df)} équipes")
    else:
        df["possession_pct"] = None
        logger.warning("Aucune donnée de possession — bloc offensif sans possession_pct")

    return df
