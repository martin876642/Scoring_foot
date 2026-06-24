"""
Visualisation 2D interactive (Plotly HTML).
- UMAP (fallback PCA) pour la réduction dimensionnelle
- Scatter interactif avec panneau radar au clic (JS embarqué)
- Génération de fichiers radar_{team}_{bloc}.html standalone
"""

import json
import logging
import math
import webbrowser
from pathlib import Path

import numpy as np
import plotly.graph_objects as go
import plotly.colors as pc
from sklearn.decomposition import PCA
from sklearn.metrics.pairwise import euclidean_distances

logger = logging.getLogger(__name__)

_PALETTE = pc.qualitative.Set1 + pc.qualitative.Set2 + pc.qualitative.Pastel1


# ─── Réduction dimensionnelle ─────────────────────────────────────────────────

def reduce_2d(X: np.ndarray) -> tuple[np.ndarray, str]:
    """UMAP ou PCA (fallback). Retourne (coords_2d, label_méthode)."""
    n = len(X)
    try:
        import umap  # noqa: F401
        n_neighbors = min(15, n - 1)
        reducer = umap.UMAP(n_components=2, n_neighbors=n_neighbors, random_state=42)
        coords = reducer.fit_transform(X)
        logger.info(f"Réduction : UMAP (n_neighbors={n_neighbors})")
        return coords, "UMAP"
    except ImportError:
        logger.warning("umap-learn non installé — fallback PCA")

    pca = PCA(n_components=2, random_state=42)
    coords = pca.fit_transform(X)
    var = pca.explained_variance_ratio_
    label = f"PCA (PC1={var[0]:.0%} PC2={var[1]:.0%})"
    logger.info(f"Réduction : {label}")
    return coords, label


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _top3_similar(idx: int, X: np.ndarray, names: list[str]) -> list[str]:
    dists = euclidean_distances(X[idx : idx + 1], X)[0]
    order = np.argsort(dists)
    return [names[i] for i in order if i != idx][:3]


def _cluster_mean(label: int, labels: np.ndarray, X: np.ndarray) -> list[float]:
    mask = labels == label
    if not mask.any():
        return [0.0] * X.shape[1]
    return X[mask].mean(axis=0).tolist()


def _safe_json(obj) -> str:
    """json.dumps qui remplace NaN/Inf par 0."""
    def _fix(o):
        if isinstance(o, float) and (math.isnan(o) or math.isinf(o)):
            return 0.0
        return o

    class _Enc(json.JSONEncoder):
        def iterencode(self, o, _one_shot=False):
            if isinstance(o, float):
                o = _fix(o)
            return super().iterencode(o, _one_shot)

    return json.dumps(obj, cls=_Enc, ensure_ascii=False)


# ─── Scatter 2D interactif ────────────────────────────────────────────────────

_RADAR_PANEL_CSS = """
#radar-panel {
  position: fixed; right: 15px; top: 70px; width: 430px;
  background: #fff; border: 1px solid #d0d0d0; border-radius: 10px;
  padding: 16px; box-shadow: 3px 3px 14px rgba(0,0,0,.18);
  display: none; z-index: 9999; font-family: Arial, sans-serif;
}
#radar-panel header {
  display: flex; justify-content: space-between; align-items: center;
  margin-bottom: 8px;
}
#radar-panel header span { font-weight: bold; font-size: 14px; }
#radar-panel button {
  border: none; background: transparent; font-size: 18px;
  cursor: pointer; color: #888; line-height: 1;
}
#radar-chart { height: 280px; }
#similar-teams {
  margin-top: 8px; padding-top: 8px; border-top: 1px solid #eee;
  font-size: 12px; color: #444;
}
"""

_RADAR_PANEL_HTML = """
<style>{css}</style>
<div id="radar-panel">
  <header>
    <span id="radar-title"></span>
    <button onclick="document.getElementById('radar-panel').style.display='none'">&#x2715;</button>
  </header>
  <div id="radar-chart"></div>
  <div id="similar-teams"></div>
</div>
"""

_CLICK_JS = """
<script>
(function () {{
  var FEATURES   = {features_js};
  var TEAM_DATA  = {team_data_js};
  var PALETTE    = {palette_js};

  function hexToRgba(hex, a) {{
    var r = parseInt(hex.slice(1,3),16),
        g = parseInt(hex.slice(3,5),16),
        b = parseInt(hex.slice(5,7),16);
    return 'rgba('+r+','+g+','+b+','+a+')';
  }}

  function waitForPlot(cb, tries) {{
    var el = document.querySelector('.plotly-graph-div');
    if (el && el.on) {{ cb(el); }}
    else if ((tries||0) < 30) {{ setTimeout(function(){{waitForPlot(cb, (tries||0)+1);}}, 200); }}
  }}

  waitForPlot(function(plot) {{
    plot.on('plotly_click', function(data) {{
      if (!data.points || !data.points.length) return;
      var pt  = data.points[0];
      var td  = TEAM_DATA[pt.text];
      if (!td) return;

      document.getElementById('radar-panel').style.display = 'block';
      document.getElementById('radar-title').textContent =
        pt.text + '  —  Cluster ' + td.cluster;

      var theta  = FEATURES.concat([FEATURES[0]]);
      var rTeam  = td.radar.concat([td.radar[0]]);
      var rMean  = td.cluster_mean.concat([td.cluster_mean[0]]);
      var col    = PALETTE[td.cluster % PALETTE.length];

      Plotly.newPlot('radar-chart', [
        {{type:'scatterpolar', r:rTeam, theta:theta, fill:'toself',
          name:pt.text,
          line:{{color:col}},
          fillcolor:hexToRgba(col, 0.25)}},
        {{type:'scatterpolar', r:rMean, theta:theta, fill:'toself',
          name:'Moy. cluster '+td.cluster,
          line:{{color:'#aaa', dash:'dash'}},
          fillcolor:'rgba(160,160,160,0.10)'}}
      ], {{
        polar:{{radialaxis:{{visible:true, range:[-3,3]}}}},
        showlegend:true,
        legend:{{x:0,y:-0.22,orientation:'h',font:{{size:10}}}},
        margin:{{t:10,b:45,l:20,r:20}},
        height:280
      }}, {{displayModeBar:false}});

      document.getElementById('similar-teams').innerHTML =
        '<b>Top 3 les plus similaires :</b> ' + td.top3.join(' · ');
    }});
  }});
}})();
</script>
"""


