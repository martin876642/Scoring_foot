"""
07_export_web.py
================
Génère maquette_site/players-data.js à partir des données réelles du pipeline.

Les features du radar utilisent EXACTEMENT les mêmes z-scores pondérés que
ceux définis dans ROLE_FEATURES de 05_features_v2.py.

Usage :
    python 07_export_web.py
    python 07_export_web.py --min-min 450
"""

import sys
import io
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

SCORES_PATH  = Path(__file__).parent.parent / "data" / "master" / "players_scores.csv"
MASTER_PATH  = Path(__file__).parent.parent / "data" / "master" / "players_master.csv"
OUTPUT_JS    = Path(__file__).parent.parent / "maquette_site" / "players-data.js"
IMAGES_PATH  = Path(__file__).parent.parent / "data" / "player_images.json"

# ──────────────────────────────────────────────────────────────────────────────
# ROLE_FEATURES_PY — copié depuis 05_features_v2.py
# Format : {role_python: {z_col: poids}}
# ──────────────────────────────────────────────────────────────────────────────
ROLE_FEATURES_PY: dict[str, dict[str, float]] = {
    "gardien_classique": {
        "z_acc_passes_p90":      1.0,
        "z_long_balls_pct":      1.0,
        "z_errors_shot_p90":     3.0,
        "z_penalty_save_pct":    1.5,
        "z_goals_prevented_p90": 5.0,
        "z_high_claims_pct":     2.0,
    },
    "gardien_libero": {
        "z_pass_acc_pct":        1.0,
        "z_long_balls_pct":      1.0,
        "z_errors_shot_p90":     3.0,
        "z_penalty_save_pct":    1.0,
        "z_goals_prevented_p90": 5.0,
        "z_runs_out_p90":        1.0,
        "z_runs_out_pct":        2.0,
        "z_high_claims_pct":     1.0,
    },
    "gardien_relanceur": {
        "z_xgchain_p90":         1.5,
        "z_pass_acc_pct":        2.0,
        "z_long_balls_pct":      2.0,
        "z_errors_shot_p90":     3.0,
        "z_penalty_save_pct":    1.0,
        "z_goals_prevented_p90": 5.0,
        "z_high_claims_pct":     1.0,
    },
    "defenseur_central": {
        "z_pass_acc_pct":        1.0,
        "z_long_balls_pct":      1.0,
        "z_poss_lost_p90":       2.0,
        "z_dribbled_past_p90":   1.5,
        "z_fouls_p90":           1.0,
        "z_errors_shot_p90":     2.0,
        "z_interceptions_p90":   3.0,
        "z_ground_duels_pct":    2.5,
        "z_aerial_duels_pct":    2.0,
    },
    "relanceur": {
        "z_aerial_duels_pct":    1.5,
        "z_ground_duels_pct":    2.0,
        "z_interceptions_p90":   2.0,
        "z_dribbled_past_p90":   2.0,
        "z_errors_shot_p90":     2.0,
        "z_fouls_p90":           1.0,
        "z_pass_acc_pct":        2.5,
        "z_long_balls_pct":      2.0,
        "z_xgchain_p90":         2.0,
        "z_poss_lost_p90":       1.0,
    },
    "stoppeur": {
        "z_aerial_duels_pct":    2.5,
        "z_ground_duels_pct":    3.0,
        "z_interceptions_p90":   1.0,
        "z_dribbled_past_p90":   1.5,
        "z_errors_shot_p90":     1.5,
        "z_pass_acc_pct":        1.0,
    },
    "libero_defensif": {
        "z_interceptions_p90":   3.0,
        "z_ball_recovery_p90":   2.0,
        "z_aerial_duels_pct":    1.0,
        "z_ground_duels_pct":    2.0,
        "z_dribbled_past_p90":   2.0,
        "z_errors_shot_p90":     2.0,
        "z_fouls_p90":           1.0,
        "z_poss_lost_p90":       1.0,
        "z_pass_acc_pct":        1.5,
    },
    "tour_de_controle": {
        "z_aerial_duels_pct":    2.5,
        "z_aerial_duels_p90":    1.5,
        "z_headed_goals_p90":    1.5,
        "z_ground_duels_pct":    2.0,
        "z_dribbled_past_p90":   1.5,
        "z_errors_shot_p90":     2.0,
        "z_fouls_p90":           1.0,
        "z_pass_acc_pct":        1.0,
        "z_poss_lost_p90":       1.0,
    },
    "lateral_classique": {
        "z_ground_duels_pct":    2.0,
        "z_aerial_duels_pct":    1.0,
        "z_interceptions_p90":   1.5,
        "z_dribbled_past_p90":   2.0,
        "z_ball_recovery_p90":   1.0,
        "z_errors_shot_p90":     1.0,
        "z_fouls_p90":           1.0,
        "z_pass_acc_pct":        2.0,
        "z_poss_lost_p90":       1.0,
        "z_crosses_pct":         1.0,
    },
    "piston": {
        "z_ground_duels_pct":    1.5,
        "z_aerial_duels_pct":    1.0,
        "z_interceptions_p90":   1.5,
        "z_dribbled_past_p90":   1.0,
        "z_errors_shot_p90":     1.0,
        "z_pass_acc_pct":        2.0,
        "z_poss_lost_p90":       1.0,
        "z_crosses_p90":         1.0,
        "z_crosses_pct":         1.0,
        "z_xgchain_p90":         2.0,
        "z_passes_f3_p90":       2.0,
    },
    "defenseur_lateral": {
        "z_ground_duels_pct":    2.0,
        "z_aerial_duels_pct":    2.0,
        "z_dribbled_past_p90":   2.0,
        "z_interceptions_p90":   2.0,
        "z_ball_recovery_p90":   1.0,
        "z_errors_shot_p90":     2.0,
        "z_fouls_p90":           1.0,
        "z_pass_acc_pct":        1.0,
        "z_poss_lost_p90":       2.0,
    },
    "lateral_inverse": {
        "z_ground_duels_pct":    2.0,
        "z_interceptions_p90":   1.5,
        "z_dribbled_past_p90":   2.0,
        "z_errors_shot_p90":     1.0,
        "z_fouls_p90":           1.0,
        "z_pass_acc_pct":        2.5,
        "z_long_balls_pct":      1.5,
        "z_passes_f3_p90":       1.0,
        "z_xgchain_p90":         2.0,
        "z_poss_lost_p90":       2.0,
    },
    "lateral_pressing": {
        "z_poss_won_att3_p90":   2.5,
        "z_interceptions_p90":   1.5,
        "z_ball_recovery_p90":   1.5,
        "z_ground_duels_pct":    1.5,
        "z_ground_duels_p90":    2.0,
        "z_aerial_duels_pct":    1.0,
        "z_dribbled_past_p90":   1.0,
        "z_errors_shot_p90":     1.0,
        "z_pass_acc_pct":        1.0,
        "z_poss_lost_p90":       1.0,
    },
    "sentinelle": {
        "z_interceptions_p90":   3.0,
        "z_ball_recovery_p90":   2.0,
        "z_tackles_p90":         1.0,
        "z_tackles_won_p90":     1.0,
        "z_ground_duels_pct":    1.0,
        "z_aerial_duels_pct":    1.5,
        "z_dribbled_past_p90":   1.0,
        "z_errors_shot_p90":     2.0,
        "z_pass_acc_pct":        2.0,
        "z_poss_lost_p90":       2.0,
    },
    "recuperateur_DM": {
        "z_ball_recovery_p90":   2.0,
        "z_interceptions_p90":   1.0,
        "z_tackles_p90":         2.0,
        "z_tackles_won_p90":     1.0,
        "z_ground_duels_pct":    2.0,
        "z_aerial_duels_pct":    1.0,
        "z_dribbled_past_p90":   1.5,
        "z_errors_shot_p90":     2.0,
        "z_pass_acc_pct":        1.0,
        "z_poss_lost_p90":       1.0,
    },
    "meneur_jeu_recule_DM": {
        "z_pass_acc_pct":        2.0,
        "z_acc_passes_p90":      1.0,
        "z_long_balls_pct":      2.0,
        "z_xgbuildup_p90":       1.0,
        "z_xgchain_p90":         1.0,
        "z_poss_lost_p90":       2.0,
        "z_interceptions_p90":   1.5,
        "z_ball_recovery_p90":   1.0,
        "z_ground_duels_pct":    1.0,
        "z_errors_shot_p90":     2.0,
    },
    "recuperateur_CM": {
        "z_poss_won_att3_p90":   2.0,
        "z_ball_recovery_p90":   2.0,
        "z_interceptions_p90":   1.0,
        "z_ground_duels_pct":    2.0,
        "z_ground_duels_p90":    2.0,
        "z_aerial_duels_pct":    1.0,
        "z_dribbled_past_p90":   1.0,
        "z_errors_shot_p90":     1.0,
        "z_pass_acc_pct":        2.0,
        "z_poss_lost_p90":       1.0,
    },
    "box_to_box": {
        "z_interceptions_p90":   1.0,
        "z_ball_recovery_p90":   1.5,
        "z_ground_duels_pct":    1.0,
        "z_ground_duels_p90":    1.0,
        "z_dribbled_past_p90":   1.0,
        "z_errors_shot_p90":     1.0,
        "z_passes_f3_p90":       2.0,
        "z_xgchain_p90":         2.0,
        "z_touches_p90":         1.5,
        "z_poss_lost_p90":       1.0,
        "z_pass_acc_pct":        2.0,
        "z_npxg_p90":            1.0,
        "z_shots_ot_p90":        1.0,
    },
    "meneur_jeu_offensif_CM": {
        "z_xa_p90":              1.5,
        "z_big_chances_p90":     2.0,
        "z_passes_f3_p90":       1.0,
        "z_xgbuildup_p90":       1.5,
        "z_xgchain_p90":         1.0,
        "z_pass_acc_pct":        2.0,
        "z_dribbles_p90":        1.0,
        "z_dribble_pct":         1.0,
        "z_touches_p90":         1.0,
        "z_poss_lost_p90":       1.0,
        "z_shots_ot_p90":        1.5,
    },
    "meneur_jeu_recule_CM": {
        "z_pass_acc_pct":        2.0,
        "z_acc_passes_p90":      1.0,
        "z_long_balls_pct":      2.0,
        "z_xgbuildup_p90":       2.0,
        "z_xgchain_p90":         1.0,
        "z_poss_lost_p90":       2.0,
        "z_touches_p90":         1.0,
        "z_interceptions_p90":   1.0,
        "z_ball_recovery_p90":   1.0,
        "z_ground_duels_pct":    1.0,
        "z_errors_shot_p90":     1.0,
        "z_dribble_pct":         1.0,
    },
    "electron_libre": {
        "z_big_chances_p90":     1.0,
        "z_passes_f3_p90":       1.0,
        "z_xgbuildup_p90":       2.0,
        "z_xgchain_p90":         1.0,
        "z_pass_acc_pct":        2.0,
        "z_dribble_pct":         1.0,
        "z_poss_lost_p90":       1.0,
        "z_touches_p90":         1.5,
    },
    "meneur_jeu_offensif_AM": {
        "z_xa_p90":              1.0,
        "z_xgbuildup_p90":       2.0,
        "z_xgchain_p90":         1.0,
        "z_pass_acc_pct":        2.0,
        "z_acc_passes_p90":      1.0,
        "z_dribbles_p90":        1.0,
        "z_dribble_pct":         1.0,
        "z_touches_p90":         1.0,
        "z_poss_lost_p90":       1.0,
        "z_shots_ot_p90":        1.5,
        "z_npxg_p90":            1.0,
    },
    "interieur": {
        "z_xa_p90":              1.0,
        "z_big_chances_p90":     2.0,
        "z_passes_f3_p90":       1.0,
        "z_xgbuildup_p90":       1.0,
        "z_xgchain_p90":         1.0,
        "z_pass_acc_pct":        1.5,
        "z_dribbles_p90":        1.0,
        "z_dribble_pct":         1.0,
        "z_poss_lost_p90":       1.0,
        "z_shots_ot_p90":        1.5,
        "z_penalty_won_p90":     1.0,
    },
    "profondeur_W": {
        "z_offsides_p90":        1.0,
        "z_shots_ot_p90":        1.0,
        "z_npxg_p90":            1.0,
        "z_goals_p90":           1.0,
        "z_np_goals_minus_npxg": 2.0,
        "z_big_miss_p90":        1.0,
        "z_penalty_won_p90":     1.0,
        "z_dribbles_p90":        1.0,
        "z_xgchain_p90":         2.0,
        "z_passes_f3_p90":       1.0,
    },
    "percuteur": {
        "z_dribbles_p90":        2.0,
        "z_dribble_pct":         2.0,
        "z_fouls_drawn_p90":     1.0,
        "z_penalty_won_p90":     1.0,
        "z_npxg_p90":            1.0,
        "z_goals_p90":           1.0,
        "z_big_chances_p90":     2.0,
    },
    "excentre": {
        "z_crosses_p90":         2.0,
        "z_crosses_pct":         2.0,
        "z_dribbles_p90":        1.0,
        "z_dribble_pct":         1.0,
        "z_xa_p90":              2.0,
        "z_big_chances_p90":     1.0,
        "z_dispossessed_p90":    1.0,
    },
    "ailier_defensif": {
        "z_poss_won_att3_p90":   3.0,
        "z_interceptions_p90":   1.0,
        "z_ball_recovery_p90":   1.0,
        "z_ground_duels_p90":    1.0,
        "z_dribbles_p90":        1.0,
        "z_dribble_pct":         1.0,
        "z_crosses_p90":         1.0,
        "z_xgchain_p90":         2.0,
        "z_pass_acc_pct":        1.0,
        "z_passes_f3_p90":       1.0,
    },
    "pivot": {
        "z_aerial_duels_p90":    2.0,
        "z_aerial_duels_pct":    2.0,
        "z_headed_goals_p90":    2.0,
        "z_fouls_drawn_p90":     1.0,
        "z_poss_lost_p90":       1.0,
        "z_np_goals_minus_npxg": 2.0,
        "z_big_miss_p90":        1.0,
        "z_big_chances_p90":     1.0,
        "z_xgchain_p90":         1.0,
    },
    "profondeur_CF": {
        "z_offsides_p90":        1.0,
        "z_goals_p90":           2.0,
        "z_np_goals_minus_npxg": 3.0,
        "z_big_miss_p90":        1.0,
        "z_dribbles_p90":        1.0,
        "z_dribble_pct":         1.0,
        "z_penalty_won_p90":     1.0,
        "z_xgchain_p90":         1.0,
    },
    "faux_9": {
        "z_big_chances_p90":     1.0,
        "z_xgchain_p90":         1.0,
        "z_xgbuildup_p90":       2.0,
        "z_pass_acc_pct":        1.0,
        "z_goals_p90":           1.0,
        "z_np_goals_minus_npxg": 1.0,
        "z_dribbles_p90":        1.0,
        "z_dribble_pct":         1.0,
    },
    "renard_surfaces": {
        "z_goals_p90":           2.0,
        "z_np_goals_minus_npxg": 4.0,
        "z_goal_conv_pct":       1.0,
        "z_big_miss_p90":        1.0,
        "z_headed_goals_p90":    1.0,
        "z_penalty_won_p90":     1.0,
    },
    "attaquant_pressing": {
        "z_poss_won_att3_p90":   3.0,
        "z_ball_recovery_p90":   1.0,
        "z_interceptions_p90":   1.0,
        "z_fouls_drawn_p90":     1.0,
        "z_goals_p90":           2.0,
        "z_np_goals_minus_npxg": 1.5,
        "z_big_miss_p90":        1.0,
    },
}

