"""
Orchestrateur — lance le pipeline complet team_style_clustering.

Usage (depuis la racine du projet) :
    python team_style_clustering/main.py
    python -m team_style_clustering.main
"""

import sys
import logging
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

_TSC_DIR = Path(__file__).resolve().parent
if str(_TSC_DIR) not in sys.path:
    sys.path.insert(0, str(_TSC_DIR))

import config
from scraper import fetch_all
from features import (
    build_features, get_feature_blocks, prepare_data, plot_correlation_matrix,
)
from clustering import kmeans_all_k, hierarchical_all_k
from visualization import reduce_2d, plot_cluster_2d


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
    logger.info(f"Team Style Clustering — {config.LEAGUES}  saison {config.SEASON}")
    logger.info(f"Outputs → {Path(out).resolve()}")
    logger.info("=" * 60)

    # ── 1. Données ──────────────────────────────────────────────────────────
    override = str(_TSC_DIR / "possession_override.csv")
    df = fetch_all(config.LEAGUES, config.SEASON, override)
    logger.info(f"Dataset : {len(df)} équipes | colonnes : {list(df.columns)}")

    # ── 2. Features ─────────────────────────────────────────────────────────
    df     = build_features(df)
    blocks = get_feature_blocks(df)
    logger.info(f"Blocs : { {k: len(v) for k, v in blocks.items()} }")

    all_feats = list(dict.fromkeys(f for flist in blocks.values() for f in flist))
    df_corr, _, _ = prepare_data(df, all_feats)
    if len(df_corr) > 1:
        plot_correlation_matrix(
            df_corr, all_feats,
            output_path=str(Path(out) / "correlation_matrix.png"),
        )

    # ── 3-5. Clustering × blocs ─────────────────────────────────────────────
    for bloc_name, features in blocks.items():
        logger.info(f"\n{'─' * 50}")
        logger.info(f"BLOC : {bloc_name.upper()}  {features}")

        df_valid, X, _ = prepare_data(df, features)
        n = len(df_valid)

        if n < 4:
            logger.error(f"Pas assez d'équipes ({n}) pour '{bloc_name}' — skip")
            continue

        k_min = min(config.KMEANS_RANGE)
        k_max = min(max(config.KMEANS_RANGE), n - 1)
        if k_max < k_min + 1:
            logger.warning(f"Plage k insuffisante pour {bloc_name} ({n} équipes) — skip")
            continue
        k_range = range(k_min, k_max + 1)

        team_names = df_valid["Team"].tolist()
        coords, reduction_name = reduce_2d(X)

        # K-Means (toutes les valeurs de k)
        km_labels_k, km_sil = kmeans_all_k(X, k_range, out, bloc_name)
        plot_cluster_2d(
            df_valid, X, km_labels_k, km_sil,
            coords, reduction_name, features, bloc_name, "kmeans", out,
        )

        # Hierarchical (toutes les valeurs de k)
        hc_labels_k, hc_sil = hierarchical_all_k(X, team_names, out, bloc_name, k_range)
        plot_cluster_2d(
            df_valid, X, hc_labels_k, hc_sil,
            coords, reduction_name, features, bloc_name, "hierarchical", out,
        )

    logger.info("\n" + "=" * 60)
    logger.info(f"Terminé — outputs : {Path(out).resolve()}")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