def plot_cluster_2d(
    df_valid: "pd.DataFrame",
    X_scaled: np.ndarray,
    labels: np.ndarray,
    coords: np.ndarray,
    reduction_name: str,
    feature_names: list[str],
    bloc_name: str,
    method_name: str,
    output_dir: str,
) -> None:
    team_names = df_valid["Team"].tolist()

    # Pré-calcul pour le panneau radar JS
    team_data: dict[str, dict] = {}
    for i, team in enumerate(team_names):
        cl = int(labels[i])
        team_data[team] = {
            "cluster":      cl,
            "radar":        [round(float(v), 4) for v in X_scaled[i]],
            "cluster_mean": [round(float(v), 4) for v in _cluster_mean(cl, labels, X_scaled)],
            "top3":         _top3_similar(i, X_scaled, team_names),
        }

    # Figure Plotly
    fig = go.Figure()
    for cl in sorted(set(labels)):
        mask = labels == cl
        cl_teams  = [team_names[i] for i in range(len(team_names)) if mask[i]]
        cl_coords = coords[mask]
        col = _PALETTE[cl % len(_PALETTE)]

        fig.add_trace(go.Scatter(
            x=cl_coords[:, 0],
            y=cl_coords[:, 1],
            mode="markers+text",
            name=f"Cluster {cl}",
            text=cl_teams,
            textposition="top center",
            textfont=dict(size=9),
            marker=dict(size=13, color=col, line=dict(width=1, color="black")),
            hovertemplate="<b>%{text}</b><br>Cluster " + str(cl) + "<br><i>cliquez pour le radar</i><extra></extra>",
        ))

    fig.update_layout(
        title=f"Clustering 2D — {bloc_name.capitalize()} — {method_name.upper()} ({reduction_name})",
        xaxis_title=f"{reduction_name} Dim 1",
        yaxis_title=f"{reduction_name} Dim 2",
        legend_title="Clusters",
        height=620,
        template="plotly_white",
    )

    # Injection du panneau radar + handler JS
    html = fig.to_html(full_html=True, include_plotlyjs="cdn")
    panel = (
        _RADAR_PANEL_HTML.format(css=_RADAR_PANEL_CSS)
        + _CLICK_JS.format(
            features_js=_safe_json(feature_names),
            team_data_js=_safe_json(team_data),
            palette_js=_safe_json([c for c in _PALETTE[:10]]),
        )
    )
    html = html.replace("</body>", panel + "\n</body>")

    out = Path(output_dir) / f"cluster_2d_{bloc_name}_{method_name}.html"
    out.write_text(html, encoding="utf-8")
    logger.info(f"Scatter 2D → {out}")
    webbrowser.open(out.resolve().as_uri())


# ─── Radar standalone ────────────────────────────────────────────────────────

def plot_radar(
    team_name: str,
    radar_values: list[float],
    cluster_mean: list[float],
    feature_names: list[str],
    cluster_id: int,
    bloc_name: str,
    output_dir: str,
) -> None:
    theta = feature_names + [feature_names[0]]
    r_team = list(radar_values) + [radar_values[0]]
    r_mean = list(cluster_mean) + [cluster_mean[0]]

    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(
        r=r_team, theta=theta, fill="toself", name=team_name,
        line=dict(color="royalblue"), fillcolor="rgba(65,105,225,0.25)",
    ))
    fig.add_trace(go.Scatterpolar(
        r=r_mean, theta=theta, fill="toself", name=f"Cluster {cluster_id} (moy.)",
        line=dict(color="#999", dash="dash"), fillcolor="rgba(150,150,150,0.10)",
    ))
    fig.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[-3, 3])),
        title=f"Style Fingerprint — {team_name}  ({bloc_name})",
        showlegend=True,
        template="plotly_white",
        height=450,
    )

    safe = team_name.replace(" ", "_").replace("/", "_").replace("'", "")
    out = Path(output_dir) / f"radar_{safe}_{bloc_name}.html"
    fig.write_html(str(out), include_plotlyjs="cdn")
    logger.info(f"Radar → {out}")