# ──────────────────────────────────────────────────────────────────────────────
# LABELS FRANÇAIS pour chaque z-col
# ──────────────────────────────────────────────────────────────────────────────
Z_COL_TO_LABEL: dict[str, str] = {
    "z_goals_p90":              "Buts /90",
    "z_npxg_p90":               "npxG /90",
    "z_xg_p90":                 "xG /90",
    "z_xgchain_p90":            "xGChain",
    "z_xgbuildup_p90":          "xGBuildup",
    "z_xa_p90":                 "xA /90",
    "z_xa_us_p90":              "xA US /90",
    "z_shots_p90":              "Tirs /90",
    "z_shots_ot_p90":           "Tirs cadrés /90",
    "z_shots_inside_p90":       "Tirs surface /90",
    "z_headed_goals_p90":       "Buts tête /90",
    "z_np_goals_minus_npxg":    "Surperf. finition",
    "z_goal_conv_pct":          "Conversion %",
    "z_big_miss_p90":           "Gros ratés /90",
    "z_big_chances_p90":        "Gr. chances créées",
    "z_npxg_proxy_p90":         "npxG proxy /90",
    "z_ast_p90":                "Passes déc. /90",
    "z_pass_to_assist_p90":     "Avant-dern. passe",
    "z_key_passes_p90":         "Passes clés /90",
    "z_passes_f3_p90":          "Passes dern. tiers",
    "z_acc_passes_p90":         "Passes réussies /90",
    "z_pass_acc_pct":           "Passes %",
    "z_long_balls_p90":         "Longues balles /90",
    "z_long_balls_pct":         "Passes longues %",
    "z_crosses_p90":            "Centres /90",
    "z_crosses_pct":            "Centres %",
    "z_total_crosses_p90":      "Centres tentés /90",
    "z_dribbles_p90":           "Dribbles /90",
    "z_dribble_pct":            "Dribbles %",
    "z_dribbles_att_p90":       "Dribbles tentés /90",
    "z_touches_p90":            "Touches /90",
    "z_dispossessed_p90":       "Dépossédé /90",
    "z_poss_lost_p90":          "Pertes balle /90",
    "z_poss_won_att3_p90":      "Récup. offensives",
    "z_fouls_drawn_p90":        "Fautes obtenues /90",
    "z_ball_recovery_p90":      "Récupérations /90",
    "z_penalty_won_p90":        "Pénaltys obtenus",
    "z_fouls_p90":              "Fautes commises /90",
    "z_penalty_conc_p90":       "Pénaltys concédés",
    "z_outfielder_blocks_p90":  "Blocs /90",
    "z_duel_lost_p90":          "Duels perdus /90",
    "z_errors_goal_p90":        "Erreurs → but",
    "z_errors_shot_p90":        "Erreurs → tir",
    "z_tackles_p90":            "Tacles /90",
    "z_tackles_won_p90":        "Tacles gagnés /90",
    "z_tackle_success_pct":     "Réussite tacles %",
    "z_interceptions_p90":      "Interceptions /90",
    "z_clearances_p90":         "Dégagements /90",
    "z_blocked_shots_p90":      "Tirs bloqués /90",
    "z_duels_won_p90":          "Duels gagnés /90",
    "z_duels_won_pct":          "Duels gagnés %",
    "z_ground_duels_p90":       "Duels sol /90",
    "z_ground_duels_pct":       "Duels sol %",
    "z_aerial_duels_p90":       "Duels aériens /90",
    "z_aerial_duels_pct":       "Duels aériens %",
    "z_dribbled_past_p90":      "Dribblé /90",
    "z_offsides_p90":           "Hors-jeux /90",
    "z_saves_p90":              "Arrêts /90",
    "z_clean_sheets_p90":       "Cleans /90",
    "z_saves_inside_p90":       "Arrêts surface /90",
    "z_saves_outside_p90":      "Arrêts ext. /90",
    "z_crosses_not_claimed_p90":"Centres non captés",
    "z_high_claims_pct":        "Sorties aériennes %",
    "z_high_claims_p90":        "Sorties hautes /90",
    "z_penalty_save_pct":       "Pénaltys arrêtés %",
    "z_save_pct":               "Arrêts %",
    "z_goals_conc_p90":         "Buts encaissés /90",
    "z_goals_prevented_p90":    "Buts évités /90",
    "z_runs_out_p90":           "Sorties terrain /90",
    "z_runs_out_suc_p90":       "Sort. réussies /90",
    "z_runs_out_pct":           "Sort. terrain %",
    "z_punches_p90":            "Dégagements poing",
    "z_gk_long_balls_pct":      "Passes longues %",
    "z_ppda_team":              "Pressing équipe",
    "z_oppda_team":             "Pressing adverse",
}

