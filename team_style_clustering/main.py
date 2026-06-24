"""
Orchestrateur — lance le pipeline complet team_style_clustering.

Usage (depuis la racine du projet) :
    python team_style_clustering/main.py
    python -m team_style_clustering.main
"""

import sys
import logging
from pathlib import Path

# UTF-8 explicite sur Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Assure que le dossier du module est dans sys.path (fonctionne script direct ET -m)
_TSC_DIR = Path(__file__).resolve().parent
if str(_TSC_DIR) not in sys.path:
    sys.path.insert(0, str(_TSC_DIR))

import config
from scraper import fetch_all
from features import (
    build_features, get_feature_blocks, prepare_data, plot_correlation_matrix,
)
from clustering import (
    kmeans_clustering, hierarchical_clustering, gmm_clustering,
)
from visualization import (
    reduce_2d, plot_cluster_2d, plot_radar,
    _cluster_mean,
)


def _setup_logging(output_dir: str) -> None:
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(
                str(Path(output_dir) / "run.log"), encoding="utf-8", mode="w"
            ),
        ],
    )


def main() -> None:
    out = config.OUTPUT_DIR
    _setup_logging(out)
    logger = logging.getLogger("main")

    logger.info("=" * 60)
    logger.info(f"Team Style Clustering — {config.LEAGUE}  saison {config.SEASON}")
    logger.info(f"Outputs → {Path(out).resolve()}")
    logger.info("=" * 60)

    # ── 1. Données ──────────────────────────────────────────────────────────
    override = str(_TSC_DIR / "possession_override.csv")
    df = fetch_all(config.LEAGUE, config.SEASON, override)
    logger.info(f"Dataset : {len(df)} équipes | colonnes : {list(df.columns)}")

    # ── 2. Features ─────────────────────────────────────────────────────────
    df     = build_features(df)
    blocks = get_feature_blocks(df)
    logger.info(f"Blocs : { {k: len(v) for k, v in blocks.items()} }")

    # Matrice de corrélation (union de toutes les features)
    all_feats = list(dict.fromkeys(f for flist in blocks.values() for f in flist))
    df_corr, _, _ = prepare_data(df, all_feats)
    if len(df_corr) > 1:
        plot_correlation_matrix(
            df_corr, all_feats,
            output_path=str(Path(out) / "correlation_matrix.png"),
        )

    # ── 3-7. Clustering × blocs ─────────────────────────────────────────────
    for bloc_name, features in blocks.items():
        logger.info(f"\n{'─' * 50}")
        logger.info(f"BLOC : {bloc_name.upper()}  {features}")

        df_valid, X, _ = prepare_data(df, features)
        n = len(df_valid)

        if n < 4:
            logger.error(f"Pas assez d'équipes ({n}) pour '{bloc_name}' — skip")
            continue

        # K-range adapté si moins d'équipes que prévu
        k_range = range(min(_cfg_k_min(config.KMEANS_RANGE), n - 1),
                        min(max(config.KMEANS_RANGE) + 1, n))
        if len(k_range) < 2:
            logger.warning(f"Plage k trop petite pour {bloc_name} ({n} équipes) — skip")
            continue

        team_names = df_valid["Team"].tolist()
        coords, reduction_name = reduce_2d(X)

        # K-Means ─────────────────────────────────────────────────────────
        km_labels, best_k = kmeans_clustering(X, k_range, out, bloc_name)
        plot_cluster_2d(
            df_valid, X, km_labels, coords, reduction_name,
            features, bloc_name, "kmeans", out,
        )

        # Hierarchical ────────────────────────────────────────────────────
        hc_labels = hierarchical_clustering(
            X, team_names, out, bloc_name, n_clusters=best_k
        )
        plot_cluster_2d(
            df_valid, X, hc_labels, coords, reduction_name,
            features, bloc_name, "hierarchical", out,
        )

        # GMM ─────────────────────────────────────────────────────────────
        gmm_range = range(min(_cfg_k_min(config.GMM_RANGE), n - 1),
                          min(max(config.GMM_RANGE) + 1, n))
        gmm_labels = gmm_clustering(X, gmm_range, out, bloc_name)
        plot_cluster_2d(
            df_valid, X, gmm_labels, coords, reduction_name,
            features, bloc_name, "gmm", out,
        )

        # Radars standalone (labels K-Means) ──────────────────────────────
        logger.info(f"Radars standalone : {len(team_names)} équipes × bloc {bloc_name}")
        for i, team in enumerate(team_names):
            cl = int(km_labels[i])
            plot_radar(
                team_name=team,
                radar_values=X[i].tolist(),
                cluster_mean=_cluster_mean(cl, km_labels, X),
                feature_names=features,
                cluster_id=cl,
                bloc_name=bloc_name,
                output_dir=out,
            )

    logger.info("\n" + "=" * 60)
    logger.info(f"Terminé — outputs : {Path(out).resolve()}")
    logger.info("=" * 60)


def _cfg_k_min(k_range) -> int:
    return min(k_range)


if __name__ == "__main__":
    main()
