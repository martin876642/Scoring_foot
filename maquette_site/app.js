/* ============ FootScout — logique & rendu ============ */

const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];

// Variable globale du joueur affiché (remplace le const de data.js)
let PLAYER = null;

/* ---- échelle de couleur unifiée — 6 paliers ----
   90-100 : bleu ciel (top 10 %)
   70-90  : vert foncé
   50-70  : jaune
   30-50  : orange
   10-30  : rouge
   0-10   : gris foncé */
function scoreColor(v) {
  if (v >= 90) return "#378ADD";
  if (v >= 70) return "#1D9E75";
  if (v >= 50) return "#EF9F27";
  if (v >= 30) return "#D85A30";
  if (v >= 10) return "#E24B4A";
  return "#444441";
}
const roleColor   = scoreColor;
const sectorColor = scoreColor;
const statColor   = scoreColor;

/* ===================== HEADER ===================== */
function renderHeader() {
  const p = PLAYER;
  $("#header").innerHTML = `
    <div class="photo-wrap">
      <div class="photo">
        ${p.photoUrl
          ? `<img src="${p.photoUrl}" alt="${p.nom}" loading="lazy"
                  onerror="this.style.display='none';this.nextElementSibling.style.display='flex'">`
          : ""}
        <span class="photo-initials" style="${p.photoUrl ? "display:none" : ""}">
          ${p.nom.split(" ").map(w => w[0]).slice(0,2).join("")}
        </span>
      </div>
      <div class="club-badge-ov" style="background:${p.club.couleur}">${p.club.abbr}</div>
    </div>
    <div class="identity">
      <div class="name">${p.nom}</div>
      <div class="badges">
        <span class="chip club" style="background:${p.club.couleur}">${p.club.nom}</span>
        <span class="chip">${p.ligue}</span>
        <span class="chip">${p.age} ans</span>
        ${p.taille ? `<span class="chip">${p.taille} cm</span>` : ""}
        <span class="chip">Pied ${p.pied.toLowerCase()}</span>
        <span class="chip"><span class="flag">${p.nationalite.code}</span>${p.nationalite.nom}</span>
      </div>
      ${p.postesAll && p.postesAll.length > 1 ? `
      <div class="poste-selector">
        <span class="poste-sel-label">Poste évalué :</span>
        ${p.postesAll.map(pos => `
          <button class="poste-pill ${pos === p.posteAbbr ? "active" : ""}" data-poste="${pos}">
            ${pos}
          </button>`).join("")}
      </div>` : ""}
    </div>
    <div class="value-box">
      <div class="v">${p.valeur}<small> M€</small></div>
      <div class="contract">Contrat jusqu'au ${p.contrat}</div>
      <button class="btn-compare" id="btnCompare">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 6h7M3 12h7M3 18h7M21 6h-7M21 12h-7M21 18h-7"/></svg>
        Comparer
      </button>
    </div>`;

  // Sélecteur de poste (si plusieurs postes disponibles)
  $$(".poste-pill").forEach(btn => {
    btn.addEventListener("click", () => {
      const selectedPoste = btn.dataset.poste;
      if (selectedPoste === PLAYER.posteAbbr) return;
      PLAYER = buildPlayerFromDB(PLAYER._pb, selectedPoste);
      renderHeader();
      renderQuickStats();
      renderRoles();
      renderSimilar();
      if (PLAYER.rolesPrincipaux && PLAYER.rolesPrincipaux.length) {
        selectRole(PLAYER.rolesPrincipaux[0].id);
      }
    });
  });

  $("#btnCompare").addEventListener("click", () => {
    const b = $("#btnCompare");
    const orig = b.innerHTML;
    b.innerHTML = "Comparateur — bientôt disponible";
    setTimeout(() => (b.innerHTML = orig), 1600);
  });
}

/* ===================== STATS RAPIDES ===================== */
function renderQuickStats() {
  $("#quickstats").innerHTML = PLAYER.statsRapides.map(s => `
    <div class="qs">
      <div class="ql">${s.label}</div>
      <div class="qv mono">${s.valeur}</div>
    </div>`).join("");
}

/* ===================== ROLES ===================== */
let ACTIVE_ROLE = null;