# ──────────────────────────────────────────────────────────────────────────────
# MAPPING rôle maquette (français) → rôle pipeline (python)
# Chaque rôle maquette utilise les features du rôle pipeline correspondant
# ──────────────────────────────────────────────────────────────────────────────
# Labels français pour chaque rôle pipeline — correspondance 1:1 avec ALL_ROLES de 06_scoring.py
ROLE_PY_LABELS: dict[str, str] = {
    # GK
    "gardien_classique":       "Gardien classique",
    "gardien_libero":          "Gardien libéro",
    "gardien_relanceur":       "Gardien relanceur",
    # CB
    "defenseur_central":       "Défenseur central",
    "stoppeur":                "Stoppeur",
    "libero_defensif":         "Libéro défensif",
    "tour_de_controle":        "Tour de contrôle",
    "relanceur":               "Relanceur",
    # FB
    "lateral_classique":       "Latéral classique",
    "piston":                  "Piston",
    "defenseur_lateral":       "Défenseur latéral",
    "lateral_inverse":         "Latéral inverse",
    "lateral_pressing":        "Latéral pressing",
    # DM
    "sentinelle":              "Sentinelle",
    "recuperateur_DM":         "Récupérateur (DM)",
    "meneur_jeu_recule_DM":    "Meneur reculé (DM)",
    # CM
    "recuperateur_CM":         "Récupérateur (CM)",
    "box_to_box":              "Box-to-box",
    "meneur_jeu_offensif_CM":  "Meneur offensif (CM)",
    "meneur_jeu_recule_CM":    "Meneur reculé (CM)",
    # AM
    "electron_libre":          "Électron libre",
    "meneur_jeu_offensif_AM":  "Meneur offensif (AM)",
    # W
    "interieur":               "Intérieur",
    "profondeur_W":            "Profondeur (W)",
    "percuteur":               "Percuteur",
    "excentre":                "Excentré",
    "ailier_defensif":         "Ailier défensif",
    # CF
    "profondeur_CF":           "Profondeur",
    "pivot":                   "Pivot",
    "faux_9":                  "Faux 9",
    "renard_surfaces":         "Renard des surfaces",
    "attaquant_pressing":      "Attaquant pressing",
}

