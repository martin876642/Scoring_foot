"""
Construction des blocs de features, scaling, matrice de corrélation.
"""

import logging
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """Ajoute les colonnes dérivées (xG_per_shot proxy)."""
    df = df.copy()
    # shots non dispo depuis Understat équipe → NPxG comme proxy qualité occasions
    df["xG_per_shot"] = df["NPxG"]
    logger.info("xG_per_shot = NPxG (proxy — shots indisponibles depuis Understat équipe)")
    return df


def get_feature_blocks(df: pd.DataFrame) -> dict[str, list[str]]:
    """Retourne les blocs de features, adapte si possession_pct absent."""
    has_poss = "possession_pct" in df.columns and df["possession_pct"].notna().any()

    offensive = ["xG", "xG_per_shot", "DC", "OPPDA"]
    if has_poss:
        offensive.insert(3, "possession_pct")
    else:
        logger.warning("possession_pct indisponible — bloc offensif : 4 features (sans possession)")

    defensive = ["xGA", "PPDA", "ODC"]

    return {
        "offensive": offensive,
        "defensive": defensive,
        "all":       offensive + defensive,
    }


def prepare_data(
    df: pd.DataFrame,
    features: list[str],
) -> tuple[pd.DataFrame, np.ndarray, StandardScaler]:
    """Retire les lignes avec NaN sur les features, standardise, retourne (df_valid, X_scaled, scaler)."""
    valid = df.dropna(subset=features).copy().reset_index(drop=True)
    n_dropped = len(df) - len(valid)
    if n_dropped:
        dropped_teams = df[df[features].isna().any(axis=1)]["Team"].tolist()
        logger.warning(f"{n_dropped} équipe(s) exclues (données manquantes) : {dropped_teams}")

    scaler = StandardScaler()
    X = scaler.fit_transform(valid[features].values.astype(float))
    return valid, X, scaler


def plot_correlation_matrix(
    df: pd.DataFrame,
    features: list[str],
    output_path: str,
) -> None:
    corr = df[features].corr()
    fig, ax = plt.subplots(figsize=(max(8, len(features)), max(6, len(features) - 1)))
    sns.heatmap(
        corr, annot=True, fmt=".2f", cmap="coolwarm",
        center=0, vmin=-1, vmax=1, ax=ax,
        square=True, linewidths=0.5, annot_kws={"size": 9},
    )
    ax.set_title("Feature Correlation Matrix", fontsize=13, pad=10)
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()
    logger.info(f"Matrice de corrélation → {output_path}")
