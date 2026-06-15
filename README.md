# Football Player Scoring — Pipeline de données

## Périmètre
- **Ligues** : Big 5 (Premier League, La Liga, Serie A, Bundesliga, Ligue 1)
- **Saison** : 2025-26 (fallback 2024-25 si non disponible)
- **Sources** : SofaScore (principal) + Understat (xGChain/xGBuildup) + Transfermarkt (profils)
- **Seuil** : ≥ 450 minutes jouées

## Pipeline en 5 étapes

```
01_extract.py     → Scraping et export des données brutes
02_validate.py    → Vérification périmètre / cohérence temporelle
03_match_ids.py   → Matching des identités inter-sources (fuzzy)
04_merge.py       → Construction de la table maître unifiée
05_features.py    → Calcul per90 / z-scores / percentiles par poste
06_scoring.py     → Modèle de scoring (à venir)
```

## Installation

```bash
pip install -r requirements.txt
```

## Exécution complète

```bash
python 01_extract.py
python 02_validate.py
python 03_match_ids.py --export-unmatched   # exporter les non-matchés pour correction manuelle
python 04_merge.py
python 05_features.py
```

## Structure des données

```
data/
  raw/
    sofascore/
      players_total.csv   # stats brutes saison
      players_per90.csv   # stats normalisées per90 (calculées par SofaScore)
    understat/
      players_season.csv  # npxG, xGChain, xGBuildup
      teams_season.csv    # PPDA équipe (contexte)
    transfermarkt/
      player_profiles.csv # poste, pied, âge, valeur marchande
  processed/
    id_mapping.csv        # table de correspondance inter-sources
    unmatched_players.csv # joueurs non-matchés (à corriger manuellement)
  master/
    players_master.csv    # table unifiée (toutes sources jointes)
    players_features.csv  # features per90 + z-scores par poste
    feature_report.txt    # rapport de couverture des features
  manual_corrections.csv  # corrections manuelles de noms (optionnel)
```

## Décisions clés

| Décision | Choix | Raison |
|---|---|---|
| Source principale | SofaScore | xG Opta, saison courante, 600+ ligues |
| xG retenu | npxG (Understat) | Hors pénalty = plus stable |
| Metrics uniques | xGChain + xGBuildup | Introuvables ailleurs gratuitement |
| Normalisation | Z-score par poste | Un défenseur ne se compare pas aux attaquants |
| Seuil de jeu | 450 min (~5 matchs) | Stats per90 instables en dessous |
| Matching | Fuzzy (rapidfuzz, seuil 88) | Noms différents selon les sources |