# Mapping inverse : label français → code pipeline
MAQUETTE_ROLE_TO_PY: dict[str, str] = {v: k for k, v in ROLE_PY_LABELS.items()}

# Rôles par poste — TOUS les rôles du pipeline (32 rôles)
ROLES_BY_POSITION: dict[str, list[str]] = {
    "GK": ["Gardien classique", "Gardien libéro", "Gardien relanceur"],
    "CB": ["Défenseur central", "Stoppeur", "Libéro défensif", "Tour de contrôle", "Relanceur"],
    "FB": ["Latéral classique", "Piston", "Défenseur latéral", "Latéral inverse", "Latéral pressing"],
    "DM": ["Sentinelle", "Récupérateur (DM)", "Meneur reculé (DM)"],
    "CM": ["Récupérateur (CM)", "Box-to-box", "Meneur offensif (CM)", "Meneur reculé (CM)"],
    "AM": ["Électron libre", "Meneur offensif (AM)"],
    "W":  ["Intérieur", "Profondeur (W)", "Percuteur", "Excentré", "Ailier défensif"],
    "CF": ["Profondeur", "Pivot", "Faux 9", "Renard des surfaces", "Attaquant pressing"],
}

# Inverse: rôle → poste
ROLE_TO_POSITION: dict[str, str] = {
    r: pos for pos, roles in ROLES_BY_POSITION.items() for r in roles
}

