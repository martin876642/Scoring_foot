"""
05_features_v2.py
=================
Feature engineering exhaustif — calcule TOUTES les features disponibles
pour chaque joueur, sans filtrage préalable par rôle.

Le scoring par rôle tactique sera fait dans 06_scoring.py
en sélectionnant le sous-ensemble de features pertinent.

Groupes de postes produits :
  GK   — Gardien
  CB   — Défenseur central
  FB   — Latéral (gauche/droit)
  DM   — Milieu défensif / récupérateur
  CM   — Milieu relanceur / box-to-box
  AM   — Milieu offensif / n10
  W    — Ailier (gauche/droit)
  CF   — Avant-centre / pivot
  SS   — Second attaquant / faux 9

Produit :
  data/master/players_features_v2.csv
  data/master/feature_catalog.csv    ← catalogue de toutes les features avec metadata

Usage :
    python 05_features_v2.py
    python 05_features_v2.py --list-features           # afficher le catalogue
    python 05_features_v2.py --inspect-role DM         # stats d'un rôle
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
from scipy.stats import percentileofscore

# ──────────────────────────────────────────────────────────────────
MASTER_DIR  = Path(__file__).parent.parent / "data" / "master"
MIN_MINUTES = 450

# ──────────────────────────────────────────────────────────────────
# NOMENCLATURE FOOTBALL MANAGER — Rôles tactiques
# Source : FM2024/2025 — 28 rôles couvrant tous les postes
#
# Chaque rôle FM est défini par :
#   - position_primary  : poste(s) TM/Opta compatibles
#   - fm_role           : code rôle FM
#   - fm_role_label     : libellé FM complet
#   - key_attributes    : attributs FM déterminants (pour référence)
#
# À ce stade, on ASSIGNE le rôle FM principal à chaque joueur
# selon sa position TM + des heuristiques sur ses features.
# L'utilisateur affinera les pondérations dans 06_scoring.py.
# ──────────────────────────────────────────────────────────────────

FM_ROLES = {

    # ── GARDIENS ─────────────────────────────────────────────────
    "GK":   {
        "label":      "Goalkeeper (GK)",
        "positions":  ["Goalkeeper"],
        "key_attrs":  ["Reflexes", "One on Ones", "Positioning", "Aerial Ability", "Handling"],
        "group":      "GK",
    },
    "SK":   {
        "label":      "Sweeper Keeper (SK)",
        "positions":  ["Goalkeeper"],
        "key_attrs":  ["First Touch", "Rushing Out", "Composure", "Passing", "Kicking"],
        "group":      "GK",
        "distinguisher": "high_runs_out + high_longballs_pct",
    },

    # ── DEFENSEURS CENTRAUX ───────────────────────────────────────
    "CD":   {
        "label":      "Central Defender (CD)",
        "positions":  ["Centre-Back"],
        "key_attrs":  ["Marking", "Tackling", "Heading", "Jumping Reach", "Positioning"],
        "group":      "CB",
    },
    "BPD":  {
        "label":      "Ball-Playing Defender (BPD)",
        "positions":  ["Centre-Back"],
        "key_attrs":  ["Passing", "First Touch", "Composure", "Technique", "Vision"],
        "group":      "CB",
        "distinguisher": "high_pass_acc + high_longballs + high_xgbuildup",
    },
    "L":    {
        "label":      "Libero (L)",
        "positions":  ["Centre-Back"],
        "key_attrs":  ["Passing", "Dribbling", "First Touch", "Composure", "Decisions"],
        "group":      "CB",
        "distinguisher": "high_progressivecarries + high_touches + high_dribbles",
    },
    "SW":   {
        "label":      "Stopper (SW)",
        "positions":  ["Centre-Back"],
        "key_attrs":  ["Aggression", "Bravery", "Tackling", "Anticipation", "Work Rate"],
        "group":      "CB",
        "distinguisher": "high_tackles + high_interceptions + high_aerial",
    },

    # ── LATERAUX ─────────────────────────────────────────────────
    "FB":   {
        "label":      "Full Back (FB)",
        "positions":  ["Left-Back", "Right-Back"],
        "key_attrs":  ["Tackling", "Marking", "Stamina", "Pace", "Work Rate"],
        "group":      "FB",
    },
    "WB":   {
        "label":      "Wing Back (WB)",
        "positions":  ["Left-Back", "Right-Back", "Wing-Back"],
        "key_attrs":  ["Crossing", "Pace", "Stamina", "Dribbling", "Work Rate"],
        "group":      "FB",
        "distinguisher": "high_crosses + high_touchesbox + high_dribbles + high_avgX",
    },
    "IWB":  {
        "label":      "Inverted Wing Back (IWB)",
        "positions":  ["Left-Back", "Right-Back"],
        "key_attrs":  ["Passing", "Vision", "Work Rate", "Decisions", "Technique"],
        "group":      "FB",
        "distinguisher": "high_passacc + high_xgbuildup + low_crosses",
    },

    # ── MILIEUX DEFENSIFS ─────────────────────────────────────────
    "DM":   {
        "label":      "Defensive Midfielder (DM)",
        "positions":  ["Defensive Midfield"],
        "key_attrs":  ["Tackling", "Marking", "Positioning", "Stamina", "Anticipation"],
        "group":      "DM",
    },
    "HB":   {
        "label":      "Half Back (HB)",
        "positions":  ["Defensive Midfield"],
        "key_attrs":  ["Positioning", "Tackling", "Composure", "Passing", "Vision"],
        "group":      "DM",
        "distinguisher": "drops between CBs — low avgX + high_clearances",
    },
    "RGA":  {
        "label":      "Regista (RGA)",
        "positions":  ["Defensive Midfield"],
        "key_attrs":  ["Passing", "Vision", "Technique", "First Touch", "Long Shots"],
        "group":      "DM",
        "distinguisher": "high_longballs + high_passacc + high_key_passes + high_xgbuildup",
    },
    "BWM":  {
        "label":      "Ball-Winning Midfielder (BWM)",
        "positions":  ["Defensive Midfield", "Central Midfield"],
        "key_attrs":  ["Tackling", "Aggression", "Stamina", "Work Rate", "Anticipation"],
        "group":      "DM",
        "distinguisher": "high_tackles + high_interceptions + high_distance",
    },

    # ── MILIEUX CENTRAUX ──────────────────────────────────────────
    "CM":   {
        "label":      "Central Midfielder (CM)",
        "positions":  ["Central Midfield"],
        "key_attrs":  ["Passing", "Stamina", "Work Rate", "Decisions", "Positioning"],
        "group":      "CM",
    },
    "DLP":  {
        "label":      "Deep-Lying Playmaker (DLP)",
        "positions":  ["Central Midfield", "Defensive Midfield"],
        "key_attrs":  ["Passing", "Vision", "Technique", "First Touch", "Anticipation"],
        "group":      "CM",
        "distinguisher": "high_passacc + high_longballs + high_xgbuildup + low_avgX",
    },
    "MEZ":  {
        "label":      "Mezzala (MEZ)",
        "positions":  ["Central Midfield"],
        "key_attrs":  ["Dribbling", "Passing", "Technique", "Vision", "Stamina"],
        "group":      "CM",
        "distinguisher": "high_keypass + high_dribbles + high_xgchain + high_xa",
    },
    "BBM":  {
        "label":      "Box-to-Box Midfielder (BBM)",
        "positions":  ["Central Midfield"],
        "key_attrs":  ["Stamina", "Work Rate", "Passing", "Tackling", "Dribbling"],
        "group":      "CM",
        "distinguisher": "high_distance + high_tackles + high_keypass",
    },
    "CAR":  {
        "label":      "Carrilero (CAR)",
        "positions":  ["Central Midfield"],
        "key_attrs":  ["Stamina", "Work Rate", "Positioning", "Tackling", "Passing"],
        "group":      "CM",
        "distinguisher": "high_distance + high_tackles + high_passes + low_xa",
    },

    # ── MILIEUX OFFENSIFS ─────────────────────────────────────────
    "AM":   {
        "label":      "Attacking Midfielder (AM)",
        "positions":  ["Attacking Midfield"],
        "key_attrs":  ["Dribbling", "Passing", "Technique", "Vision", "First Touch"],
        "group":      "AM",
    },
    "SS":   {
        "label":      "Shadow Striker (SS)",
        "positions":  ["Attacking Midfield", "Second Striker"],
        "key_attrs":  ["Off the Ball", "Dribbling", "First Touch", "Finishing", "Anticipation"],
        "group":      "AM",
        "distinguisher": "high_xg + high_touches_box + high_shots + high_avgX",
    },
    "T":    {
        "label":      "Trequartista (T)",
        "positions":  ["Attacking Midfield"],
        "key_attrs":  ["Flair", "Technique", "Vision", "Dribbling", "Creativity"],
        "group":      "AM",
        "distinguisher": "high_keypass + high_xgchain + high_dribbles + free_role",
    },

    # ── AILIERS ───────────────────────────────────────────────────
    "W":    {
        "label":      "Winger (W)",
        "positions":  ["Left Winger", "Right Winger"],
        "key_attrs":  ["Pace", "Crossing", "Dribbling", "Acceleration", "Technique"],
        "group":      "W",
    },
    "IW":   {
        "label":      "Inverted Winger (IW)",
        "positions":  ["Left Winger", "Right Winger"],
        "key_attrs":  ["Dribbling", "Technique", "Cutting Inside", "Long Shots", "Finishing"],
        "group":      "W",
        "distinguisher": "high_shots + high_xg + high_dribbles + low_crosses",
    },
    "IF":   {
        "label":      "Inside Forward (IF)",
        "positions":  ["Left Winger", "Right Winger"],
        "key_attrs":  ["Dribbling", "Finishing", "Off the Ball", "Pace", "First Touch"],
        "group":      "W",
        "distinguisher": "high_touches_box + high_xg + high_shots_ot",
    },
    "WTM":  {
        "label":      "Wide Target Man (WTM)",
        "positions":  ["Left Winger", "Right Winger"],
        "key_attrs":  ["Strength", "Jumping", "Heading", "Holding Up Ball", "Aerial"],
        "group":      "W",
        "distinguisher": "high_aerial + high_headed_goals + high_duels",
    },

    # ── AVANT-CENTRES ─────────────────────────────────────────────
    "CF":   {
        "label":      "Complete Forward (CF)",
        "positions":  ["Centre-Forward"],
        "key_attrs":  ["Off the Ball", "Finishing", "Dribbling", "Technique", "Work Rate"],
        "group":      "CF",
    },
    "AF":   {
        "label":      "Advanced Forward (AF)",
        "positions":  ["Centre-Forward"],
        "key_attrs":  ["Pace", "Finishing", "Off the Ball", "Dribbling", "Acceleration"],
        "group":      "CF",
        "distinguisher": "high_npxg + high_shots + high_offsides (depth runs)",
    },
    "DLF":  {
        "label":      "Deep-Lying Forward (DLF)",
        "positions":  ["Centre-Forward", "Second Striker"],
        "key_attrs":  ["First Touch", "Passing", "Technique", "Vision", "Dribbling"],
        "group":      "CF",
        "distinguisher": "high_xgbuildup + high_keypass + high_assists + low_avgX",
    },
    "F9":   {
        "label":      "False 9 (F9)",
        "positions":  ["Centre-Forward"],
        "key_attrs":  ["Dribbling", "Creativity", "Vision", "Passing", "First Touch"],
        "group":      "CF",
        "distinguisher": "high_xa + high_keypass + high_xgchain + very_low_avgX",
    },
    "P":    {
        "label":      "Poacher (P)",
        "positions":  ["Centre-Forward"],
        "key_attrs":  ["Finishing", "Off the Ball", "Anticipation", "Composure", "Concentration"],
        "group":      "CF",
        "distinguisher": "high_goals_conv + high_shots_ot + low_xgbuildup + high_avgX",
    },
    "TM":   {
        "label":      "Target Man (TM)",
        "positions":  ["Centre-Forward"],
        "key_attrs":  ["Strength", "Jumping Reach", "Heading", "Aerial Ability", "Hold Up Play"],
        "group":      "CF",
        "distinguisher": "high_aerial + high_headed_goals + high_touches + high_duels",
    },
    "PF":   {
        "label":      "Pressing Forward (PF)",
        "positions":  ["Centre-Forward", "Left Winger", "Right Winger"],
        "key_attrs":  ["Work Rate", "Stamina", "Aggression", "Pace", "Pressing"],
        "group":      "CF",
        "distinguisher": "high_distance + high_fouls_won + low_xg + high_pressures",
    },
}

# ──────────────────────────────────────────────────────────────────
# GROUPES DE POSTES & RÔLES TACTIQUES (CHANGEMENTS 3 & 4)
# ──────────────────────────────────────────────────────────────────

POSTE_TO_NORM_GROUP: dict[str, str] = {
    "GK": "GK",
    "CB": "DEF",
    "FB": "DEF",
    "DM": "MID",
    "CM": "MID",
    "AM": "MID",
    "W":  "ATT",
    "CF": "ATT",
}

# Pour fm_role_primary (compat affichage) : poste → code FM court
POSTE_TO_FM_ROLE: dict[str, str] = {
    "GK": "GK", "CB": "CD", "FB": "FB", "DM": "DM",
    "CM": "CM", "AM": "AM", "W":  "W",  "CF": "CF",
}

# Priorité pour choisir le groupe de normalisation quand un joueur a plusieurs postes
POSTE_PRIORITY = ["GK", "CB", "FB", "DM", "CM", "AM", "W", "CF"]

# Rôles tactiques détaillés par poste (CHANGEMENT 3)
POSTE_TO_ROLES: dict[str, list[str]] = {
    "GK": ["gardien_classique", "gardien_libero", "gardien_relanceur"],
    "CB": ["defenseur_central", "stoppeur", "libero_defensif",
           "tour_de_controle", "relanceur"],
    "FB": ["lateral_classique", "piston", "defenseur_lateral",
           "lateral_inverse", "lateral_pressing"],
    "DM": ["sentinelle", "recuperateur_DM", "meneur_jeu_recule_DM"],
    "CM": ["recuperateur_CM", "box_to_box",
           "meneur_jeu_offensif_CM", "meneur_jeu_recule_CM"],
    "AM": ["electron_libre", "meneur_jeu_offensif_AM"],
    "W":  ["interieur", "profondeur_W", "percuteur",
           "excentre", "ailier_defensif"],
    "CF": ["profondeur_CF", "pivot", "faux_9",
           "renard_surfaces", "attaquant_pressing"],
}

# Reverse: role → parent poste
ROLE_TO_POSTE: dict[str, str] = {
    role: poste
    for poste, roles in POSTE_TO_ROLES.items()
    for role in roles
}

# Features par rôle (CHANGEMENT 4)
# Format : {z_col: poids} — poids négatif = ré-inverser une feature déjà inversée
ROLE_FEATURES: dict[str, dict[str, float]] = {

    # ── GARDIENS ─────────────────────────────────────────────────────
    "gardien_classique": {
        "z_acc_passes_p90":       1.0,
        "z_long_balls_pct":       1.0,
        "z_errors_shot_p90":      3.0,
        "z_penalty_save_pct":     1.5,
        "z_goals_prevented_p90":  5.0,
        "z_high_claims_pct":      2.0,
    },
    "gardien_libero": {
        "z_pass_acc_pct":         1.0,
        "z_long_balls_pct":       1.0,
        "z_errors_shot_p90":      3.0,
        "z_penalty_save_pct":     1.0,
        "z_goals_prevented_p90":  5.0,
        "z_runs_out_p90":         1.0,
        "z_runs_out_pct":         2.0,
        "z_high_claims_pct":      1.0,
    },
    "gardien_relanceur": {
        "z_xgchain_p90":          1.5,
        "z_pass_acc_pct":         2.0,
        "z_long_balls_pct":       2.0,
        "z_errors_shot_p90":      3.0,
        "z_penalty_save_pct":     1.0,
        "z_goals_prevented_p90":  5.0,
        "z_high_claims_pct":      1.0,
    },

    # ── DÉFENSEURS CENTRAUX ───────────────────────────────────────────
    "defenseur_central": {
        "z_pass_acc_pct":         1.0,
        "z_long_balls_pct":       1.0,
        "z_poss_lost_p90":        2.0,
        "z_dribbled_past_p90":    1.5,
        "z_fouls_p90":            1.0,
        "z_errors_shot_p90":      2.0,
        "z_interceptions_p90":    3.0,
        "z_ground_duels_pct":     2.5,
        "z_aerial_duels_pct":     2.0,
    },
    "relanceur": {
        "z_aerial_duels_pct":     1.5,
        "z_ground_duels_pct":     2.0,
        "z_interceptions_p90":    2.0,
        "z_dribbled_past_p90":    2.0,
        "z_errors_shot_p90":      2.0,
        "z_fouls_p90":            1.0,
        "z_pass_acc_pct":         2.5,
        "z_long_balls_pct":       2.0,
        "z_xgchain_p90":          2.0,
        "z_poss_lost_p90":        1.0,
    },
    "stoppeur": {
        "z_aerial_duels_pct":     2.5,
        "z_ground_duels_pct":     3.0,
        "z_interceptions_p90":    1.0,
        "z_dribbled_past_p90":    1.5,
        "z_errors_shot_p90":      1.5,
        "z_pass_acc_pct":         1.0,
    },
    "libero_defensif": {
        "z_interceptions_p90":    3.0,
        "z_ball_recovery_p90":    2.0,
        "z_aerial_duels_pct":     1.0,
        "z_ground_duels_pct":     2.0,
        "z_dribbled_past_p90":    2.0,
        "z_errors_shot_p90":      2.0,
        "z_fouls_p90":            1.0,
        "z_poss_lost_p90":        1.0,
        "z_pass_acc_pct":         1.5,
    },
    "tour_de_controle": {
        "z_aerial_duels_pct":     2.5,
        "z_aerial_duels_p90":     1.5,
        "z_headed_goals_p90":     1.5,
        "z_ground_duels_pct":     2.0,
        "z_dribbled_past_p90":    1.5,
        "z_errors_shot_p90":      2.0,
        "z_fouls_p90":            1.0,
        "z_pass_acc_pct":         1.0,
        "z_poss_lost_p90":        1.0,
    },

    # ── LATÉRAUX ─────────────────────────────────────────────────────
    "lateral_classique": {
        "z_ground_duels_pct":     2.0,
        "z_aerial_duels_pct":     1.0,
        "z_interceptions_p90":    1.5,
        "z_dribbled_past_p90":    2.0,
        "z_ball_recovery_p90":    1.0,
        "z_errors_shot_p90":      1.0,
        "z_fouls_p90":            1.0,
        "z_pass_acc_pct":         2.0,
        "z_poss_lost_p90":        1.0,
        "z_crosses_pct":          1.0,
    },
    "piston": {
        "z_ground_duels_pct":     1.5,
        "z_aerial_duels_pct":     1.0,
        "z_interceptions_p90":    1.5,
        "z_dribbled_past_p90":    1.0,
        "z_errors_shot_p90":      1.0,
        "z_pass_acc_pct":         2.0,
        "z_poss_lost_p90":        1.0,
        "z_crosses_p90":          1.0,
        "z_crosses_pct":          1.0,
        "z_xgchain_p90":          2.0,
        "z_passes_f3_p90":        2.0,
    },
    "defenseur_lateral": {
        "z_ground_duels_pct":     2.0,
        "z_aerial_duels_pct":     2.0,
        "z_dribbled_past_p90":    2.0,
        "z_interceptions_p90":    2.0,
        "z_ball_recovery_p90":    1.0,
        "z_errors_shot_p90":      2.0,
        "z_fouls_p90":            1.0,
        "z_pass_acc_pct":         1.0,
        "z_poss_lost_p90":        2.0,
    },
    "lateral_inverse": {
        "z_ground_duels_pct":     2.0,
        "z_interceptions_p90":    1.5,
        "z_dribbled_past_p90":    2.0,
        "z_errors_shot_p90":      1.0,
        "z_fouls_p90":            1.0,
        "z_pass_acc_pct":         2.5,
        "z_long_balls_pct":       1.5,
        "z_passes_f3_p90":        1.0,
        "z_xgchain_p90":          2.0,
        "z_poss_lost_p90":        2.0,
    },
    "lateral_pressing": {
        "z_poss_won_att3_p90":    2.5,
        "z_interceptions_p90":    1.5,
        "z_ball_recovery_p90":    1.5,
        "z_ground_duels_pct":     1.5,
        "z_ground_duels_p90":     2.0,
        "z_aerial_duels_pct":     1.0,
        "z_dribbled_past_p90":    1.0,
        "z_errors_shot_p90":      1.0,
        "z_pass_acc_pct":         1.0,
        "z_poss_lost_p90":        1.0,
    },

    # ── MILIEUX DÉFENSIFS ─────────────────────────────────────────────
    "sentinelle": {
        "z_interceptions_p90":    3.0,
        "z_ball_recovery_p90":    2.0,
        "z_tackles_p90":          1.0,
        "z_tackles_won_p90":      1.0,
        "z_ground_duels_pct":     1.0,
        "z_aerial_duels_pct":     1.5,
        "z_dribbled_past_p90":    1.0,
        "z_errors_shot_p90":      2.0,
        "z_pass_acc_pct":         2.0,
        "z_poss_lost_p90":        2.0,
    },
    "recuperateur_DM": {
        "z_ball_recovery_p90":    2.0,
        "z_interceptions_p90":    1.0,
        "z_tackles_p90":          2.0,
        "z_tackles_won_p90":      1.0,
        "z_ground_duels_pct":     2.0,
        "z_aerial_duels_pct":     1.0,
        "z_dribbled_past_p90":    1.5,
        "z_errors_shot_p90":      2.0,
        "z_pass_acc_pct":         1.0,
        "z_poss_lost_p90":        1.0,
    },
    "meneur_jeu_recule_DM": {
        "z_pass_acc_pct":         2.0,
        "z_acc_passes_p90":       1.0,
        "z_long_balls_pct":       2.0,
        "z_xgbuildup_p90":        1.0,
        "z_xgchain_p90":          1.0,
        "z_poss_lost_p90":        2.0,
        "z_interceptions_p90":    1.5,
        "z_ball_recovery_p90":    1.0,
        "z_ground_duels_pct":     1.0,
        "z_errors_shot_p90":      2.0,
    },

    # ── MILIEUX CENTRAUX ──────────────────────────────────────────────
    "recuperateur_CM": {
        "z_poss_won_att3_p90":    2.0,
        "z_ball_recovery_p90":    2.0,
        "z_interceptions_p90":    1.0,
        "z_ground_duels_pct":     2.0,
        "z_ground_duels_p90":     2.0,
        "z_aerial_duels_pct":     1.0,
        "z_dribbled_past_p90":    1.0,
        "z_errors_shot_p90":      1.0,
        "z_pass_acc_pct":         2.0,
        "z_poss_lost_p90":        1.0,
    },
    "box_to_box": {
        "z_interceptions_p90":    1.0,
        "z_ball_recovery_p90":    1.5,
        "z_ground_duels_pct":     1.0,
        "z_ground_duels_p90":     1.0,
        "z_dribbled_past_p90":    1.0,
        "z_errors_shot_p90":      1.0,
        "z_passes_f3_p90":        2.0,
        "z_xgchain_p90":          2.0,
        "z_touches_p90":          1.5,
        "z_poss_lost_p90":        1.0,
        "z_pass_acc_pct":         2.0,
        "z_npxg_p90":             1.0,
        "z_shots_ot_p90":         1.0,
    },
    "meneur_jeu_offensif_CM": {
        "z_xa_p90":               1.5,
        "z_big_chances_p90":      2.0,
        "z_passes_f3_p90":        1.0,
        "z_xgbuildup_p90":        1.5,
        "z_xgchain_p90":          1.0,
        "z_pass_acc_pct":         2.0,
        "z_dribbles_p90":         1.0,
        "z_dribble_pct":          1.0,
        "z_touches_p90":          1.0,
        "z_poss_lost_p90":        1.0,
        "z_shots_ot_p90":         1.5,
    },
    "meneur_jeu_recule_CM": {
        "z_pass_acc_pct":         2.0,
        "z_acc_passes_p90":       1.0,
        "z_long_balls_pct":       2.0,
        "z_xgbuildup_p90":        2.0,
        "z_xgchain_p90":          1.0,
        "z_poss_lost_p90":        2.0,
        "z_touches_p90":          1.0,
        "z_interceptions_p90":    1.0,
        "z_ball_recovery_p90":    1.0,
        "z_ground_duels_pct":     1.0,
        "z_errors_shot_p90":      1.0,
        "z_dribble_pct":          1.0,
    },

    # ── MILIEUX OFFENSIFS ─────────────────────────────────────────────
    "electron_libre": {
        "z_big_chances_p90":      1.0,
        "z_passes_f3_p90":        1.0,
        "z_xgbuildup_p90":        2.0,
        "z_xgchain_p90":          1.0,
        "z_pass_acc_pct":         2.0,
        "z_dribble_pct":          1.0,
        "z_poss_lost_p90":        1.0,
        "z_touches_p90":          1.5,
    },
    "meneur_jeu_offensif_AM": {
        "z_xa_p90":               1.0,
        "z_xgbuildup_p90":        2.0,
        "z_xgchain_p90":          1.0,
        "z_pass_acc_pct":         2.0,
        "z_acc_passes_p90":       1.0,
        "z_dribbles_p90":         1.0,
        "z_dribble_pct":          1.0,
        "z_touches_p90":          1.0,
        "z_poss_lost_p90":        1.0,
        "z_shots_ot_p90":         1.5,
        "z_npxg_p90":             1.0,
    },

    # ── AILIERS ───────────────────────────────────────────────────────
    "interieur": {
        "z_xa_p90":               1.0,
        "z_big_chances_p90":      2.0,
        "z_passes_f3_p90":        1.0,
        "z_xgbuildup_p90":        1.0,
        "z_xgchain_p90":          1.0,
        "z_pass_acc_pct":         1.5,
        "z_dribbles_p90":         1.0,
        "z_dribble_pct":          1.0,
        "z_poss_lost_p90":        1.0,
        "z_shots_ot_p90":         1.5,
        "z_penalty_won_p90":      1.0,
    },
    "profondeur_W": {
        "z_offsides_p90":         1.0,
        "z_shots_ot_p90":         1.0,
        "z_npxg_p90":             1.0,
        "z_goals_p90":            1.0,
        "z_np_goals_minus_npxg":  2.0,
        "z_big_miss_p90":         1.0,
        "z_penalty_won_p90":      1.0,
        "z_dribbles_p90":         1.0,
        "z_xgchain_p90":          2.0,
        "z_passes_f3_p90":        1.0,
    },
    "percuteur": {
        "z_dribbles_p90":         2.0,
        "z_dribble_pct":          2.0,
        "z_fouls_drawn_p90":      1.0,
        "z_penalty_won_p90":      1.0,
        "z_npxg_p90":             1.0,
        "z_goals_p90":            1.0,
        "z_big_chances_p90":      2.0,
    },
    "excentre": {
        "z_crosses_p90":          2.0,
        "z_crosses_pct":          2.0,
        "z_dribbles_p90":         1.0,
        "z_dribble_pct":          1.0,
        "z_xa_p90":               2.0,
        "z_big_chances_p90":      1.0,
        "z_dispossessed_p90":     1.0,
    },
    "ailier_defensif": {
        "z_poss_won_att3_p90":    3.0,
        "z_interceptions_p90":    1.0,
        "z_ball_recovery_p90":    1.0,
        "z_ground_duels_p90":     1.0,
        "z_dribbles_p90":         1.0,
        "z_dribble_pct":          1.0,
        "z_crosses_p90":          1.0,
        "z_xgchain_p90":          2.0,
        "z_pass_acc_pct":         1.0,
        "z_passes_f3_p90":        1.0,
    },

    # ── AVANT-CENTRES ─────────────────────────────────────────────────
    "pivot": {
        "z_aerial_duels_p90":     2.0,
        "z_aerial_duels_pct":     2.0,
        "z_headed_goals_p90":     2.0,
        "z_fouls_drawn_p90":      1.0,
        "z_poss_lost_p90":        1.0,
        "z_np_goals_minus_npxg":  2.0,
        "z_big_miss_p90":         1.0,
        "z_big_chances_p90":      1.0,
        "z_xgchain_p90":          1.0,
    },
    "profondeur_CF": {
        "z_offsides_p90":         1.0,
        "z_goals_p90":            2.0,
        "z_np_goals_minus_npxg":  3.0,
        "z_big_miss_p90":         1.0,
        "z_dribbles_p90":         1.0,
        "z_dribble_pct":          1.0,
        "z_penalty_won_p90":      1.0,
        "z_xgchain_p90":          1.0,
    },
    "faux_9": {
        "z_big_chances_p90":      1.0,
        "z_xgchain_p90":          1.0,
        "z_xgbuildup_p90":        2.0,
        "z_pass_acc_pct":         1.0,
        "z_goals_p90":            1.0,
        "z_np_goals_minus_npxg":  1.0,
        "z_dribbles_p90":         1.0,
        "z_dribble_pct":          1.0,
    },
    "renard_surfaces": {
        "z_goals_p90":            2.0,
        "z_np_goals_minus_npxg":  4.0,
        "z_goal_conv_pct":        1.0,
        "z_big_miss_p90":         1.0,
        "z_headed_goals_p90":     1.0,
        "z_penalty_won_p90":      1.0,
    },
    "attaquant_pressing": {
        "z_poss_won_att3_p90":    3.0,
        "z_ball_recovery_p90":    1.0,
        "z_interceptions_p90":    1.0,
        "z_fouls_drawn_p90":      1.0,
        "z_goals_p90":            2.0,
        "z_np_goals_minus_npxg":  1.5,
        "z_big_miss_p90":         1.0,
    },
}

# Groupes larges pour la normalisation z-score (compare les joueurs similaires)
ROLE_TO_GROUP = {
    role: data["group"]
    for role, data in FM_ROLES.items()
}
# GK seul dans son groupe
NORM_GROUPS = {
    "GK":  ["GK", "SK"],
    "DEF": ["CD", "BPD", "L", "SW", "FB", "WB", "IWB"],
    "MID": ["DM", "HB", "RGA", "BWM", "CM", "DLP", "MEZ", "BBM", "CAR", "AM", "SS", "T"],
    "ATT": ["W", "IW", "IF", "WTM", "CF", "AF", "DLF", "F9", "P", "TM", "PF"],
}
ROLE_TO_NORM_GROUP = {r: g for g, roles in NORM_GROUPS.items() for r in roles}


# ──────────────────────────────────────────────────────────────────
# CATALOGUE EXHAUSTIF DES FEATURES
# Format : (colonne_source, nom_feature, type, description, exemple, roles_pertinents)
# type : "vol" = per90, "pct" = déjà %, "raw" = garder tel quel
# ──────────────────────────────────────────────────────────────────

FEATURE_CATALOG = [

    # ── OFFENSIF — Buts & tirs ────────────────────────────────────
    ("goals",                    "goals_p90",           "vol",
     "But marqué — ballon franchissant entièrement la ligne de but, attribué au dernier joueur ayant touché le ballon intentionnellement",
     "Haaland reprend un centre de Bernardo Silva du pied droit — but",
     ["CF","W","AM","SS"]),

    ("expectedGoals",            "xg_p90",              "vol",
     "Probabilité qu'un tir donné se transforme en but, calculée sur la base de situations similaires dans la base historique Opta (~1 million de tirs). Facteurs : position, partie du corps, type de situation (ouvert/corner/coup franc), pression défensive. Échelle 0-1.",
     "Tir du pied droit à 12m face au but, sans gardien sorti : xG=0.38. Même tir de l'extérieur de la surface : xG=0.05",
     ["CF","W","AM","SS","CM"]),

    ("np_xg",                    "npxg_p90",            "vol",
     "xG total du joueur sur la saison, pénaltys exclus. Les pénaltys étant des tirs à xG fixe ~0.76 quelle que soit la qualité du tireur, ils sont retirés pour mesurer la vraie qualité des occasions en jeu ouvert.",
     "Joueur avec 18 xG dont 4 sur pénaltys → npxG = 14",
     ["CF","W","AM","SS","CM"]),

    ("_np_goals_minus_npxg",    "np_goals_minus_npxg", "vol",
     "Surperformance de finition : buts hors pénaltys − npxG. Positif = marque plus que prédit (finisseur efficace). Négatif = sous-performance. Normalisé per-90.",
     "Joueur : 8 np_goals, 6.5 npxG → +1.5 saison → ~+0.08/90. Haaland 23-24 : +15 au-dessus de son npxG",
     ["CF","W","AM"]),

    ("xGChain_us",               "xgchain_p90",         "vol",
     "Somme des xG de toutes les occasions auxquelles le joueur a participé dans la séquence de jeu, qu'il ait tiré, passé, ou simplement touché le ballon à n'importe quel moment de l'action. Très inclusif.",
     "Modric touche le ballon 3 passes avant le tir de Benzema (xG=0.25) → Modric reçoit 0.25 dans son xGChain",
     ["CF","W","AM","CM","DM","FB"]),

    ("xGBuildup_us",             "xgbuildup_p90",       "vol",
     "xGChain moins la contribution directe du tireur (xG) et du passeur décisif (xA). Mesure exclusivement les touches 'invisibles' en amont de la phase finale — la contribution à la construction profonde.",
     "Cancelo → De Bruyne → Haaland (but, xG=0.45). Cancelo : xGBuildup=0.45. De Bruyne : xGBuildup=0 (passeur déc. exclu). Haaland : xGBuildup=0 (tireur exclu)",
     ["CM","DM","CB","FB","AM"]),

    ("totalShots",               "shots_p90",           "vol",
     "Toute tentative délibérée de marquer, qu'elle soit cadrée, non-cadrée, bloquée ou sur le poteau. Exclut : les centres rentrants comptés comme but, les dégagements comptés comme tir.",
     "Frappe de 25m qui finit en tribunes = 1 tir. Tir bloqué par un défenseur = 1 tir (mais pas cadré)",
     ["CF","W","AM"]),

    ("shotsFromInsideTheBox",    "shots_inside_p90",    "vol",
     "Tirs tentés depuis l'intérieur de la surface de réparation (18 yards). Sous-ensemble de totalShots mesurant la présence offensive dans la zone de vérité, indépendamment de la précision.",
     "Haaland contrôle dans la surface à 7m et frappe au but = 1 tir depuis l'intérieur de la surface",
     ["CF","W","AM"]),

    ("headedGoals",              "headed_goals_p90",    "vol",
     "Buts marqués de la tête — sous-ensemble de goals attribués à une touche de tête intentionnelle. Indicateur de domination aérienne offensive.",
     "Giroud détourne un corner de la tête en haut du filet = 1 headed goal",
     ["CF","CD"]),

    ("_npxg_proxy_p90",          "npxg_proxy_p90",      "vol",
     "Proxy npxG calculé depuis les données Opta : xG total (expectedGoals) moins la contribution estimée des pénaltys (penaltiesTaken × 0.76). Clip à 0 pour éviter les valeurs négatives.",
     "Joueur avec expectedGoals=12.5 et penaltiesTaken=3 → npxg_proxy = 12.5 − 3×0.76 = 10.22",
     ["CF","W","AM","SS","CM"]),

    ("shotsOnTarget",            "shots_ot_p90",        "vol",
     "Tir cadré = tir qui serait rentré sans intervention du gardien ou du dernier défenseur. Inclut les buts. Exclut les tirs bloqués par un défenseur ordinaire (non dernier défenseur) et les tirs sur le poteau.",
     "Tir stoppé par le gardien = cadré. Tir bloqué par un défenseur en dehors de la ligne = non cadré. Tir sur le poteau = non cadré",
     ["CF","W","AM"]),

    ("goalConversionPercentage", "goal_conv_pct",       "pct",
     "Buts divisés par tirs totaux tentés, exprimé en pourcentage. Mesure l'efficacité brute de finition. Ne tient pas compte de la qualité des occasions (contrairement à xG).",
     "10 buts sur 50 tirs = 20%. Valeur moyenne PL ≈ 10-12%",
     ["CF","W","AM"]),

    ("bigChancesMissed",         "big_miss_p90",        "vol",
     "Situation individuelle où le tireur devrait raisonnablement marquer mais ne le fait pas. Mêmes critères que bigChancesCreated — appliqués au tireur plutôt qu'au créateur.",
     "Haaland seul face au gardien à 5m tire au-dessus = 1 big chance missed",
     ["CF","W"]),

    # ── OFFENSIF — Passes & création ─────────────────────────────
    ("assists",                  "ast_p90",             "vol",
     "Dernière action (passe, déviation, ou toute autre touche) menant directement au but du receveur. Si la passe décisive est déviée par un adversaire, une 'fantasy assist' est comptée pour le rating mais pas dans les stats officielles.",
     "De Bruyne centre, Haaland marque de la tête = assist De Bruyne. Si un défenseur dévie le centre et Haaland marque = pas d'assist officiel",
     ["W","AM","CM","CF","FB"]),

    ("passToAssist",             "pass_to_assist_p90",  "vol",
     "Avant-dernière passe dans une séquence aboutissant à un but — la passe qui mène à la passe décisive. Mesure la contribution créatrice en amont de la phase finale, invisible dans les stats assists.",
     "Kroos joue à Modric, Modric passe à Benzema qui marque → assist pour Modric, passToAssist pour Kroos",
     ["CM","AM","W"]),

    ("accurateFinalThirdPasses", "passes_f3_p90",       "vol",
     "Passes dont le point d'arrivée se situe dans le dernier tiers du terrain (33m finaux). Mesure la capacité à faire progresser le jeu vers l'avant. Ne requiert pas que la passe soit une passe clé.",
     "Busquets joue une passe depuis son propre camp vers Pedri dans le dernier tiers = 1 passToFinalThird",
     ["CM","DM","CB","AM"]),

    ("expectedAssists",          "xa_p90",              "vol",
     "xG de l'occasion créée par la passe, calculé au moment où le receveur tire. Mesure la qualité des passes menant à un tir, quel que soit le résultat du tir. Une passe vers un xG=0.5 vaut xA=0.5 même si le tir est raté.",
     "Passe dans la surface pour tir à bout portant (xG=0.45) = xA=0.45 pour le passeur. Passe vers une frappe lointaine (xG=0.03) = xA=0.03",
     ["W","AM","CM","CF","FB"]),

    ("xA_us",                    "xa_us_p90",           "vol",
     "xA calculé par Understat — probabilité de but générée par les passes du joueur, sur la base des tirs qui ont suivi. Méthodologie légèrement différente de l'xA Opta : Understat exclut les assistances sur pénaltys.",
     "De Bruyne joue 3 passes menant à des tirs (xG=0.35, 0.12, 0.08) → xA_us = 0.55 pour ce match",
     ["W","AM","CM","CF","FB"]),

    ("keyPasses",                "key_passes_p90",      "vol",
     "Passe menant directement à une tentative de but de l'équipe, sans être une passe décisive officielle (le tir ne se transforme pas en but). Critère : la passe doit être la dernière avant le tir.",
     "Ødegaard joue une passe à Saka qui tire, gardien arrête = 1 key pass pour Ødegaard. Si Saka marque = assist, pas key pass",
     ["AM","CM","W","CF","FB"]),

    ("bigChancesCreated",        "big_chances_p90",     "vol",
     "Passes ou actions menant à une situation où le receveur devrait raisonnablement être attendu à marquer. Inclut les pénaltys obtenus suite à une passe. Critère : face-à-face, tir à bout portant depuis la zone de vérité (< 6m), ou un-contre-un latéral.",
     "De Bruyne joue une passe dans le dos de la défense pour Haaland seul face au gardien = 1 big chance created",
     ["AM","CM","W","FB"]),

    ("passesToFinalThird",       "passes_f3_p90",       "vol",
     "Passes dont le point d'arrivée se situe dans le dernier tiers du terrain (33m finaux). Mesure la capacité à faire progresser le jeu vers l'avant. Ne requiert pas que la passe soit une passe clé.",
     "Busquets joue une passe depuis son propre camp vers Pedri dans le dernier tiers = 1 passToFinalThird",
     ["CM","DM","CB","AM"]),

    ("accuratePasses",           "acc_passes_p90",      "vol",
     "Nombre absolu de passes réussies sur la saison — passe qu'un coéquipier contrôle. Converti en per-90 pour la comparaison inter-joueurs. Exclut les corners, remises en jeu et dégagements gardien.",
     "Kroos : 85 passes réussies en 90min = 85 acc_passes pour ce match. Moyenne DM = 60-80 per-90",
     ["CM","DM","CB","AM"]),

    ("accuratePassesPercentage", "pass_acc_pct",        "pct",
     "Passes réussies divisées par passes tentées. Une passe est réussie si un coéquipier la contrôle. Exclut les corners, remises en jeu, dégagements du gardien et centres (comptés séparément).",
     "Kroos : 85 passes réussies / 90 tentées = 94.4%. Moyenne DM Premier League ≈ 82%",
     ["CM","DM","CB","FB","AM","GK"]),

    ("accurateLongBalls",        "long_balls_p90",      "vol",
     "Passes longues réussies — ballon joué en hauteur sur une distance significative (généralement >32m) récupéré par un coéquipier. Comptées en absolu per-90.",
     "Rúben Dias joue 8 longues passes dont 6 arrivent à un coéquipier = 6 long balls réussies",
     ["CB","DM","GK","CM"]),

    ("accurateLongBallsPercentage","long_balls_pct",    "pct",
     "Passes longues réussies sur passes longues tentées. Une passe longue est définie par Opta comme un ballon joué en hauteur sur une distance significative (généralement >32m). Indicateur clé des CBs relanceurs et gardiens modernes.",
     "Rúben Dias joue 8 longues passes, 6 arrivent à un coéquipier = 75% long balls",
     ["CB","DM","GK","CM"]),

    ("accurateCrosses",          "crosses_p90",         "vol",
     "Centres réussis — ballons intentionnels joués depuis une position latérale vers la zone devant le but, récupérés par un coéquipier. Comptés en absolu per-90.",
     "Trent croise 10 fois, 3 trouvent un coéquipier = 3 crosses réussies",
     ["FB","W","CM"]),

    ("accurateCrossesPercentage","crosses_pct",         "pct",
     "Centres réussis sur centres tentés. Un centre est défini comme tout ballon intentionnel joué depuis une position latérale vers la zone devant le but. Réussi = contrôlé par un coéquipier.",
     "Trent croise 10 fois, 3 trouvent un coéquipier = 30%. Valeur moyenne latéral PL ≈ 20-25%",
     ["FB","W","CM"]),

    ("totalCrosses",             "total_crosses_p90",   "vol",
     "Centres totaux tentés, réussis ou non. Mesure le volume de débordements et de jeu dans la largeur, indépendamment de la précision.",
     "Sané effectue 8 centres dans le match dont 2 réussis = 8 totalCrosses",
     ["FB","W"]),

    # ── POSSESSION & DRIBBLES ────────────────────────────────────
    ("touches",                  "touches_p90",         "vol",
     "Somme de tous les événements où le joueur touche le ballon — passe, tir, contrôle, dégagement, etc. Si un joueur contrôle puis passe, c'est 1 touche (l'action complète), pas 2.",
     "Iniesta reçoit, contrôle et passe en une action fluide = 1 touch. Un défenseur qui dévie involontairement un tir = 1 touch",
     ["CF","CM","DM","AM","W"]),

    ("successfulDribbles",       "dribbles_p90",        "vol",
     "Dribbles réussis — tentatives où le joueur bat l'adversaire en conservant la possession. Échoué si le dribbleur est taclé ou si le ballon s'éloigne trop (overrun).",
     "Neymar tente 8 dribbles, en réussit 6 = 6 successfulDribbles",
     ["W","CF","AM","CM"]),

    ("successfulDribblesPercentage","dribble_pct",      "pct",
     "Dribbles réussis sur dribbles tentés. Un dribble est réussi si le joueur bat l'adversaire en conservant la possession. Échoué si le dribbleur est taclé ou si le ballon s'éloigne trop (overrun).",
     "Neymar tente 8 dribbles, en réussit 6 = 75%. Valeur top ailier PL ≈ 55-65%",
     ["W","CF","AM"]),

    ("attemptedDribbles",        "dribbles_att_p90",    "vol",
     "Dribbles tentés — total des duels de dribble disputés, réussis ou non. Mesure le volume d'initiatives balle au pied, indépendamment de l'efficacité.",
     "Mbappé tente 6 dribbles dans un match = 6 attempted dribbles (qu'il en réussisse 4 ou 6)",
     ["W","CF","AM"]),

    ("dispossessed",             "dispossessed_p90",    "vol",
     "Sous-ensemble de possessionLost : uniquement les pertes de balle causées par un tacle adverse réussi sur le joueur en possession. Exclut les mauvaises passes et mauvais contrôles.",
     "Vinicius conduit, un défenseur le tacklé proprement et récupère le ballon = 1 dispossessed. Mauvaise passe de Vinicius = possessionLost mais pas dispossessed",
     ["W","CF","AM","CM"]),

    ("possessionLost",           "poss_lost_p90",       "vol",
     "Nombre de fois où le joueur perd la possession — tacle adverse réussi sur lui, mauvais contrôle, passe ratée dans les pieds adverses, interception subie. Comptabilisé uniquement quand la possession change d'équipe suite à l'action du joueur.",
     "Griezmann reçoit, adverse le tacklé et récupère le ballon = 1 possession lost pour Griezmann",
     ["CF","W","CM","DM","CB"]),

    ("possessionWonAttThird",    "poss_won_att3_p90",   "vol",
     "Ballons récupérés dans le tiers offensif adverse — résultat d'un pressing haut réussi ou d'une interception dans la zone ennemie. Indicateur d'intensité et d'efficacité du pressing offensif.",
     "Firmino presse le défenseur adverse dans son couloir défensif, provoque une mauvaise passe et récupère = 1 possession won att third",
     ["CF","W","AM","CM"]),

    ("wasFouled",                "fouls_drawn_p90",     "vol",
     "Fautes obtenues par le joueur — toute infraction sifflée par l'arbitre suite à un contact sur le joueur en possession ou cherchant à récupérer le ballon. Comptée indépendamment du carton éventuel.",
     "Salah percute un défenseur qui le fauche = 1 foul drawn pour Salah. Si l'arbitre siffle = 1 foul drawn, que ce soit carton ou non",
     ["CF","W","AM"]),

    ("ballRecovery",             "ball_recovery_p90",   "vol",
     "Récupération de balle — action où le joueur obtient la possession sur un ballon libre ou dévié, sans que ce soit un tacle direct sur porteur ni une interception anticipée. Inclut les segundas pelotas.",
     "Kanté se retrouve sur un rebond d'un tir adverse et récupère le ballon = 1 ball recovery",
     ["DM","CM","CD","FB"]),

    ("totalContest",             "dribbles_att_p90",    "vol",
     "Duels de dribble disputés (totalContest = total des contests dribble). Équivalent d'attemptedDribbles dans la nomenclature SofaScore. Mesure le volume d'initiatives balle au pied.",
     "Mbappé tente 6 dribbles dans un match = 6 totalContest (réussis ou non)",
     ["W","CF","AM"]),

    ("dribbledPast",             "dribbled_past_p90",   "vol",
     "Nombre de fois où un adversaire réussit un dribble sur ce joueur. Feature défensive à inverser : moins le joueur se fait dribbler, mieux c'est. Indicateur de solidité défensive individuelle au sol.",
     "Salah élimine le latéral adverse qui ne peut que le faucher = 1 dribbled past pour le défenseur",
     ["CD","FB"]),

    ("penaltyWon",               "penalty_won_p90",     "vol",
     "Pénalty accordé au joueur suite à une faute commise sur lui dans la surface adverse. Attribué au joueur fauté, pas au tireur si différent.",
     "Salah élimine un défenseur en surface, le défenseur le fauche → pénalty accordé à Salah",
     ["CF","W","AM"]),


    ("foulsDrawn",               "fouls_drawn_p90",     "vol",
     "Fautes obtenues par le joueur — toute infraction sifflée par l'arbitre suite à un contact sur le joueur en possession ou cherchant à récupérer le ballon. Comptée indépendamment du carton éventuel.",
     "Salah percute un défenseur qui le fauche = 1 foul drawn pour Salah. Si l'arbitre siffle = 1 foul drawn, que ce soit carton ou non",
     ["CF","W","AM"]),

    # ── DÉFENSIF ─────────────────────────────────────────────────
    ("fouls",                    "fouls_p90",           "vol",
     "Fautes commises — infractions sifflées suite à un contact irrégulier du joueur sur un adversaire. Comptée indépendamment du carton éventuel. Feature à inverser : moins = mieux.",
     "Tchouaméni tacklé irrégulièrement un adversaire, arbitre siffle = 1 foul. Valeur typique DM ≈ 2-3/match",
     ["DM","CB","CM"]),

    ("penaltyConceded",          "penalty_conc_p90",    "vol",
     "Pénalty concédé — faute commise par ce joueur dans sa propre surface de réparation, entraînant un pénalty pour l'adversaire. Feature à inverser : moins = mieux.",
     "Pavard fauche Mbappé dans la surface = 1 penalty conceded pour Pavard",
     ["CD","FB"]),

    ("outfielderBlocks",         "outfielder_blocks_p90","vol",
     "Bloc ou dégagement d'urgence d'un joueur de champ — intervention défensive où le joueur se sacrifie pour couper un tir ou une passe dangereuse dans la surface. Différent de blockedShots (moins strict sur la direction).",
     "Saliba plonge devant une frappe dans la surface et la dévie en corner = 1 outfielder block",
     ["CD","DM"]),

    ("duelLost",                 "duel_lost_p90",       "vol",
     "Duels perdus — contests 1v1 aériens ou au sol où l'adversaire remporte la possession. Pour chaque duel perdu d'un joueur, il y a un duel gagné côté adverse. Feature à inverser.",
     "Tchouaméni perd un duel au sol face à De Bruyne = 1 duel lost. Valeur typique DM ≈ 3-5/match",
     ["CD","DM","CM","CF"]),

    ("errorLeadToGoal",          "errors_goal_p90",     "vol",
     "Erreur individuelle d'un joueur menant DIRECTEMENT à un but encaissé. L'erreur doit être la cause directe sans phase de jeu intermédiaire. Très rare — 0 à 2 occurrences par saison pour la plupart des joueurs.",
     "Maguire perd le ballon dans sa propre surface, l'adversaire marque immédiatement = 1 errorLeadToGoal. Feature à inverser",
     ["CD","GK","FB"]),

    ("errorLeadToShot",          "errors_shot_p90",     "vol",
     "Erreur menant DIRECTEMENT à un tir adverse, but ou non. Sur-ensemble de errorLeadToGoal — chaque errorLeadToGoal est aussi un errorLeadToShot mais pas l'inverse. Légèrement plus fréquent (2-6/saison).",
     "Stones glisse et offre le ballon à Salah qui tire (gardien arrête) = 1 errorLeadToShot mais pas errorLeadToGoal",
     ["CD","GK","FB"]),

    ("totalCross",               "total_crosses_p90",   "vol",
     "Centres totaux tentés, réussis ou non. Colonne source alternative (totalCross vs totalCrosses) selon la version de l'API SofaScore.",
     "Sané effectue 8 centres dans le match dont 2 réussis = 8 totalCross",
     ["FB","W"]),

    ("tackles",                  "tackles_p90",         "vol",
     "Tacle réussi = le joueur entre en contact avec le ballon dans un duel au sol et récupère la possession ou dégage le ballon. Le joueur taclé doit clairement être en possession. Couper une passe n'est PAS un tacle (c'est une interception).",
     "Kanté glisse et rafle le ballon sous le pied de Pogba qui avait le contrôle = 1 tackle. Kanté intercepte une passe = interception, pas tackle",
     ["DM","CB","CM","FB"]),

    ("tacklesWon",               "tackles_won_p90",     "vol",
     "Sous-ensemble des tacles : tacles remportés où le joueur récupère proprement la possession après le tacle (pas seulement dégagé). Indicateur de qualité défensive au sol.",
     "Kanté tacklé Pogba et repart avec le ballon = 1 tackle won. Kanté dévie le ballon en touche = tacle mais pas won",
     ["DM","CB","CM","FB"]),

    ("_tackle_success_pct",      "tackle_success_pct",  "pct",
     "% tacles réussis = tacklesWon / tackles × 100. Mesure l'efficacité défensive au sol. Distingue le défenseur engagé précis (haut %) du défenseur brouillon qui tacle beaucoup mais perd souvent.",
     "Fabinho : 8 tacles, 6 remportés = 75% tackle success. Valeur top DM PL ≈ 65-75%",
     ["DM","CB","CM","FB"]),

    ("interceptions",            "interceptions_p90",   "vol",
     "Le joueur lit la passe adverse et se déplace dans la trajectoire du ballon pour l'intercepter. Geste ANTICIPATIF — le joueur doit se déplacer vers la ligne de passe avant que le ballon arrive. Différent du tacle (réactif sur porteur) et de la récupération (ballon libre).",
     "Fabinho lit une passe horizontale, se décale et intercepte le ballon dans sa course = 1 interception. Fabinho récupère un rebond qui traîne = ball recovery, pas interception",
     ["DM","CB","CM","FB"]),

    ("clearances",               "clearances_p90",      "vol",
     "Dégagement = action d'un joueur qui éloigne le ballon d'une zone dangereuse SANS cible précise — il n'essaie pas de passer à un coéquipier, juste de dégager le danger. Si une cible est identifiée, c'est une passe.",
     "Stones dégage un centre tendu de la tête dans les tribunes = 1 clearance. Stones contrôle le même centre et passe à Ederson = passe, pas clearance",
     ["CB","FB","DM"]),

    ("blockedShots",             "blocked_shots_p90",   "vol",
     "Joueur de champ qui bloque une tentative de but adverse. Condition stricte Opta : le tir doit être dirigé vers le but (aurait été cadré ou but sans le bloc). Si le tir allait de toute façon à côté, aucun bloc n'est comptabilisé.",
     "Van Dijk se jette devant la frappe de Salah adverse qui allait en haut du poteau = 1 blocked shot. Van Dijk dévie un tir qui allait largement à côté = 0 blocked shot",
     ["CB","DM","CM"]),

    ("errorsLeadingToGoal",      "errors_goal_p90",     "vol",
     "Erreur individuelle d'un joueur menant DIRECTEMENT à un but encaissé. L'erreur doit être la cause directe sans phase de jeu intermédiaire. Très rare — 0 à 2 occurrences par saison pour la plupart des joueurs.",
     "Maguire perd le ballon dans sa propre surface, l'adversaire marque immédiatement = 1 errorLeadingToGoal",
     ["CB","GK","FB"]),

    ("errorsLeadingToShot",      "errors_shot_p90",     "vol",
     "Erreur menant DIRECTEMENT à un tir adverse, but ou non. Sur-ensemble de errorsLeadingToGoal — chaque erreur menant à un but est aussi un errorLeadingToShot mais pas l'inverse. Légèrement plus fréquent (2-6/saison).",
     "Stones glisse et offre le ballon à Salah qui tire (gardien arrête) = 1 errorsLeadingToShot mais pas errorsLeadingToGoal",
     ["CB","GK","FB"]),

    ("_duels_won_p90",           "duels_won_p90",       "vol",
     "Duels gagnés par 90min — somme des duels au sol et aériens gagnés (groundDuelsWon + aerialDuelsWon), converti en per-90. Indicateur global de présence physique dans les duels.",
     "Tchouaméni : 4 duels sol gagnés + 2 duels aériens gagnés = 6 duels_won pour ce match",
     ["CB","DM","CM","CF"]),

    ("_duels_won_pct",           "duels_won_pct",       "pct",
     "% duels gagnés (tous types) — proxy calculé comme (groundDuelsWonPercentage + aerialDuelsWonPercentage) / 2. Indicateur global d'efficacité dans les duels 1v1.",
     "Tchouaméni : 67% duels sol + 58% duels aériens = 62.5% duels_won_pct",
     ["CB","DM","CM","CF","FB"]),

    ("groundDuelsWon",           "ground_duels_p90",    "vol",
     "Duels au sol gagnés — contests 50/50 sur le sol où le joueur récupère la possession. Comptés séparément des duels aériens. Indicateur de solidité physique au sol.",
     "Tchouaméni glisse dans un tacle et récupère le ballon face à De Bruyne = 1 ground duel won",
     ["DM","CM","CB","CF"]),

    ("groundDuelsWonPercentage", "ground_duels_pct",    "pct",
     "% duels au sol gagnés sur duels au sol disputés. Un duel est défini comme un contest 50/50 entre deux joueurs adverses. Indicateur de solidité au sol dans les duels 1v1.",
     "Tchouaméni : 6 duels sol gagnés / 9 disputés = 67%. Moyenne milieu défensif PL ≈ 55-60%",
     ["DM","CM","CB","CF"]),

    ("aerialDuelsWon",           "aerial_duels_p90",    "vol",
     "Duels aériens gagnés — challenges en l'air pour des centres, dégagements ou balles longues. Indicateur de domination physique aérienne. Comptés séparément des duels au sol.",
     "Giroud saute plus haut que le défenseur et capte un corner de la tête = 1 aerial duel won",
     ["CB","CF","DM"]),

    ("aerialDuelsWonPercentage", "aerial_duels_pct",    "pct",
     "Duels aériens gagnés sur duels aériens disputés. Un duel aérien nécessite 2+ joueurs qui challengent pour le même ballon en l'air. Gagné = le joueur obtient le premier contact contrôlé. Si fauté pendant le duel aérien, le joueur fauté gagne le duel.",
     "Giroud vs un défenseur sur corner : tous deux sautent, Giroud capte le ballon de la tête = Giroud gagne le duel aérien. Si le défenseur le fauche en sautant = Giroud gagne le duel (fauté)",
     ["CB","CF","DM","FB"]),

    ("foulsCommitted",           "fouls_p90",           "vol",
     "Fautes commises — infractions sifflées suite à un contact irrégulier du joueur sur un adversaire. Ancienne nomenclature Opta (= fouls dans les données actuelles). Feature à inverser.",
     "Tchouaméni tacklé irrégulièrement = 1 foulsCommitted. Valeur typique DM ≈ 2-3/match",
     ["DM","CB","CM"]),

    ("offsides",                 "offsides_p90",        "vol",
     "Hors-jeux signalés contre le joueur — position en avance sur le dernier défenseur au moment où le ballon est joué vers lui. Signal indirect de courses en profondeur dans le dos de la défense.",
     "Mbappé part dans le dos d'une défense, le assistant lève le drapeau = 1 offside. 8-10 hors-jeux/saison = joueur qui cherche la profondeur",
     ["CF","W"]),

    # ── GARDIEN ──────────────────────────────────────────────────
    ("saves",                    "saves_p90",           "vol",
     "Arrêts réalisés — tirs cadrés adverses stoppés par le gardien. Comptés uniquement sur les tirs qui auraient constitué un but sans l'intervention. Corrélé au volume de tirs adverses reçus.",
     "Alisson arrête un tir de Salah au premier poteau = 1 save. Alisson dévie un tir qui allait à côté = 0 save (pas cadré)",
     ["GK"]),

    ("cleanSheet",               "clean_sheets_p90",    "vol",
     "Match sans but encaissé — gardien ayant tenu sa cage à zéro pour la totalité du match joué. Per-90 utilisé comme proportion de matchs à zéro. Corrélé à la qualité défensive collective.",
     "Ederson joue 90min sans encaisser = 1 cleanSheet. Ederson sort à la 80e (0-0), remplaçant encaisse = pas de cleanSheet",
     ["GK"]),

    ("savedShotsFromInsideTheBox","saves_inside_p90",   "vol",
     "Arrêts sur tirs depuis l'intérieur de la surface de réparation — sous-ensemble des saves sur les tirs les plus dangereux (zone de vérité). Indicateur du niveau de difficulté des arrêts réalisés.",
     "Alisson arrête une frappe à bout portant de Haaland à 6m = 1 savedShotFromInsideTheBox",
     ["GK"]),

    ("savedShotsFromOutsideTheBox","saves_outside_p90", "vol",
     "Arrêts sur tirs depuis l'extérieur de la surface — saves sur frappes lointaines. Généralement plus prévisibles mais peuvent être déviées. Indicateur du volume de tirs lointains arrêtés.",
     "Alisson arrête une frappe de 25m de Salah qui allait dans le coin = 1 savedShotFromOutsideTheBox",
     ["GK"]),

    ("crossesNotClaimed",        "crosses_not_claimed_p90","vol",
     "Centres non interceptés par le gardien — ballon joué depuis les côtés vers la surface que le gardien n'a pas capté ni dégagé. Feature à inverser : plus ce nombre est élevé, moins le gardien contrôle sa surface.",
     "Un corner arrive dans la surface, Courtois ne sort pas et le ballon traîne = 1 crossNotClaimed",
     ["GK"]),

    ("high_claims_pct",          "high_claims_pct",     "pct",
     "Passes aériennes captées / (captées + ratées). highClaims = gardien sort et capte le ballon aérien. crossesNotClaimed = gardien sort pour capter un cross mais rate le ballon. Ratio de réussite sur les sorties aériennes tentées.",
     "Alisson : 28 highClaims, 3 crossesNotClaimed → high_claims_pct = 28/31 = 90.3%",
     ["GK"]),

    ("_penalty_save_pct",        "penalty_save_pct",    "pct",
     "% pénaltys arrêtés = penaltySave / penaltyFaced × 100. Mesure la performance du gardien sur penalty. Calculé uniquement pour les gardiens ayant fait face à au moins 1 pénalty saison.",
     "Alisson face à 5 pénaltys, en arrête 2 = 40% penalty_save_pct. Moyenne PL gardien ≈ 20-30%",
     ["GK"]),

    ("rating",                   "ss_rating",           "raw",
     "Note SofaScore calculée algorithmiquement à partir de l'ensemble des actions de jeu pondérées par poste. Échelle 1-10, mise à jour après chaque match. Utilisée comme benchmark de validation des scores du modèle.",
     "De Bruyne : moyenne 7.3 sur la saison = excellent. Moyenne joueur ≈ 6.8. Gardien bonne saison ≈ 7.0-7.2",
     ["ALL"]),

    ("_save_pct",                "save_pct",            "pct",
     "Arrêts réalisés divisés par tirs cadrés adverses reçus. Ne tient pas compte de la difficulté des tirs (contrairement à PSxG). Un gardien face à une équipe qui tire beaucoup de loin aura mécaniquement un bon % même s'il n'est pas excellent.",
     "Alisson : 112 arrêts / 140 tirs cadrés = 80%. Valeur top gardien PL ≈ 72-78%",
     ["GK"]),

    ("cleanSheets",              "clean_sheets_p90",    "vol",
     "Match sans but encaissé. Ancienne nomenclature Opta (= cleanSheet dans les données actuelles). Per-90 utilisé comme proportion de matchs à zéro.",
     "Ederson joue 90min sans encaisser = 1 cleanSheet",
     ["GK"]),

    ("goalsConceded",            "goals_conc_p90",      "vol",
     "Buts encaissés sur la saison. Feature à inverser : moins le gardien encaisse, mieux c'est. Corrélé à la qualité défensive collective — un gardien de grande équipe encaissera naturellement moins.",
     "Courtois encaisse 1 but par match en moyenne = 1 goal_conc_p90. Top gardien PL ≈ 0.8-1.0",
     ["GK"]),

    ("goalsPrevented",           "goals_prevented_p90", "vol",
     "Buts évités = arrêts réalisés moins xGoals concédés attendus. Mesure la surperformance du gardien par rapport aux attentes. Équivalent SofaScore du PSxG+/- de FBref. Positif = meilleur que prévu, négatif = moins bon.",
     "Ederson reçoit 45 tirs cadrés avec xGC=38.5, encaisse 34 buts → goalsPrevented = 38.5-34 = +4.5 (surperformance)",
     ["GK"]),

    ("highClaims",               "high_claims_p90",     "vol",
     "Captages hauts réussis — le gardien sort aériennement pour attraper ou dégager un centre ou corner en hauteur, en challengeant avec des attaquants adverses. Réussi = le gardien capture ou dégage proprement sans laisser la balle traîner.",
     "Alisson sort sur un corner, capte le ballon devant Lukaku qui challengeait = 1 high claim réussi. Alisson sort, perd le duel et le ballon traîne = 0 high claim réussi",
     ["GK"]),

    ("runsOut",                  "runs_out_p90",        "vol",
     "Sorties physiques du gardien HORS de sa surface de réparation pour intervenir sur le ballon — couper une passe longue, contrer un dribbleur en un-contre-un, dégager un ballon avant l'attaquant. Le gardien doit franchir la ligne des 18m.",
     "Neuer sort à 30m de son but pour couper un ballon dans le dos de Boateng = 1 runOut. Neuer sort à la limite de sa surface = 0 runOut",
     ["GK"]),

    ("successfulRunsOut",        "runs_out_suc_p90",    "vol",
     "Sous-ensemble des sorties (runsOut) réussies — le gardien récupère proprement le ballon ou le dégage sans laisser de rebond dangereux. Indicateur de précision dans les sorties hors surface.",
     "Neuer sort à 25m et capte le ballon proprement = 1 successful runOut. Neuer sort, rate le ballon, attaquant passe à côté = runOut non réussi",
     ["GK"]),

    ("runs_out_pct",             "runs_out_pct",        "pct",
     "Sorties hors surface réussies / sorties tentées. runsOut = gardien franchit la ligne des 18m pour intervenir sur le ballon. successfulRunsOut = parmi ces sorties, celles où il obtient le ballon.",
     "Neuer : 18 runsOut, 16 successfulRunsOut → runs_out_pct = 88.9%",
     ["GK"]),

    ("punches",                  "punches_p90",         "vol",
     "Dégagements au poing — action du gardien qui repousse le ballon du poing plutôt que de le capter. Souvent utilisé sur les centres difficiles à contrôler en conditions de pression.",
     "Lloris ne peut pas capter un corner tendu et repousse du poing = 1 punch",
     ["GK"]),

    ("savedShotsFromInsideBox",  "saves_inside_p90",    "vol",
     "Arrêts sur tirs depuis l'intérieur de la surface de réparation. Ancienne nomenclature API (= savedShotsFromInsideTheBox dans les données actuelles).",
     "Alisson arrête une frappe à bout portant = 1 savedShotFromInsideBox",
     ["GK"]),

    ("savedShotsFromOutsideBox", "saves_outside_p90",   "vol",
     "Arrêts sur tirs depuis l'extérieur de la surface. Ancienne nomenclature API (= savedShotsFromOutsideTheBox dans les données actuelles).",
     "Alisson arrête une frappe de 25m = 1 savedShotFromOutsideBox",
     ["GK"]),

    ("accurateLongBallsPercentage","gk_long_balls_pct", "pct",
     "% longues passes réussies du gardien — passes longues réussies / tentées. Indicateur clé du gardien relanceur ou sweeper keeper qui participe à la construction.",
     "Ederson joue 8 longues passes, 6 arrivent à un coéquipier = 75% gk_long_balls_pct",
     ["GK"]),

    # ── CONTEXTE ÉQUIPE (Understat) ───────────────────────────────
    ("ppda",                     "ppda_team",           "raw",
     "Passes Per Defensive Action — nombre de passes que l'équipe adverse réalise pour chaque action défensive (tacle, interception, faute) effectuée par l'équipe en phase de pressing. Bas = pressing intense. Haut = bloc bas, peu de pressing haut.",
     "Manchester City 2023 : ppda≈5.2 (pressing très intense, 1 action défensive toutes les 5 passes adverses). Leicester défensif : ppda≈14 (bloc bas, 1 action toutes les 14 passes)",
     ["ALL"]),

    ("oppda",                    "oppda_team",          "raw",
     "OPPDA (Opposing PPDA) — PPDA de l'équipe adverse subi par l'équipe du joueur. Mesure l'intensité du pressing adverse. Bas = l'équipe est soumise à un pressing intense de ses adversaires.",
     "Équipe qui joue contre des équipes peu agressives : oppda élevé. Équipe soumise à un pressing intense : oppda bas",
     ["ALL"]),

    ("deep",                     "deep_passes_team",    "raw",
     "Nombre de passes complétées dans les 40 derniers mètres du terrain adverse par match. Mesure la profondeur des phases offensives — une équipe avec un 'deep' élevé pénètre régulièrement dans la zone dangereuse par la passe.",
     "Équipe dominant possession : deep≈12-15. Équipe en contre : deep≈5-7",
     ["ALL"]),

    ("odc",                      "odc_team",            "raw",
     "Passes profondes concédées par match (dans les 40 derniers mètres du terrain propre). Mesure l'exposition défensive de l'équipe dans les zones dangereuses. Contexte pour interpréter les stats défensives individuelles.",
     "Équipe exposée défensivement : odc élevé. Équipe en bloc bas compact : odc faible",
     ["ALL"]),

    ("xp",                       "xp_team",             "raw",
     "Différence entre les points réels obtenus et les expected points (xPts) calculés sur la base des xG créés et concédés par match. Positif = équipe qui surperforme ses xG (chance, gardien excellent). Négatif = sous-performe.",
     "Liverpool xpts_diff=+6 : a obtenu 6 points de plus que ses xG ne le prédisaient → chance ou très bon gardien. Chelsea xpts_diff=-8 → sous-performance finition",
     ["ALL"]),

    ("xg",                       "xg_team",             "raw",
     "xG total de l'équipe sur la saison — mesure la qualité offensive de l'équipe indépendamment des résultats. Contexte pour interpréter les stats offensives individuelles.",
     "Man City : xG équipe=85/saison (excellente création offensive). Équipe de bas de tableau : xG≈35-45",
     ["ALL"]),

    ("xg_against",               "xga_team",            "raw",
     "xGA total de l'équipe sur la saison — xGoals concédés. Contexte défensif de l'équipe du joueur. Faible xGA = défense solide, évalue mieux la contribution défensive individuelle.",
     "Man City : xGA≈32/saison (défense hermétique). Équipe exposée : xGA≈60-70",
     ["ALL"]),

    # ── PROFIL JOUEUR (Transfermarkt) ─────────────────────────────
    ("age_tm",                   "age",                 "raw",
     "Âge du joueur au moment du scraping Transfermarkt. Donnée statique issue du profil officiel TM. Contexte pour pondérer la valeur marchande et anticiper l'évolution de carrière.",
     "Bellingham : 21 ans (prime value). Van Dijk : 33 ans (décote âge malgré niveau maintenu)",
     ["ALL"]),

    ("height",                   "height_cm",           "raw",
     "Taille en cm déclarée sur le profil officiel Transfermarkt du joueur. Donnée statique, issue des fiches officielles clubs / fédérations.",
     "Virgil van Dijk : 193cm. Thibaut Courtois : 199cm. Seuil 'tour de contrôle' CB : ≥188cm",
     ["CB","CF","GK"]),

    ("market_value",             "market_value",        "raw",
     "Estimation de la valeur marchande actuelle du joueur par la communauté Transfermarkt, mise à jour périodiquement. Basée sur l'âge, les performances, le contrat restant, l'inflation du marché. N'est pas une valeur contractuelle — c'est une estimation de ce qu'un club paierait.",
     "Bellingham évalué 200M€ = estimation TM communauté, pas valeur contractuelle. Kane à 30 ans : 80M€ vs 150M€ à 27 ans (décote âge)",
     ["ALL"]),
    # Historique MV volontairement exclu (valeur actuelle uniquement)
]


# ──────────────────────────────────────────────────────────────────
# FEATURES À INVERSER (plus = mieux → on inverse pour le scoring)
# ──────────────────────────────────────────────────────────────────
INVERTED_FEATURES = {
    "poss_lost_p90", "bad_touches_p90", "dispossessed_p90",
    "errors_goal_p90", "errors_shot_p90", "fouls_p90",
    "goals_conc_p90", "xg_conc_p90", "big_miss_p90", "offsides_p90",
    "dribbled_past_p90", "penalty_conc_p90", "duel_lost_p90",
    "crosses_not_claimed_p90",
}


# ──────────────────────────────────────────────────────────────────
# CALCUL
# ──────────────────────────────────────────────────────────────────

def parse_postes_list(val) -> list[str]:
    """Parse postes_list (JSON string ou liste) → liste Python."""
    if isinstance(val, list):
        return val
    if isinstance(val, str):
        try:
            result = json.loads(val)
            if isinstance(result, list):
                return result
        except (json.JSONDecodeError, ValueError):
            pass
    return ["CM"]


def get_norm_group(postes: list[str]) -> str:
    """Retourne le groupe de normalisation (GK/DEF/MID/ATT) selon le poste prioritaire."""
    for p in POSTE_PRIORITY:
        if p in postes:
            return POSTE_TO_NORM_GROUP.get(p, "MID")
    return "MID"


def get_fm_role_primary(postes: list[str]) -> str:
    """Retourne le code rôle FM court du poste prioritaire (compat affichage)."""
    for p in POSTE_PRIORITY:
        if p in postes:
            return POSTE_TO_FM_ROLE.get(p, "UNK")
    return "UNK"


def calc_per90(series: pd.Series, minutes: pd.Series) -> pd.Series:
    return (series / minutes * 90).replace([np.inf, -np.inf], np.nan)


def zscore_by_group(df: pd.DataFrame, col: str) -> pd.Series:
    """
    Z-score normalise par groupe large FM (GK / DEF / MID / ATT).
    On ne compare jamais un gardien a un milieu.
    """
    result = pd.Series(np.nan, index=df.index)
    for grp in ["GK", "DEF", "MID", "ATT"]:
        mask = df["norm_group"] == grp
        sub  = df.loc[mask, col].dropna()
        if len(sub) < 3:
            continue
        mu, sigma = sub.mean(), sub.std()
        if sigma > 0:
            result[mask & df[col].notna()] = (
                df.loc[mask & df[col].notna(), col] - mu
            ) / sigma
        else:
            result[mask] = 0.0
    return result


def build_all_features(df: pd.DataFrame) -> pd.DataFrame:
    """Calcule toutes les features pour tous les joueurs."""

    # Assigner postes_list, fm_role_primary et norm_group (CHANGEMENT 3)
    if "postes_list" in df.columns:
        postes_parsed = df["postes_list"].apply(parse_postes_list)
    else:
        # Fallback si postes_list absent (04_merge.py pas encore relancé)
        postes_parsed = pd.Series([["CM"]] * len(df), index=df.index)
        print("  ⚠  Colonne 'postes_list' absente — fallback CM pour tous")

    df["fm_role"]    = postes_parsed.apply(get_fm_role_primary)
    df["norm_group"] = postes_parsed.apply(get_norm_group)
    # Conserver postes_list parsée comme liste JSON pour le scoring
    df["postes_list"] = postes_parsed.apply(json.dumps)

    n_unk = (df["fm_role"] == "UNK").sum()
    if n_unk > 0:
        print(f"  ⚠  {n_unk} joueurs sans poste identifié — conservés avec fm_role=UNK")

    minutes = df["minutesPlayed"].clip(lower=MIN_MINUTES)

    # ── npxG proxy : xG Opta - xG pénaltys (0.76 par pénalty tenté) ─
    if "expectedGoals" in df.columns and "penaltiesTaken" in df.columns:
        xg  = pd.to_numeric(df["expectedGoals"], errors="coerce")
        pen = pd.to_numeric(df["penaltiesTaken"], errors="coerce").fillna(0)
        df["_npxg_proxy_p90"] = (xg - pen * 0.76).clip(lower=0)
    elif "expectedGoals" in df.columns:
        # Fallback : penaltyGoals comme proxy (sous-estime si penalties ratés)
        pg  = pd.to_numeric(df.get("penaltyGoals", pd.Series(0, index=df.index)), errors="coerce").fillna(0)
        xg  = pd.to_numeric(df["expectedGoals"], errors="coerce")
        df["_npxg_proxy_p90"] = (xg - pg * 0.76).clip(lower=0)

    # ── % arrêts sur penalty gardien ─────────────────────────────────
    if "penaltySave" in df.columns and "penaltyFaced" in df.columns:
        ps = pd.to_numeric(df["penaltySave"],  errors="coerce")
        pf = pd.to_numeric(df["penaltyFaced"], errors="coerce")
        df["_penalty_save_pct"] = (ps / pf.replace(0, pd.NA) * 100)

    # ── np_goals_minus_npxg : surperformance finishing ────────────────
    if "goals" in df.columns:
        goals_s  = pd.to_numeric(df["goals"], errors="coerce").fillna(0)
        pen_g    = pd.to_numeric(df.get("penaltyGoals", pd.Series(0, index=df.index)), errors="coerce").fillna(0)
        np_goals_s = goals_s - pen_g
        if "np_xg" in df.columns:
            np_xg_s = pd.to_numeric(df["np_xg"], errors="coerce")  # NaN si non matché Understat
            df["_np_goals_minus_npxg"] = np_goals_s - np_xg_s
        else:
            df["_np_goals_minus_npxg"] = np.nan

    # ── Parser market_value (ex: "€40.00m" → 40_000_000) ────────────
    if "market_value" in df.columns:
        def parse_mv(v):
            if pd.isna(v):
                return np.nan
            s = str(v).replace("€", "").replace(",", ".").strip()
            try:
                if "m" in s.lower():
                    return float(s.lower().replace("m", "")) * 1_000_000
                elif "k" in s.lower():
                    return float(s.lower().replace("k", "")) * 1_000
                else:
                    return float(s)
            except ValueError:
                return np.nan
        df["market_value"] = df["market_value"].apply(parse_mv)

    # ── Features calculées à partir des colonnes existantes ──────────
    # % tacles réussis
    if "tackles" in df.columns and "tacklesWon" in df.columns:
        t = pd.to_numeric(df["tackles"], errors="coerce")
        tw = pd.to_numeric(df["tacklesWon"], errors="coerce")
        df["_tackle_success_pct"] = (tw / t.replace(0, pd.NA) * 100)

    # Duels totaux gagnés = sol + aérien
    if "groundDuelsWon" in df.columns and "aerialDuelsWon" in df.columns:
        gd = pd.to_numeric(df["groundDuelsWon"], errors="coerce")
        ad = pd.to_numeric(df["aerialDuelsWon"], errors="coerce")
        # per90 calculé manuellement car c'est une somme (pas directement en vol)
        df["_duels_won_p90"] = (gd + ad)          # total saison → per90 dans la boucle
        # % duels : on n'a pas le total tenté directement → proxy via pct pondéré
        gdp = pd.to_numeric(df.get("groundDuelsWonPercentage", pd.Series(dtype=float)), errors="coerce")
        adp = pd.to_numeric(df.get("aerialDuelsWonPercentage", pd.Series(dtype=float)), errors="coerce")
        df["_duels_won_pct"] = (gdp + adp) / 2    # moyenne des deux % comme proxy

    # % arrêts gardien
    if "saves" in df.columns and "goalsConceded" in df.columns:
        sv = pd.to_numeric(df["saves"], errors="coerce")
        gc = pd.to_numeric(df["goalsConceded"], errors="coerce")
        df["_save_pct"] = sv / (sv + gc).replace(0, pd.NA) * 100

    # ── % high claims réussis ─────────────────────────────────────────
    if "crossesNotClaimed" in df.columns and "highClaims" in df.columns:
        hc = pd.to_numeric(df["highClaims"], errors="coerce")
        nc = pd.to_numeric(df["crossesNotClaimed"], errors="coerce")
        denominator = hc + nc
        df["high_claims_pct"] = np.where(denominator > 0, hc / denominator, np.nan)
    else:
        df["high_claims_pct"] = np.nan
        print("  INFO : crossesNotClaimed absent — high_claims_pct non calculé")

    # ── % sorties hors surface réussies ──────────────────────────────
    if "runsOut" in df.columns and "successfulRunsOut" in df.columns:
        ro = pd.to_numeric(df["runsOut"], errors="coerce")
        sr = pd.to_numeric(df["successfulRunsOut"], errors="coerce")
        df["runs_out_pct"] = np.where(ro > 0, sr / ro, np.nan)
    else:
        df["runs_out_pct"] = np.nan

    # ── Passes progressives (vraie colonne SS si dispo, sinon NaN) ───
    _prog_candidates = ["progressivePasses", "accurateProgressivePasses", "prgP"]
    _prog_src = next((c for c in _prog_candidates if c in df.columns), None)
    if _prog_src:
        df["_prog_passes_p90"] = pd.to_numeric(df[_prog_src], errors="coerce")
        print(f"  INFO : passes progressives depuis '{_prog_src}'")
    else:
        df["_prog_passes_p90"] = np.nan
        print("  INFO : aucune colonne passes progressives — _prog_passes_p90 non calculé")

    print(f"\n  Calcul de {len(FEATURE_CATALOG)} features...")

    for src_col, feat_name, feat_type, description, exemple, roles in FEATURE_CATALOG:
        if src_col not in df.columns:
            continue

        raw = pd.to_numeric(df[src_col], errors="coerce")

        # Calcul
        if feat_type == "vol":
            feat = calc_per90(raw, minutes)
        else:
            feat = raw

        # Clipping outliers (Winsorizing à 5%-95%)
        lo, hi = feat.quantile(0.05), feat.quantile(0.95)
        iqr = hi - lo
        if iqr > 0:
            feat = feat.clip(lower=lo - 2 * iqr, upper=hi + 2 * iqr)

        feat_col = f"feat_{feat_name}"
        df[feat_col] = feat

    # Défragmenter avant les z-scores (évite PerformanceWarning pandas)
    df = df.copy()

    # Z-scores
    print(f"  Calcul des z-scores par groupe de poste...")
    feat_cols = [c for c in df.columns if c.startswith("feat_")]
    z_cols_data = {}
    for feat_col in feat_cols:
        feat_name = feat_col.replace("feat_", "")
        z_vals = zscore_by_group(df, feat_col)
        if feat_name in INVERTED_FEATURES:
            z_vals = -z_vals
        z_cols_data[f"z_{feat_name}"] = z_vals

    df = pd.concat([df, pd.DataFrame(z_cols_data, index=df.index)], axis=1)

    return df


def compute_role_scores(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calcule un score 0-100 pour chaque rôle tactique (CHANGEMENT 5).

    Pour chaque rôle :
      1. Éligibilité  : joueurs dont postes_list contient le poste parent du rôle
      2. Score brut   : moyenne pondérée des z-scores (poids négatif = ré-inversion)
      3. Percentile   : scipy.stats.norm.cdf(score_brut) * 100
                        → 50 = joueur médian, 84 ≈ +1σ, 97.7 ≈ +2σ
    """
    df = df.copy()

    postes_series = df["postes_list"].apply(parse_postes_list)

    for role, weights in ROLE_FEATURES.items():
        parent_poste = ROLE_TO_POSTE.get(role)
        if parent_poste is None:
            continue

        eligible_mask = postes_series.apply(lambda p: parent_poste in p)
        col_name = f"score_{role}"
        df[col_name] = np.nan

        if eligible_mask.sum() == 0:
            continue

        raw_scores: list[float] = []
        idx_list: list = []

        for idx, row in df.loc[eligible_mask].iterrows():
            total_w = 0.0
            total_wz = 0.0
            for z_col, w in weights.items():
                if z_col not in row.index:
                    continue
                val = row[z_col]
                if pd.isna(val):
                    continue
                total_wz += w * val
                total_w  += abs(w)

            if total_w > 0:
                raw_scores.append(total_wz / total_w)
                idx_list.append(idx)

        if len(raw_scores) < 2:
            continue

        raw_arr = np.array(raw_scores)
        pct_arr = np.array([percentileofscore(raw_arr, v, kind="rank") for v in raw_arr])
        df.loc[idx_list, col_name] = pct_arr

    return df


