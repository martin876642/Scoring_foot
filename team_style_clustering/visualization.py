"""
Visualisation 2D interactive (Plotly HTML).
- UMAP (fallback PCA) pour la réduction dimensionnelle
- Scatter interactif avec sélecteur k + filtre ligue + radar au clic
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

_LEAGUE_SYMBOLS = {
    "EPL":        "circle",
    "La_liga":    "square",
    "Bundesliga": "diamond",
    "Serie_A":    "cross",
    "Ligue_1":    "triangle-up",
}
_LEAGUE_LABELS = {
    "EPL":        "EPL ●",
    "La_liga":    "La Liga ■",
    "Bundesliga": "Bundesliga ◆",
    "Serie_A":    "Serie A +",
    "Ligue_1":    "Ligue 1 ▲",
}

# ─── CSS ──────────────────────────────────────────────────────────────────────

_CONTROLS_CSS = """
#controls-bar {
  position: fixed; top: 8px; left: 50%; transform: translateX(-50%);
  z-index: 9999; background: #fff; border: 1px solid #ccc; border-radius: 8px;
  padding: 6px 14px; box-shadow: 2px 2px 10px rgba(0,0,0,.15);
  display: flex; align-items: center; gap: 8px;
  font-family: Arial, sans-serif; font-size: 13px; white-space: nowrap;
}
.ctrl-sep { width: 1px; height: 22px; background: #ddd; margin: 0 6px; }
.ctrl-label { font-weight: bold; color: #555; }
.k-btn, .lg-btn {
  border: 1px solid #bbb; border-radius: 5px; padding: 3px 9px;
  cursor: pointer; font-size: 12px; background: #eee; color: #333;
  transition: background 0.15s;
}
.k-btn.active  { background: #3a7bd5; color: #fff; border-color: #2a6bc5; font-weight: bold; }
.lg-btn.active { background: #2e8b57; color: #fff; border-color: #1e7b47; font-weight: bold; }
"""

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

# ─── JS statique (placeholders remplacés à la génération) ─────────────────────
# Les {} littéraux JS ne posent pas de problème : ce template
# est manipulé via .replace() et non via .format() ou f-string.

_MAIN_JS = """
<script>
(function() {
  var TRACE_MAP     = __TRACE_MAP__;
  var ALL_TEAM_DATA = __ALL_TEAM_DATA__;
  var FEATURES      = __FEATURES__;
  var PALETTE       = __PALETTE__;
  var BEST_K        = __BEST_K__;

  var currentK      = BEST_K;
  var currentLeague = 'all';
  var gd            = null;

  function hexToRgba(hex, a) {
    var r = parseInt(hex.slice(1,3),16),
        g = parseInt(hex.slice(3,5),16),
        b = parseInt(hex.slice(5,7),16);
    return 'rgba('+r+','+g+','+b+','+a+')';
  }

  function updateVisibility() {
    if (!gd) return;
    var vis = TRACE_MAP.map(function(t) {
      return t.k === currentK && (currentLeague === 'all' || t.league === currentLeague);
    });
    Plotly.restyle(gd, {visible: vis});
  }

  window.selectK = function(k) {
    currentK = k;
    document.querySelectorAll('.k-btn').forEach(function(b) {
      b.classList.toggle('active', +b.dataset.k === k);
    });
    var panel = document.getElementById('radar-panel');
    if (panel) panel.style.display = 'none';
    updateVisibility();
  };

  window.selectLeague = function(lg) {
    currentLeague = lg;
    document.querySelectorAll('.lg-btn').forEach(function(b) {
      b.classList.toggle('active', b.dataset.league === lg);
    });
    var panel = document.getElementById('radar-panel');
    if (panel) panel.style.display = 'none';
    updateVisibility();
  };

  function waitForPlot(cb, tries) {
    var el = document.querySelector('.js-plotly-plot') ||
             document.querySelector('.plotly-graph-div');
    if (el && typeof el.on === 'function') { cb(el); return; }
    if ((tries||0) < 40) setTimeout(function(){waitForPlot(cb,(tries||0)+1);}, 150);
  }

  waitForPlot(function(el) {
    gd = el;
    updateVisibility();

    el.on('plotly_click', function(data) {
      if (!data.points || !data.points.length) return;
      var pt      = data.points[0];
      var teamMap = ALL_TEAM_DATA[String(currentK)];
      var td      = teamMap ? teamMap[pt.text] : null;
      if (!td) return;

      document.getElementById('radar-panel').style.display = 'block';
      var lgLabel = td.league ? ' (' + td.league.replace(/_/g, ' ') + ')' : '';
      document.getElementById('radar-title').textContent =
        pt.text + lgLabel + '  —  Cluster ' + td.cluster;

      var theta = FEATURES.concat([FEATURES[0]]);
      var rTeam = td.radar.concat([td.radar[0]]);
      var rMean = td.cluster_mean.concat([td.cluster_mean[0]]);
      var col   = PALETTE[td.cluster % PALETTE.length];

      Plotly.newPlot('radar-chart', [
        {type:'scatterpolar', r:rTeam, theta:theta, fill:'toself',
         name:pt.text, line:{color:col}, fillcolor:hexToRgba(col,0.25)},
        {type:'scatterpolar', r:rMean, theta:theta, fill:'toself',
         name:'Moy. cluster '+td.cluster,
         line:{color:'#aaa', dash:'dash'}, fillcolor:'rgba(160,160,160,0.10)'}
      ], {
        polar:{radialaxis:{visible:true, range:[-3,3]}},
        showlegend:true,
        legend:{x:0, y:-0.22, orientation:'h', font:{size:10}},
        margin:{t:10, b:45, l:20, r:20},
        height:280
      }, {displayModeBar:false});

      document.getElementById('similar-teams').innerHTML =
        '<b>Top 3 les plus similaires :</b> ' + td.top3.join(' · ');
    });
  });
})();
</script>
"""


# ─── Helpers ──────────────────────────────────────────────────────────────────

def reduce_2d(X: np.ndarray) -> tuple[np.ndarray, str]:
    n = len(X)
    try:
        import umap
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


def _top3_similar(idx: int, X: np.ndarray, names: list[str]) -> list[str]:
    dists = euclidean_distances(X[idx:idx+1], X)[0]
    order = np.argsort(dists)
    return [names[i] for i in order if i != idx][:3]


def _cluster_mean(label: int, labels: np.ndarray, X: np.ndarray) -> list[float]:
    mask = labels == label
    if not mask.any():
        return [0.0] * X.shape[1]
    return X[mask].mean(axis=0).tolist()


def _safe_json(obj) -> str:
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


# ─── Scatter 2D interactif (multi-k + multi-ligue) ───────────────────────────

def plot_cluster_2d(
    df_valid: "pd.DataFrame",
    X_scaled: np.ndarray,
    labels_by_k: dict[int, np.ndarray],
    sil_scores: dict[int, float],
    coords: np.ndarray,
    reduction_name: str,
    feature_names: list[str],
    bloc_name: str,
    method_name: str,
    output_dir: str,
) -> None:
    team_names = df_valid["Team"].tolist()
    has_league = "League" in df_valid.columns
    leagues_in = sorted(df_valid["League"].unique()) if has_league else []
    k_list     = sorted(labels_by_k)
    best_k     = max(sil_scores, key=sil_scores.get) if sil_scores else k_list[0]

    # ── 1. ALL_TEAM_DATA = {str(k): {team: {cluster, radar, ...}}} ──────────
    all_team_data: dict[str, dict] = {}
    for k, labels in labels_by_k.items():
        td_k = {}
        for i, team in enumerate(team_names):
            cl = int(labels[i])
            td_k[team] = {
                "cluster":      cl,
                "radar":        [round(float(v), 4) for v in X_scaled[i]],
                "cluster_mean": [round(float(v), 4)
                                 for v in _cluster_mean(cl, labels, X_scaled)],
                "top3":         _top3_similar(i, X_scaled, team_names),
                "league":       str(df_valid.iloc[i]["League"]) if has_league else "",
            }
        all_team_data[str(k)] = td_k

    # ── 2. Traces — une par (k × cluster × ligue) ───────────────────────────
    fig = go.Figure()
    trace_map: list[dict] = []   # métadonnées parallèles à fig.data

    for k, labels in sorted(labels_by_k.items()):
        is_best_k = (k == best_k)
        clusters_k = sorted(set(int(l) for l in labels))

        for cl in clusters_k:
            col = _PALETTE[cl % len(_PALETTE)]
            first_in_cluster = True

            for league in (leagues_in if has_league else [None]):
                if has_league:
                    mask = (labels == cl) & (df_valid["League"] == league).values
                else:
                    mask = labels == cl

                if not mask.any():
                    continue

                cl_teams  = [team_names[i] for i in range(len(team_names)) if mask[i]]
                cl_coords = coords[mask]
                symbol    = _LEAGUE_SYMBOLS.get(league, "star") if has_league else "circle"
                lg_str    = _LEAGUE_LABELS.get(league, league) if has_league else ""

                hover = (
                    "<b>%{text}</b>"
                    + (f"<br>{lg_str}" if lg_str else "")
                    + f"<br>Cluster {cl} · k={k}"
                    + "<br><i>cliquez pour le radar</i><extra></extra>"
                )

                fig.add_trace(go.Scatter(
                    x=cl_coords[:, 0],
                    y=cl_coords[:, 1],
                    mode="markers+text",
                    name=f"Cluster {cl}",
                    legendgroup=f"cluster_{cl}",
                    showlegend=(is_best_k and first_in_cluster),
                    text=cl_teams,
                    textposition="top center",
                    textfont=dict(size=8),
                    marker=dict(
                        size=12, color=col, symbol=symbol,
                        line=dict(width=1, color="black"),
                    ),
                    hovertemplate=hover,
                    visible=is_best_k,
                ))
                trace_map.append({
                    "k":       k,
                    "cluster": cl,
                    "league":  league or "all",
                })
                first_in_cluster = False

    # ── 3. Layout ────────────────────────────────────────────────────────────
    n_teams  = len(team_names)
    n_lig    = len(leagues_in) if has_league else 1
    fig.update_layout(
        title=(
            f"Clustering 2D — {bloc_name.capitalize()} — {method_name.upper()} "
            f"({reduction_name})"
            f"<br><sup>{n_teams} équipes · {n_lig} ligue{'s' if n_lig > 1 else ''}"
            f" · k affiché = {best_k} (meilleur silhouette)</sup>"
        ),
        xaxis_title=f"{reduction_name} Dim 1",
        yaxis_title=f"{reduction_name} Dim 2",
        legend_title="Clusters",
        height=720,
        template="plotly_white",
        margin=dict(t=100, b=80),
    )

    # ── 4. Barre de contrôles ─────────────────────────────────────────────────
    k_buttons_html = ""
    for k in k_list:
        sil  = sil_scores.get(k, 0.0)
        cls  = " active" if k == best_k else ""
        k_buttons_html += (
            f'<button class="k-btn{cls}" data-k="{k}" onclick="selectK({k})">'
            f'k={k} <small style="opacity:.7">sil={sil:.2f}</small></button> '
        )

    league_section = ""
    symbol_note    = ""
    if has_league and len(leagues_in) > 1:
        lg_btns = (
            '<button class="lg-btn active" data-league="all" '
            'onclick="selectLeague(\'all\')">Toutes</button> '
        )
        for lg in leagues_in:
            label = _LEAGUE_LABELS.get(lg, lg)
            lg_btns += (
                f'<button class="lg-btn" data-league="{lg}" '
                f"onclick=\"selectLeague('{lg}')\">{label}</button> "
            )
        league_section = (
            '<span class="ctrl-sep"></span>'
            f'<span class="ctrl-label">Ligue :</span> {lg_btns}'
        )
        symbol_note = (
            "Symboles : ● EPL  ■ La Liga  ◆ Bundesliga  + Serie A  ▲ Ligue 1"
        )

    controls_html = (
        f'<style>{_CONTROLS_CSS}</style>'
        f'<div id="controls-bar">'
        f'<span class="ctrl-label">k&nbsp;:</span> {k_buttons_html}'
        f'{league_section}'
        f'</div>'
    )
    if symbol_note:
        controls_html += (
            f'<div style="position:fixed;bottom:6px;left:50%;transform:translateX(-50%);'
            f'z-index:9998;font-size:10px;color:#888;font-family:Arial">'
            f'{symbol_note}</div>'
        )

    # ── 5. Panneau radar ──────────────────────────────────────────────────────
    radar_panel_html = (
        f'<style>{_RADAR_PANEL_CSS}</style>'
        '<div id="radar-panel">'
        '  <header>'
        '    <span id="radar-title"></span>'
        '    <button onclick="document.getElementById(\'radar-panel\').style.display=\'none\'">'
        '      &#x2715;</button>'
        '  </header>'
        '  <div id="radar-chart"></div>'
        '  <div id="similar-teams"></div>'
        '</div>'
    )

    # ── 6. JS ─────────────────────────────────────────────────────────────────
    js_block = (
        _MAIN_JS
        .replace("__TRACE_MAP__",     _safe_json(trace_map))
        .replace("__ALL_TEAM_DATA__", _safe_json(all_team_data))
        .replace("__FEATURES__",      _safe_json(feature_names))
        .replace("__PALETTE__",       _safe_json(list(_PALETTE[:12])))
        .replace("__BEST_K__",        str(best_k))
    )

    # ── 7. Assemblage ─────────────────────────────────────────────────────────
    html = fig.to_html(full_html=True, include_plotlyjs="cdn")
    injection = "\n".join([controls_html, radar_panel_html, js_block])
    html = html.replace("</body>", injection + "\n</body>")

    out = Path(output_dir) / f"cluster_2d_{bloc_name}_{method_name}.html"
    out.write_text(html, encoding="utf-8")
    logger.info(
        f"Scatter 2D [{method_name}·{bloc_name}] → {out} "
        f"(k={k_list}, best={best_k})"
    )
    webbrowser.open(out.resolve().as_uri())


# ─── Radar standalone (non appelé par défaut) ─────────────────────────────────

def plot_radar(
    team_name: str,
    radar_values: list[float],
    cluster_mean: list[float],
    feature_names: list[str],
    cluster_id: int,
    bloc_name: str,
    output_dir: str,
) -> None:
    theta  = feature_names + [feature_names[0]]
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
        showlegend=True, template="plotly_white", height=450,
    )
    safe = team_name.replace(" ", "_").replace("/", "_").replace("'", "")
    out = Path(output_dir) / f"radar_{safe}_{bloc_name}.html"
    fig.write_html(str(out), include_plotlyjs="cdn")
    logger.info(f"Radar → {out}")