# Transitions directes autorisées (paires naturelles en football)
# Volontairement restrictif pour éviter les faux positifs :
# on ne permet que les postes immédiatement adjacents.
ALLOWED_SECONDARY: dict[str, list[str]] = {
    "GK": [],
    "CB": ["FB"],
    "FB": ["CB"],
    "DM": ["CM"],
    "CM": ["DM"],
    "AM": ["CM"],
    "W":  ["CF", "AM"],
    "CF": ["W"],
}

# Seuil de score dérivé (0-100) — 70 = nettement au-dessus de la moyenne
SECONDARY_POSTE_THRESHOLD = 70

# Colonnes score par poste
SCORE_COLS_BY_POSTE: dict[str, list[str]] = {
    "GK": ["score_gardien_classique", "score_gardien_libero", "score_gardien_relanceur"],
    "CB": ["score_defenseur_central", "score_stoppeur", "score_relanceur",
           "score_libero_defensif", "score_tour_de_controle"],
    "FB": ["score_lateral_classique", "score_piston", "score_defenseur_lateral",
           "score_lateral_inverse", "score_lateral_pressing"],
    "DM": ["score_sentinelle", "score_recuperateur_DM", "score_meneur_jeu_recule_DM"],
    "CM": ["score_recuperateur_CM", "score_box_to_box",
           "score_meneur_jeu_offensif_CM", "score_meneur_jeu_recule_CM"],
    "AM": ["score_electron_libre", "score_meneur_jeu_offensif_AM"],
    "W":  ["score_interieur", "score_profondeur_W", "score_percuteur",
           "score_excentre", "score_ailier_defensif"],
    "CF": ["score_profondeur_CF", "score_pivot", "score_faux_9",
           "score_renard_surfaces", "score_attaquant_pressing"],
}

LEAGUE_MAP: dict[str, dict] = {
    "England Premier League": {"nom": "Premier League", "la": "PL", "couleur": "#3b2e7e"},
    "France Ligue 1":         {"nom": "Ligue 1",        "la": "L1", "couleur": "#003189"},
    "Germany Bundesliga":     {"nom": "Bundesliga",     "la": "BL", "couleur": "#c40000"},
    "Italy Serie A":          {"nom": "Serie A",        "la": "SA", "couleur": "#1a4fa0"},
    "Spain La Liga":          {"nom": "La Liga",        "la": "LL", "couleur": "#ffbe00"},
}

POSITION_LABEL: dict[str, str] = {
    "GK": "Gardien", "CB": "Défenseur central", "FB": "Latéral",
    "DM": "Milieu défensif", "CM": "Milieu central", "AM": "Milieu offensif",
    "W": "Ailier", "CF": "Avant-centre",
}

# ROLE_PY_TO_FR = même chose que ROLE_PY_LABELS (défini plus haut)
ROLE_PY_TO_FR = ROLE_PY_LABELS

