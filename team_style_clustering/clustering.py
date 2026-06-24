"""
K-Means et Hierarchical (Ward) — toutes les valeurs de k dans k_range.
"""

import logging
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.cluster.hierarchy import dendrogram, linkage
from sklearn.cluster import KMeans, AgglomerativeClustering
from sklearn.metrics import silhouette_score

logger = logging.getLogger(__name__)


def kmeans_all_k(
    X: np.ndarray,
    k_range,
    output_dir: str,
    bloc_name: str,
) -> tuple[dict[int, np.ndarray], dict[int, float]]:
    """
    Teste chaque k dans k_range, sauvegarde elbow+silhouette.
    Retourne ({k: labels}, {k: silhouette}).
    """
    results: dict[int, dict] = {}
    for k in k_range:
        km = KMeans(n_clusters=k, n_init=10, random_state=42)
        lbl = km.fit_predict(X)
        sil = silhouette_score(X, lbl) if len(set(lbl)) > 1 else -1.0
        results[k] = {"labels": lbl, "silhouette": sil, "inertia": km.inertia_}
        logger.debug(f"  KMeans k={k} : sil={sil:.3f}  inertia={km.inertia_:.1f}")

    best_k = max(results, key=lambda k: results[k]["silhouette"])
    logger.info(
        f"KMeans [{bloc_name}] k optimal={best_k} "
        f"(sil={results[best_k]['silhouette']:.3f})"
    )

    ks   = sorted(results)
    sils = [results[k]["silhouette"] for k in ks]
    ines = [results[k]["inertia"]    for k in ks]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4))
    ax1.plot(ks, ines, "bo-", markersize=7)
    ax1.axvline(best_k, color="red", linestyle="--", alpha=0.7, label=f"k={best_k} optimal")
    ax1.set_xlabel("k"); ax1.set_ylabel("Inertie")
    ax1.set_title(f"Elbow — {bloc_name}"); ax1.legend(fontsize=9)

    colors = ["tomato" if k == best_k else "steelblue" for k in ks]
    ax2.bar(ks, sils, color=colors, edgecolor="white")
    ax2.set_xlabel("k"); ax2.set_ylabel("Silhouette")
    ax2.set_title(f"Silhouette — {bloc_name}")
    if max(sils) > 0:
        ax2.set_ylim(0, max(sils) * 1.15)

    plt.tight_layout()
    out = Path(output_dir) / f"elbow_silhouette_{bloc_name}.png"
    plt.savefig(str(out), dpi=150, bbox_inches="tight")
    plt.close()
    logger.info(f"Elbow+silhouette → {out}")

    return (
        {k: results[k]["labels"] for k in ks},
        {k: round(results[k]["silhouette"], 4) for k in ks},
    )


def hierarchical_all_k(
    X: np.ndarray,
    team_names: list[str],
    output_dir: str,
    bloc_name: str,
    k_range,
) -> tuple[dict[int, np.ndarray], dict[int, float]]:
    """
    Ward linkage, coupe à chaque k dans k_range.
    Sauvegarde dendrogramme, retourne ({k: labels}, {k: silhouette}).
    """
    Z = linkage(X, method="ward")

    fig, ax = plt.subplots(figsize=(max(12, len(team_names) * 0.5), 6))
    dendrogram(
        Z, labels=team_names,
        leaf_rotation=45, leaf_font_size=7, ax=ax,
        color_threshold=0.7 * float(Z[:, 2].max()),
    )
    ax.set_title(f"Dendrogramme (Ward) — {bloc_name}", fontsize=12)
    ax.set_xlabel("Équipe"); ax.set_ylabel("Distance")
    plt.tight_layout()
    out = Path(output_dir) / f"dendrogram_{bloc_name}.png"
    plt.savefig(str(out), dpi=150, bbox_inches="tight")
    plt.close()
    logger.info(f"Dendrogramme → {out}")

    labels_by_k: dict[int, np.ndarray] = {}
    sil_by_k: dict[int, float] = {}
    for k in k_range:
        lbl = AgglomerativeClustering(n_clusters=k, linkage="ward").fit_predict(X)
        sil = silhouette_score(X, lbl) if len(set(lbl)) > 1 else -1.0
        labels_by_k[k] = lbl
        sil_by_k[k] = round(sil, 4)
        logger.debug(f"  Hierarchical k={k} : sil={sil:.3f}")

    best_k = max(sil_by_k, key=sil_by_k.get)
    logger.info(
        f"Hierarchical [{bloc_name}] k optimal={best_k} "
        f"(sil={sil_by_k[best_k]:.3f})"
    )
    return labels_by_k, sil_by_k