def export_catalog() -> pd.DataFrame:
    """Exporte le catalogue des features en CSV."""
    rows = []
    for src_col, feat_name, feat_type, description, exemple, roles in FEATURE_CATALOG:
        rows.append({
            "source_column": src_col,
            "feature_name":  feat_name,
            "type":          feat_type,
            "description":   description,
            "exemple":       exemple,
            "relevant_roles":"|".join(roles) if isinstance(roles, list) else roles,
            "inverted":      feat_name in INVERTED_FEATURES,
            "feat_col":      f"feat_{feat_name}",
            "z_col":         f"z_{feat_name}",
        })
    return pd.DataFrame(rows)


def inspect_role(df: pd.DataFrame, role: str):
    sub = df[df["fm_role"] == role.upper()]
    if sub.empty:
        print(f"  ❌  Rôle '{role}' non trouvé. Rôles disponibles : {sorted(df['fm_role'].unique())}")
        return
    feat_cols = [c for c in sub.columns if c.startswith("feat_")]
    print(f"\n  Rôle {role.upper()} — {len(sub)} joueurs")
    # Afficher seulement les features pertinentes pour ce rôle
    relevant = [
        f"feat_{feat_name}"
        for _, feat_name, _, _, _, roles in FEATURE_CATALOG
        if role.upper() in (roles if isinstance(roles, list) else []) or roles == "ALL"
        and f"feat_{feat_name}" in sub.columns
    ]
    if relevant:
        print(sub[relevant].describe().round(3).to_string())
    else:
        print(sub[feat_cols].describe().round(3).to_string())