NATION_FLAG: dict[str, str] = {
    "Afghanistan": "🇦🇫", "Albania": "🇦🇱", "Algeria": "🇩🇿", "Argentina": "🇦🇷",
    "Australia": "🇦🇺", "Austria": "🇦🇹", "Belgium": "🇧🇪", "Bolivia": "🇧🇴",
    "Bosnia and Herzegovina": "🇧🇦", "Brazil": "🇧🇷", "Bulgaria": "🇧🇬", "Burkina Faso": "🇧🇫",
    "Cameroon": "🇨🇲", "Canada": "🇨🇦", "Chile": "🇨🇱", "China": "🇨🇳",
    "Colombia": "🇨🇴", "Congo": "🇨🇩", "Costa Rica": "🇨🇷", "Croatia": "🇭🇷",
    "Czech Republic": "🇨🇿", "Czechia": "🇨🇿", "Côte d'Ivoire": "🇨🇮", "Denmark": "🇩🇰",
    "DR Congo": "🇨🇩", "Ecuador": "🇪🇨", "Egypt": "🇪🇬", "England": "🏴󠁧󠁢󠁥󠁮󠁧󠁿",
    "Ethiopia": "🇪🇹", "Finland": "🇫🇮", "France": "🇫🇷", "Gabon": "🇬🇦",
    "Georgia": "🇬🇪", "Germany": "🇩🇪", "Ghana": "🇬🇭", "Greece": "🇬🇷",
    "Guinea": "🇬🇳", "Guinea-Bissau": "🇬🇼", "Honduras": "🇭🇳", "Hungary": "🇭🇺",
    "Iceland": "🇮🇸", "Iran": "🇮🇷", "Iraq": "🇮🇶", "Ireland": "🇮🇪",
    "Israel": "🇮🇱", "Italy": "🇮🇹", "Jamaica": "🇯🇲", "Japan": "🇯🇵",
    "Jordan": "🇯🇴", "Kazakhstan": "🇰🇿", "Kosovo": "🇽🇰", "Mali": "🇲🇱",
    "Mexico": "🇲🇽", "Moldova": "🇲🇩", "Montenegro": "🇲🇪", "Morocco": "🇲🇦",
    "Netherlands": "🇳🇱", "Nigeria": "🇳🇬", "North Macedonia": "🇲🇰",
    "Northern Ireland": "🇬🇧", "Norway": "🇳🇴", "Panama": "🇵🇦",
    "Paraguay": "🇵🇾", "Peru": "🇵🇪", "Poland": "🇵🇱", "Portugal": "🇵🇹",
    "Republic of Ireland": "🇮🇪", "Romania": "🇷🇴", "Russia": "🇷🇺",
    "Scotland": "🏴󠁧󠁢󠁳󠁣󠁴󠁿", "Senegal": "🇸🇳", "Serbia": "🇷🇸", "Slovakia": "🇸🇰",
    "Slovenia": "🇸🇮", "South Korea": "🇰🇷", "Spain": "🇪🇸", "Sweden": "🇸🇪",
    "Switzerland": "🇨🇭", "Syria": "🇸🇾", "Tunisia": "🇹🇳", "Turkey": "🇹🇷",
    "Ukraine": "🇺🇦", "United States": "🇺🇸", "Uruguay": "🇺🇾",
    "Venezuela": "🇻🇪", "Wales": "🏴󠁧󠁢󠁷󠁬󠁳󠁿", "Zambia": "🇿🇲", "Zimbabwe": "🇿🇼",
    "Cape Verde": "🇨🇻", "Comoros": "🇰🇲", "Mozambique": "🇲🇿",
}


def slugify(name: str) -> str:
    import unicodedata, re
    n = unicodedata.normalize("NFD", name)
    n = "".join(c for c in n if unicodedata.category(c) != "Mn")
    n = n.lower()
    n = re.sub(r"[^a-z0-9]+", "-", n).strip("-")
    return n


def z_to_pct(z: float | None) -> int | None:
    if z is None or (isinstance(z, float) and np.isnan(z)):
        return None
    pct = norm.cdf(float(z)) * 100
    return int(np.clip(round(pct), 5, 95))