function roleRowHTML(r) {
  const col = roleColor(r.score);
  return `
    <div class="role" data-role="${r.id}">
      <div class="role-badge" style="background:${col}">${r.score}</div>
      <div class="role-body">
        <div class="role-name">${r.nom} <span class="role-rank">${r.rang}</span></div>
        <div class="role-bar"><i style="width:0%;background:${col}" data-w="${r.score}"></i></div>
      </div>
      <div class="chev"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 6l6 6-6 6"/></svg></div>
    </div>`;
}

function renderRoles() {
  const p = PLAYER;
  let html = p.rolesPrincipaux.map(roleRowHTML).join("");
  if (p.rolesSecondaires && p.rolesSecondaires.length) {
    html += `<div class="subhead">Poste secondaire : ${p.posteSecondaireAbbr} · ${p.posteSecondaire}</div>`;
    html += p.rolesSecondaires.map(roleRowHTML).join("");
  }
  $("#roles").innerHTML = html;

  $$(".role").forEach(el => {
    el.addEventListener("click", () => selectRole(el.dataset.role));
  });

  // animation des barres
  requestAnimationFrame(() => {
    $$(".role-bar i").forEach(i => (i.style.width = i.dataset.w + "%"));
  });
}

function allRoles() { return [...PLAYER.rolesPrincipaux, ...PLAYER.rolesSecondaires]; }

function selectRole(id) {
  ACTIVE_ROLE = allRoles().find(r => r.id === id);
  $$(".role").forEach(el => el.classList.toggle("active", el.dataset.role === id));
  renderRadar(ACTIVE_ROLE);
  renderLegend(ACTIVE_ROLE);
}

/* ===================== PROFILS SIMILAIRES ===================== */
function renderSimilar() {
  $("#similar").innerHTML = PLAYER.similaires.map(s => {
    const c = scoreColor(s.sim);
    return `
    <div class="sim">
      <div>
        <div class="sn">${s.nom}</div>
        <div class="sc">${s.club}</div>
      </div>
      <div class="sp" style="color:${c}">${s.sim}%</div>
      <div class="sbar"><i style="width:${s.sim}%;background:${c}"></i></div>
    </div>`;
  }).join("");
}

/* ===================== RADAR (pizza chart) ===================== */
const CX = 220, CY = 220, MAXR = 150, SVGW = 440;

function polar(r, deg) {
  const a = (deg - 90) * Math.PI / 180;
  return [CX + r * Math.cos(a), CY + r * Math.sin(a)];
}
function wedgePath(i, n, r) {
  const start = i * 360 / n, end = (i + 1) * 360 / n;
  const [x1, y1] = polar(r, start);
  const [x2, y2] = polar(r, end);
  const large = (end - start) > 180 ? 1 : 0;
  return `M ${CX} ${CY} L ${x1.toFixed(2)} ${y1.toFixed(2)} A ${r} ${r} 0 ${large} 1 ${x2.toFixed(2)} ${y2.toFixed(2)} Z`;
}

let radarAnim = null;