# ──────────────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Feature engineering exhaustif v2")
    parser.add_argument("--list-features",  action="store_true",
                        help="Afficher le catalogue complet des features")
    parser.add_argument("--inspect-role",   type=str, default=None,
                        help="Stats d'un rôle (GK/CB/FB/DM/CM/AM/W/CF)")
    args = parser.parse_args()

    print("\n" + "═" * 60)
    print("  FEATURE ENGINEERING v2 — Football Scoring Project")
    print("═" * 60)

    # Afficher le catalogue
    if args.list_features:
        cat = export_catalog()
        print(f"\n  {len(cat)} features dans le catalogue :\n")
        for _, row in cat.iterrows():
            inv = " [inversé]" if row["inverted"] else ""
            print(f"  {row['feat_col']:<45} {row['description'][:55]}{inv}")
        return

    master_path = MASTER_DIR / "players_master.csv"
    if not master_path.exists():
        print(f"  ❌  Fichier manquant : {master_path} — relancer 04_merge.py")
        return

    df = pd.read_csv(master_path, encoding="utf-8-sig")
    print(f"  Table maître : {len(df)} joueurs × {len(df.columns)} colonnes")

    # Filtre temps de jeu
    if "minutesPlayed" in df.columns:
        before = len(df)
        df = df[df["minutesPlayed"] >= MIN_MINUTES].copy()
        print(f"  Filtre ≥{MIN_MINUTES} min : {before} → {len(df)} joueurs")

    df = build_all_features(df)

    # Statistiques
    feat_cols  = [c for c in df.columns if c.startswith("feat_")]
    z_cols     = [c for c in df.columns if c.startswith("z_")]
    print(f"\n  {len(feat_cols)} features calculées")
    print(f"  {len(z_cols)} z-scores calculés")
    print(f"\n  Répartition par poste (fm_role_primary) :")
    for role, count in df["fm_role"].value_counts().items():
        grp = POSTE_TO_NORM_GROUP.get(role, POSTE_TO_NORM_GROUP.get(role, "?"))
        print(f"    {role:<6} [{grp}]  {count:>4} joueurs")
    n_multi = df["postes_list"].apply(parse_postes_list).apply(len).gt(1).sum()
    print(f"  Joueurs avec plusieurs postes : {n_multi}")

    # Exporter le catalogue
    cat = export_catalog()
    cat.to_csv(MASTER_DIR / "feature_catalog.csv", index=False, encoding="utf-8-sig")
    print(f"\n  Catalogue exporté : {MASTER_DIR}/feature_catalog.csv")

    # Sauvegarder les features (players_features_v2.csv — toutes les feat_ et z_)
    feat_path = MASTER_DIR / "players_features_v2.csv"
    df.to_csv(feat_path, index=False, encoding="utf-8-sig")
    print(f"  Features sauvegardées : {feat_path}")
    print(f"  {len(df)} joueurs × {len(df.columns)} colonnes")

    if args.inspect_role:
        inspect_role(df, args.inspect_role)

    # ── Calcul des scores par rôle (CHANGEMENT 5) ────────────────────
    print(f"\n  Calcul des scores pour {len(ROLE_FEATURES)} rôles tactiques...")
    df_scored = compute_role_scores(df)

    score_cols = [c for c in df_scored.columns if c.startswith("score_")]
    print(f"  {len(score_cols)} colonnes de scores créées")
    for role in ROLE_FEATURES:
        col = f"score_{role}"
        if col in df_scored.columns:
            n = df_scored[col].notna().sum()
            print(f"    {role:<30} {n:>4} joueurs scorés")

    # Output players_scores.csv
    id_cols = [c for c in [
        "master_id", "player_name", "team_name", "league", "season",
        "postes_list", "fm_role", "minutesPlayed",
        "age_tm", "market_value", "contract_expires", "nationality",
        "player_name_us", "player_name_tm",
    ] if c in df_scored.columns]

    scores_path = MASTER_DIR / "players_scores.csv"
    out_df = df_scored[id_cols + score_cols + feat_cols + z_cols]
    out_df.to_csv(scores_path, index=False, encoding="utf-8-sig")
    print(f"\n  ✅  Scores sauvegardés : {scores_path}")
    print(f"     {len(out_df)} joueurs × {len(out_df.columns)} colonnes")

    print("\n" + "═" * 60)
    print("  Prochaine étape : python 06_scoring.py  (affichage/ranking)")
    print("  Commandes utiles :")
    print("    python 05_features_v2.py --list-features")
    print("    python 05_features_v2.py --inspect-role DM")
    print("═" * 60 + "\n")


if __name__ == "__main__":
    main()