def build_club_color(team: str) -> str:
    h = 0
    for c in team:
        h = (h * 31 + ord(c)) & 0xFFFFFFFF
    hue = h % 360
    sat = 55 + (h // 360) % 20
    lig = 25 + (h // 7200) % 20

    def hsl_to_hex(h, s, l):
        s /= 100; l /= 100
        c = (1 - abs(2 * l - 1)) * s
        x = c * (1 - abs((h / 60) % 2 - 1))
        m = l - c / 2
        if h < 60:   r, g, b = c, x, 0
        elif h < 120: r, g, b = x, c, 0
        elif h < 180: r, g, b = 0, c, x
        elif h < 240: r, g, b = 0, x, c
        elif h < 300: r, g, b = x, 0, c
        else:         r, g, b = c, 0, x
        r, g, b = int((r + m) * 255), int((g + m) * 255), int((b + m) * 255)
        return f"#{r:02x}{g:02x}{b:02x}"

    return hsl_to_hex(hue, sat, lig)


def get_primary_poste(postes_list_json: str) -> str | None:
    try:
        postes = json.loads(postes_list_json)
        return postes[0] if postes else None
    except Exception:
        return None


def get_best_role(row: pd.Series, poste: str) -> tuple[str, float]:
    cols = SCORE_COLS_BY_POSTE.get(poste, [])
    best_role, best_score = "", -1.0
    for col in cols:
        val = row.get(col, np.nan)
        if pd.notna(val) and float(val) > best_score:
            best_score = float(val)
            best_role = col.replace("score_", "")
    return best_role, best_score


def build_role_features_web() -> dict[str, list[str]]:
    """
    Construit ROLE_FEATURES pour la maquette JS à partir des ROLE_FEATURES_PY du pipeline.
    Retourne {role_fr: [label_feature, ...]} avec les 6 features les plus pondérées.
    """
    result: dict[str, list[str]] = {}
    for role_fr, py_role in MAQUETTE_ROLE_TO_PY.items():
        py_feats = ROLE_FEATURES_PY.get(py_role, {})
        if not py_feats:
            continue
        # Toutes les features, triées par poids décroissant
        sorted_feats = sorted(py_feats.items(), key=lambda x: -x[1])
        labels = [Z_COL_TO_LABEL.get(col, col) for col, _ in sorted_feats]
        result[role_fr] = labels
    return result


def compute_z_features_for_player(
    row: pd.Series,
    postes_all: list[str],
    role_features_web: dict[str, list[str]],
) -> dict[str, dict[str, int | None]]:
    """
    Pour chaque rôle de TOUS les postes du joueur, calcule {label: percentile}.
    Couvre les postes secondaires (ex: CM+W) pour le sélecteur de poste.
    """
    result: dict[str, dict[str, int | None]] = {}
    roles_seen: set[str] = set()

    # Construire la liste de rôles à calculer (tous les postes, sans doublon)
    roles_for_poste = []
    for poste in postes_all:
        for role_fr in ROLES_BY_POSITION.get(poste, []):
            if role_fr not in roles_seen:
                roles_seen.add(role_fr)
                roles_for_poste.append(role_fr)

    for role_fr in roles_for_poste:
        py_role = MAQUETTE_ROLE_TO_PY.get(role_fr)
        if not py_role:
            continue
        py_feats = ROLE_FEATURES_PY.get(py_role, {})
        # Toutes les features, triées par poids décroissant
        sorted_feats = sorted(py_feats.items(), key=lambda x: -x[1])
        feats: dict[str, int | None] = {}
        for z_col, _ in sorted_feats:
            label = Z_COL_TO_LABEL.get(z_col, z_col)
            z_val = row.get(z_col, np.nan)
            feats[label] = z_to_pct(z_val if pd.notna(z_val) else None)
        result[role_fr] = feats

    return result


def derive_poste_score(row: pd.Series, poste: str) -> float:
    """
    Calcule un score (0-100) pour un joueur dans un poste donné
    en faisant la moyenne pondérée de ses z-scores sur tous les rôles du poste.
    Utilisé pour inférer les postes secondaires sans re-scraper TM.
    """
    scores = []
    for role_fr in ROLES_BY_POSITION.get(poste, []):
        py_role = MAQUETTE_ROLE_TO_PY.get(role_fr)
        if not py_role:
            continue
        py_feats = ROLE_FEATURES_PY.get(py_role, {})
        if not py_feats:
            continue
        total_w = sum(py_feats.values())
        weighted = sum(
            (z_to_pct(row.get(z_col, np.nan)) or 50) * w
            for z_col, w in py_feats.items()
        )
        scores.append(weighted / total_w if total_w else 50)
    return max(scores) if scores else 0.0


def infer_postes_all(row: pd.Series, primary_poste: str,
                     tm_postes: list[str]) -> list[str]:
    """
    Construit la liste complète des postes du joueur :
    1. Postes TM (pipeline) → TOUJOURS inclus, sans filtre de score.
    2. Postes secondaires inférés par z-scores → seulement si TM ne les fournit pas
       ET si le score dépasse le seuil ET si la transition est autorisée.
    """
    # Étape 1 : tous les postes TM tels quels
    postes: list[str] = list(tm_postes)

    # Étape 2 : inférence complémentaire par z-scores (seulement pour combler les lacunes TM)
    for candidate in ALLOWED_SECONDARY.get(primary_poste, []):
        if candidate in postes:
            continue  # déjà connu par TM → pas besoin d'inférer
        score = derive_poste_score(row, candidate)
        if score >= SECONDARY_POSTE_THRESHOLD:
            postes.append(candidate)

    return postes


def build_players_db(df: pd.DataFrame, master: pd.DataFrame,
                     role_features_web: dict[str, list[str]],
                     player_images: dict[str, str | None] | None = None) -> list[dict]:
    # Colonnes utiles du master
    master_slim = master[["master_id", "goals", "appearances"]].drop_duplicates("master_id")
    df = df.merge(master_slim, on="master_id", how="left", suffixes=("", "_m"))

    players = []
    for _, row in df.iterrows():
        poste = get_primary_poste(str(row.get("postes_list", "[]")))
        if poste is None:
            continue

        best_role_py, best_score = get_best_role(row, poste)
        role_fr = ROLE_PY_TO_FR.get(best_role_py, "")
        if not role_fr:
            continue

        league_raw = str(row.get("league", ""))
        league_info = LEAGUE_MAP.get(league_raw, {"nom": league_raw, "la": "??", "couleur": "#444"})

        team = str(row.get("team_name", "Inconnu"))
        club_abbr = team[:3].upper() if len(team) >= 3 else team.upper()
        club_color = build_club_color(team)

        nat = str(row.get("nationality", ""))
        nat_flag = NATION_FLAG.get(nat, "🏳️")
        nat_code = nat[:3].upper() if nat else "UNK"

        minutes = float(row.get("minutesPlayed", 0) or 0)
        apps = float(row.get("appearances", 0) or 0)
        min_per_match = round(minutes / apps) if apps > 0 else 0

        goals_raw = float(row.get("goals", 0) or 0)
        xg_p90 = float(row.get("feat_xg_p90", 0) or 0)
        xg_season = round(xg_p90 * minutes / 90, 1)

        market_value_raw = float(row.get("market_value", 0) or 0)
        valeur_meur = round(market_value_raw / 1_000_000, 1)

        contrat_raw = str(row.get("contract_expires", "") or "")
        # Convertir "Jun 30, 2028" → "06/2028", ou garder brut si format inconnu
        import re as _re
        mo = _re.match(
            r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d+,?\s+(\d{4})",
            contrat_raw, _re.I,
        )
        MONTH_NUM = {"jan":"01","feb":"02","mar":"03","apr":"04","may":"05","jun":"06",
                     "jul":"07","aug":"08","sep":"09","oct":"10","nov":"11","dec":"12"}
        contrat = f"{MONTH_NUM.get(mo.group(1)[:3].lower(), '??')}/{mo.group(2)}" if mo else contrat_raw or "—"

        age_raw = row.get("age_tm", np.nan)
        if pd.isna(age_raw):
            age_raw = row.get("feat_age", np.nan)
        age = int(round(float(age_raw))) if pd.notna(age_raw) else 0

        # Taille en cm (feat_height_cm stocke en mètres malgré son nom)
        h_raw = row.get("feat_height_cm", np.nan)
        taille = int(round(float(h_raw) * 100)) if pd.notna(h_raw) and float(h_raw) > 0 else 0

        # Pied préféré (non disponible pour l'instant dans le pipeline)
        pied = str(row.get("foot", "")) or "D"

        score = int(round(float(best_score)))
        score = max(1, min(99, score))

        # Postes TM existants puis enrichissement par z-scores
        tm_postes = json.loads(str(row.get("postes_list", f'["{poste}"]') or f'["{poste}"]'))
        postes_all_list = infer_postes_all(row, poste, tm_postes)
        z_feats = compute_z_features_for_player(row, postes_all_list, role_features_web)

        player = {
            "id":          slugify(str(row["player_name"])),
            "nom":         str(row["player_name"]),
            "nationalite": {"code": nat_code, "flag": nat_flag},
            "age":         age,
            "taille":      taille,
            "pied":        pied if pied in ("D", "G") else "D",
            "clubAbbr":    club_abbr,
            "club": {
                "nom":    team,
                "couleur": club_color,
                "ligue":  league_info["nom"],
                "la":     league_info["la"],
            },
            "poste":       poste,
            "postesAll":   postes_all_list,
            "posteLabel":  POSITION_LABEL.get(poste, poste),
            "role":        role_fr,
            "score":       score,
            "valeur":      valeur_meur,
            "contrat":     contrat,
            "min90":       min_per_match,
            "buts":        int(goals_raw),
            "xg":          xg_season,
            "photoUrl":    (player_images or {}).get(str(row["player_name"])),
            "zFeats":      z_feats,
        }
        players.append(player)

    return players


def compute_rankings(players: list[dict]) -> None:
    from collections import defaultdict
    by_poste_ligue: dict = defaultdict(list)
    by_poste_big5:  dict = defaultdict(list)
    for p in players:
        by_poste_ligue[(p["poste"], p["club"]["la"])].append(p)
        by_poste_big5[p["poste"]].append(p)
    for group in by_poste_ligue.values():
        group.sort(key=lambda x: -x["score"])
        for i, p in enumerate(group):
            p["rangLigue"] = i + 1
            p["totalPosteLigue"] = len(group)
    for group in by_poste_big5.values():
        group.sort(key=lambda x: -x["score"])
        for i, p in enumerate(group):
            p["rangBig5"] = i + 1
            p["totalPosteBig5"] = len(group)


def render_js(players: list[dict], role_features_web: dict[str, list[str]]) -> str:
    players_json = json.dumps(players, ensure_ascii=False, indent=None,
                              separators=(",", ":"))
    rf_json = json.dumps(role_features_web, ensure_ascii=False, indent=2)

    # Génère ROLES_BY_POSITION dynamiquement depuis le dictionnaire Python
    rbp_lines = []
    for poste, roles in ROLES_BY_POSITION.items():
        roles_js = json.dumps(roles, ensure_ascii=False)
        rbp_lines.append(f"  {poste}: {roles_js},")
    rbp_js = "\n".join(rbp_lines)

    return f"""/* players-data.js — GÉNÉRÉ PAR 07_export_web.py — NE PAS MODIFIER */
/* {len(players)} joueurs | {sum(len(v) for v in ROLES_BY_POSITION.values())} rôles | Features issues de ROLE_FEATURES (05_features_v2.py) */

const ROLES_BY_POSITION = {{
{rbp_js}
}};

const POSITION_LABEL = {{
  GK:"Gardien", CB:"Défenseur central", FB:"Latéral",
  DM:"Milieu défensif", CM:"Milieu central", AM:"Milieu offensif",
  W:"Ailier", CF:"Avant-centre",
}};

/* ROLE_FEATURES — tous les indicateurs pondérés par rôle (pipeline 05_features_v2.py) */
const ROLE_FEATURES = {rf_json};

const PLAYERS_DB = {players_json};
"""


def main():
    parser = argparse.ArgumentParser(description="Export pipeline → maquette_site/players-data.js")
    parser.add_argument("--min-min", type=int, default=450, help="Minutes minimum (défaut: 450)")
    args = parser.parse_args()

    print("\n" + "═" * 60)
    print("  EXPORT WEB — Football Scoring Project")
    print("═" * 60)

    if not SCORES_PATH.exists():
        print(f"  Fichier manquant : {SCORES_PATH}")
        return
    if not MASTER_PATH.exists():
        print(f"  Fichier manquant : {MASTER_PATH}")
        return

    print(f"  Chargement scores : {SCORES_PATH.name}")
    df = pd.read_csv(SCORES_PATH, encoding="utf-8-sig")
    print(f"  Joueurs bruts : {len(df)}")

    print(f"  Chargement master : {MASTER_PATH.name}")
    master = pd.read_csv(MASTER_PATH, encoding="utf-8-sig")

    df = df[df["minutesPlayed"] >= args.min_min].copy()
    print(f"  Apres filtre >=  {args.min_min} min : {len(df)} joueurs")

    # Construire ROLE_FEATURES pour le JS (basé sur ROLE_FEATURES_PY)
    # Charger les photos si disponibles (générées par 08_fetch_player_images.py)
    player_images: dict[str, str | None] = {}
    if IMAGES_PATH.exists():
        with open(IMAGES_PATH, encoding="utf-8") as f:
            player_images = json.load(f)
        found = sum(1 for v in player_images.values() if v)
        print(f"  Photos chargees   : {found}/{len(player_images)} joueurs")
    else:
        print(f"  Photos            : absent (lancer 08_fetch_player_images.py)")

    print("  Construction ROLE_FEATURES (features pipeline)...")
    role_features_web = build_role_features_web()

    print("  Construction PLAYERS_DB...")
    players = build_players_db(df, master, role_features_web, player_images)
    print(f"  Joueurs exportes : {len(players)}")

    print("  Calcul des classements...")
    compute_rankings(players)

    print(f"  Generation {OUTPUT_JS.name}...")
    js_content = render_js(players, role_features_web)
    with open(OUTPUT_JS, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(js_content)
    size_kb = OUTPUT_JS.stat().st_size / 1024
    print(f"  OK : {OUTPUT_JS.name} ({size_kb:.0f} Ko, {len(players)} joueurs)")

    print("\n  ROLE_FEATURES generes :")
    for role, feats in list(role_features_web.items())[:5]:
        print(f"    {role}: {feats}")
    print(f"  ... ({len(role_features_web)} roles au total)")


if __name__ == "__main__":
    main()