function renderRadar(role) {
  $("#radarRole").textContent = role.nom;
  $("#radarSub").textContent = `${PLAYER.poste} · ${role.features.length} indicateurs · percentiles`;

  const f = role.features, n = f.length;
  const ns = "http://www.w3.org/2000/svg";
  const svg = $("#radarSvg");
  svg.setAttribute("viewBox", `0 0 ${SVGW} ${SVGW}`);
  svg.innerHTML = "";

  const mk = (tag, attrs) => {
    const e = document.createElementNS(ns, tag);
    for (const k in attrs) e.setAttribute(k, attrs[k]);
    return e;
  };

  // fond du cercle
  svg.appendChild(mk("circle", { cx: CX, cy: CY, r: MAXR, fill: "#080d15" }));

  // cercles de référence 25/50/75/100
  [0.25, 0.5, 0.75, 1].forEach(t => {
    svg.appendChild(mk("circle", {
      cx: CX, cy: CY, r: MAXR * t, fill: "none",
      stroke: "#2a3548", "stroke-width": t === 1 ? 1 : 0.6,
      "stroke-dasharray": t === 1 ? "none" : "2 3", opacity: 0.7,
    }));
  });

  // rayons séparateurs
  for (let i = 0; i < n; i++) {
    const [x, y] = polar(MAXR, i * 360 / n);
    svg.appendChild(mk("line", { x1: CX, y1: CY, x2: x, y2: y, stroke: "#2a3548", "stroke-width": 0.5, opacity: 0.6 }));
  }

  // groupe des secteurs — dessinés à leur valeur finale (entrée gérée en CSS)
  const gWedges = mk("g", { class: "wedges" });
  svg.appendChild(gWedges);
  f.forEach((feat, i) => {
    const r = (feat.v / 100) * MAXR;
    const pth = mk("path", { d: wedgePath(i, n, r), fill: sectorColor(feat.v), "fill-opacity": 0.9 });
    gWedges.appendChild(pth);
  });

  // labels + valeurs
  const gText = mk("g", { class: "rtext" });
  svg.appendChild(gText);
  f.forEach((feat, i) => {
    const mid = (i + 0.5) * 360 / n;
    // label extérieur
    const [lx, ly] = polar(MAXR + 16, mid);
    const dx = lx - CX;
    const anchor = Math.abs(dx) < 10 ? "middle" : dx > 0 ? "start" : "end";
    const lbl = mk("text", {
      x: lx.toFixed(1), y: ly.toFixed(1), "text-anchor": anchor,
      "dominant-baseline": "middle", "font-size": 10.5, fill: "#9aa4b2", "font-weight": 500,
    });
    lbl.textContent = feat.label;
    gText.appendChild(lbl);

    // valeur intérieure
    const vr = Math.max((feat.v / 100) * MAXR - 16, 20);
    const [vx, vy] = polar(vr, mid);
    const val = mk("text", {
      x: vx.toFixed(1), y: vy.toFixed(1), "text-anchor": "middle",
      "dominant-baseline": "middle", "font-size": 12.5, fill: "#fff", "font-weight": 700,
      "font-family": "IBM Plex Mono, monospace",
    });
    val.textContent = feat.v;
    gText.appendChild(val);
  });
}

function renderLegend(role) {
  $("#legend").innerHTML = role.features.map(f => `
    <div class="lg">
      <div class="lgl"><span class="sw" style="background:${sectorColor(f.v)}"></span><span>${f.label}</span></div>
      <div class="lgv">${f.v}</div>
    </div>`).join("");
}

/* ===================== STATS DÉTAILLÉES ===================== */
function renderDetail() {
  $("#detail").innerHTML = PLAYER.statsDetaillees.map(block => `
    <div class="detail-card">
      <div class="detail-title">${block.titre}</div>
      ${block.stats.map(s => `
        <div class="stat-row">
          <div class="sl">${s.label}</div>
          <div class="stat-bar" data-brut="${s.brut}" data-label="${s.label}">
            <i style="width:0%;background:${statColor(s.p)}" data-w="${s.p}"></i>
          </div>
          <div class="sv" style="color:${statColor(s.p)}">${s.p}</div>
        </div>`).join("")}
    </div>`).join("");

  requestAnimationFrame(() => {
    $$("#detail .stat-bar i").forEach(i => (i.style.width = i.dataset.w + "%"));
  });

  // tooltips
  const tip = $("#tooltip");
  $$("#detail .stat-bar").forEach(bar => {
    bar.addEventListener("mouseenter", () => {
      tip.innerHTML = `<div class="tt-l">${bar.dataset.label}</div>${bar.dataset.brut}`;
      tip.classList.add("show");
    });
    bar.addEventListener("mousemove", e => {
      tip.style.left = (e.clientX + 14) + "px";
      tip.style.top = (e.clientY - 10) + "px";
    });
    bar.addEventListener("mouseleave", () => tip.classList.remove("show"));
  });
}

/* ===================== CONSTRUCTION FICHE DEPUIS PLAYERS_DB =====================
   Utilisé quand l'URL contient ?id=<player-id>
   Construit un objet PLAYER complet depuis l'entrée PLAYERS_DB correspondante.
*/
/* ROLES_BY_POSITION et ROLE_FEATURES sont définis dans players-data.js */

