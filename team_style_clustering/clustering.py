"""
K-Means, Hierarchical (Ward), GMM — sélection automatique du k optimal.
"""

import logging
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.cluster.hierarchy import dendrogram, linkage
from sklearn.cluster import KMeans, AgglomerativeClustering
from sklearn.mixture import GaussianMixture
from sklearn.metrics import silhouette_score

logger = logging.getLogger(__name__)


def kmeans_clustering(
    X: np.ndarray,
    k_range,
    output_dir: str,
    bloc_name: str,
) -> tuple[np.ndarray, int]:
    """
    Teste k=3..7, sélectionne le k optimal (silhouette max).
    Sauvegarde elbow + silhouette plot.
    Retourne (labels, best_k).
    """
    results: dict[int, dict] = {}
    for k in k_range:
        km = KMeans(n_clusters=k, n_init=10, random_state=42)
        labels = km.fit_predict(X)
        sil = silhouette_score(X, labels) if len(set(labels)) > 1 else -1
        results[k] = {"labels": labels, "silhouette": sil, "inertia": km.inertia_}
        logger.debug(f"  KMeans k={k} : silhouette={sil:.3f}  inertia={km.inertia_:.1f}")

    best_k = max(results, key=lambda k: results[k]["silhouette"])
    logger.info(f"KMeans [{bloc_name}] best k={best_k}  silhouette={results[best_k]['silhouette']:.3f}")

    # --- Plot elbow + silhouette ---
    ks   = sorted(results)
    sils = [results[k]["silhouette"] for k in ks]
    ines = [results[k]["inertia"]    for k in ks]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4))
    ax1.plot(ks, ines, "bo-", markersize=7)
    ax1.axvline(best_k, color="red", linestyle="--", alpha=0.7, label=f"k={best_k} retenu")
    ax1.set_xlabel("k")
    ax1.set_ylabel("Inertie")
    ax1.set_title(f"Elbow — {bloc_name}")
    ax1.legend(fontsize=9)

    colors = ["tomato" if k == best_k else "steelblue" for k in ks]
    ax2.bar(ks, sils, color=colors, edgecolor="white")
    ax2.set_xlabel("k")
    ax2.set_ylabel("Silhouette Score")
    ax2.set_title(f"Silhouette — {bloc_name}")
    ax2.set_ylim(0, max(sils) * 1.15)

    plt.tight_layout()
    out = Path(output_dir) / f"elbow_silhouette_{bloc_name}.png"
    plt.savefig(str(out), dpi=150, bbox_inches="tight")
    plt.close()
    logger.info(f"Elbow+silhouette → {out}")

    return results[best_k]["labels"], best_k


def hierarchical_clustering(
    X: np.ndarray,
    team_names: list[str],
    output_dir: str,
    bloc_name: str,
    n_clusters: int = 4,
) -> np.ndarray:
    """
    Ward linkage + dendrogramme. Coupe à n_clusters.
    Sauvegarde dendrogram_{bloc}.png.
    """
    Z = linkage(X, method="ward")

    fig, ax = plt.subplots(figsize=(max(12, len(team_names) * 0.6), 6))
    dendrogram(
        Z,
        labels=team_names,
        leaf_rotation=45,
        leaf_font_size=8,
        ax=ax,
        color_threshold=0.7 * float(Z[:, 2].max()),
    )
    ax.set_title(f"Dendrogramme (Ward) — {bloc_name}  [coupure à k={n_clusters}]", fontsize=12)
    ax.set_xlabel("Équipe")
    ax.set_ylabel("Distance")
    plt.tight_layout()
    out = Path(output_dir) / f"dendrogram_{bloc_name}.png"
    plt.savefig(str(out), dpi=150, bbox_inches="tight")
    plt.close()
    logger.info(f"Dendrogramme → {out}")

    model = AgglomerativeClustering(n_clusters=n_clusters, linkage="ward")
    return model.fit_predict(X)


def gmm_clustering(
    X: np.ndarray,
    k_range,
    output_dir: str,
    bloc_name: str,
) -> np.ndarray:
    """
    GMM : sélection du nombre de composantes par critère BIC (minimum).
    """
    bics: dict[int, float] = {}
    models: dict[int, GaussianMixture] = {}
    for k in k_range:
        gmm = GaussianMixture(n_components=k, n_init=5, random_state=42)
        gmm.fit(X)
        bics[k] = gmm.bic(X)
        models[k] = gmm
        logger.debug(f"  GMM k={k} : BIC={bics[k]:.1f}")

    best_k = min(bics, key=bics.get)
    logger.info(f"GMM [{bloc_name}] best k={best_k}  BIC={bics[best_k]:.1f}")

    return models[best_k].predict(X)