function buildRolesForPoste(pb, poste) {
  const rolesForPoste = (typeof ROLES_BY_POSITION !== "undefined" ? ROLES_BY_POSITION[poste] : []) || [];
  return rolesForPoste
    .filter(roleName => pb.zFeats && pb.zFeats[roleName])
    .map(roleName => {
      const feats = pb.zFeats[roleName];
      const featLabels = (typeof ROLE_FEATURES !== "undefined" ? ROLE_FEATURES[roleName] : null) || [];
      const features = featLabels.map(label => ({
        label,
        v: feats[label] != null ? feats[label] : 50,
      }));
      const avg = Math.round(features.reduce((s, f) => s + f.v, 0) / (features.length || 1));
      const score = roleName === pb.role ? pb.score : Math.max(1, Math.min(99, avg));
      const rang = roleName === pb.role ? `#${pb.rangLigue} ${pb.club.ligue}` : "";
      return { id: roleName.toLowerCase().replace(/[^a-z0-9]/g, "_"), nom: roleName, score, rang, features };
    })
    .sort((a, b) => b.score - a.score);
}

function buildPlayerFromDB(pb, selectedPoste) {
  const poste = selectedPoste || pb.poste;
  const postesAll = pb.postesAll && pb.postesAll.length ? pb.postesAll : [pb.poste];

  const rolesPrincipaux = buildRolesForPoste(pb, poste);

  // Trouver les joueurs similaires (même poste, même rôle, scores proches)
  const similaires = (typeof PLAYERS_DB !== "undefined" ? PLAYERS_DB : [])
    .filter(x => x.id !== pb.id && x.poste === poste && x.role === pb.role)
    .sort((a, b) => Math.abs(a.score - pb.score) - Math.abs(b.score - pb.score))
    .slice(0, 3)
    .map(x => ({
      nom: x.nom, club: x.club.nom,
      sim: Math.max(70, Math.min(99, 100 - Math.abs(x.score - pb.score) * 2)),
    }));

  const totalMin = pb.min90 > 0 ? pb.min90 * (pb.buts > 0 ? Math.round(pb.buts / (pb.buts / (pb.min90 > 0 ? 1 : 1))) : 1) : 0;

  const POSITION_LABEL_LOCAL = {
    GK:"Gardien", CB:"Défenseur central", FB:"Latéral",
    DM:"Milieu défensif", CM:"Milieu central", AM:"Milieu offensif",
    W:"Ailier", CF:"Avant-centre",
  };

  return {
    id:        pb.id,
    nom:       pb.nom,
    club:      { nom: pb.club.nom, abbr: pb.clubAbbr, couleur: pb.club.couleur },
    ligue:     pb.club.ligue,
    age:       pb.age,
    taille:    pb.taille || 0,
    pied:      pb.pied === "G" ? "Gauche" : "Droit",
    nationalite: { code: pb.nationalite.code, nom: pb.nationalite.code },
    poste:     POSITION_LABEL_LOCAL[poste] || pb.posteLabel,
    posteAbbr: poste,
    postesAll,
    _pb:       pb,   // référence au joueur source pour changer de poste
    valeur:    String(pb.valeur),
    contrat:   pb.contrat || "—",
    statsRapides: [
      { label: "Score principal", valeur: String(pb.score) },
      { label: "Min / match",     valeur: String(pb.min90) },
      { label: "Buts",            valeur: String(pb.buts) },
      { label: "xG saison",       valeur: String(pb.xg) },
      { label: "Valeur marchande", valeur: `${pb.valeur} M€` },
      { label: "Rang ligue",      valeur: `#${pb.rangLigue}/${pb.totalPosteLigue}` },
    ],
    rolesPrincipaux,
    rolesSecondaires: [],
    similaires,
    statsDetaillees: [],
  };
}

/* ===================== SCORE COLOR HELPER ===================== */
function scoreClass(v) {
  if (v >= 90) return "s90";
  if (v >= 70) return "s70";
  if (v >= 50) return "s50";
  if (v >= 30) return "s30";
  if (v >= 10) return "s10";
  return "s0";
}
const SCORE_BG = { s90:"#0C447C", s70:"#0F6E56", s50:"#633806", s30:"#4a2000", s10:"#4a0000", s0:"#1a2235" };
const SCORE_FG = { s90:"#378ADD", s70:"#5DCAA5", s50:"#EF9F27", s30:"#D85A30", s10:"#E24B4A", s0:"#444441" };

/* ===================== PAGE RECHERCHE ===================== */
const POSITIONS = ["GK","CB","FB","DM","CM","AM","W","CF"];
let fjPosFilter = "ALL";
let fjQuery = "";

let _searchInitialized = false;

function renderSearchPage() {
  document.getElementById("search-page").style.display = "flex";
  document.getElementById("player-page").style.display = "none";

  // Pills de filtrage par poste (reconstruites à chaque fois pour mettre à jour l'état actif)
  const pills = document.getElementById("fjPosPills");
  pills.innerHTML = ["ALL", ...POSITIONS].map(p =>
    `<button class="fj-pos-pill ${fjPosFilter === p ? "active" : ""}" data-pos="${p}">
      ${p === "ALL" ? "Tous" : p}
    </button>`
  ).join("");
  pills.querySelectorAll(".fj-pos-pill").forEach(b => {
    b.addEventListener("click", () => { fjPosFilter = b.dataset.pos; renderSearchResults(); });
  });

  // Listener input : ajouté une seule fois
  if (!_searchInitialized) {
    document.getElementById("fjSearchInput").addEventListener("input", e => {
      fjQuery = e.target.value;
      renderSearchResults();
    });
    _searchInitialized = true;
  }
  document.getElementById("fjSearchInput").focus();
  renderSearchResults();
}

function renderSearchResults() {
  // Mettre à jour les pills
  document.querySelectorAll(".fj-pos-pill").forEach(b => {
    b.classList.toggle("active", b.dataset.pos === fjPosFilter);
  });

  const q = fjQuery.trim().toLowerCase();
  let list = typeof PLAYERS_DB !== "undefined" ? PLAYERS_DB : [];

  if (fjPosFilter !== "ALL") list = list.filter(p => p.poste === fjPosFilter);
  if (q) list = list.filter(p =>
    p.nom.toLowerCase().includes(q) ||
    p.club.nom.toLowerCase().includes(q) ||
    p.role.toLowerCase().includes(q)
  );
  list = [...list].sort((a, b) => b.score - a.score).slice(0, 60);

  const container = document.getElementById("fjResults");
  if (!list.length) {
    container.innerHTML = `<div class="fj-empty">Aucun joueur trouvé</div>`;
    return;
  }
  container.innerHTML = list.map(p => {
    const ini = p.nom.split(" ").map(w => w[0]).slice(0,2).join("");
    const cls = scoreClass(p.score);
    return `<a class="fj-row" href="FootScout - Fiche Joueur.html?id=${encodeURIComponent(p.id)}&v=4">
      <div class="fj-ava">${ini}</div>
      <div>
        <div class="fj-name">${p.nom}</div>
        <div class="fj-sub">${p.nationalite.flag} ${p.club.nom} · ${p.role}</div>
      </div>
      <div class="fj-pos-badge">${p.poste}</div>
      <div class="fj-score-badge" style="background:${SCORE_BG[cls]};color:${SCORE_FG[cls]}">${p.score}</div>
    </a>`;
  }).join("");
}

/* ===================== PAGE DETAIL ===================== */
function showPlayerDetail(pb) {
  document.getElementById("search-page").style.display = "none";
  document.getElementById("player-page").style.display = "block";
  PLAYER = buildPlayerFromDB(pb);
  renderHeader();
  renderQuickStats();
  renderRoles();
  renderSimilar();
  if (PLAYER.rolesPrincipaux && PLAYER.rolesPrincipaux.length) {
    selectRole(PLAYER.rolesPrincipaux[0].id);
  }
}

/* ===================== INIT ===================== */
function init() {
  const params = new URLSearchParams(window.location.search);
  const playerId = params.get("id");

  if (playerId && typeof PLAYERS_DB !== "undefined") {
    const found = PLAYERS_DB.find(p => p.id === playerId);
    if (found) {
      showPlayerDetail(found);
      return;
    }
  }

  // Pas de joueur → afficher la recherche
  renderSearchPage();
}
document.addEventListener("DOMContentLoaded", init);
