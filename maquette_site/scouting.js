/* ============ FootScout — Scouting (logique + rendu) ============ */

const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];

/* ---- échelles ---- */
function scoreClass(v) {
  if (v >= 90) return "s90";
  if (v >= 70) return "s70";
  if (v >= 50) return "s50";
  if (v >= 30) return "s30";
  if (v >= 10) return "s10";
  return "s0";
}

/* ---- état des filtres ---- */
const LEAGUES = ["Premier League", "La Liga", "Serie A", "Bundesliga", "Ligue 1"];
const POSITIONS = ["GK", "CB", "FB", "DM", "CM", "AM", "W", "CF"];

const STATE = {
  query: "",
  leagues: new Set(LEAGUES),
  positions: new Set(POSITIONS),
  role: "",          // "" = tous
  scoreMin: 0,
  valMin: 0,
  valMax: 200,
  ageMin: 16,
  ageMax: 40,
  foot: "all",        // all | D | G
  sort: "score",      // score | val | age | buts | min
  sortDir: -1,        // -1 desc, 1 asc
  view: "list",       // list | grid
};

function defaultsCopy() {
  return {
    query: "",
    leagues: new Set(LEAGUES),
    positions: new Set(POSITIONS),
    role: "",
    scoreMin: 0,
    valMin: 0, valMax: 200,
    ageMin: 16, ageMax: 40,
    foot: "all",
    sort: "score", sortDir: -1, view: STATE.view,
  };
}

/* ===================== RENDU FILTRES ===================== */
function renderFiltersSkeleton() {
  $("#filters-scroll").innerHTML = `
    <div class="flt-head">
      <h2>Filtres</h2>
      <button class="flt-reset" id="btnReset">Réinitialiser</button>
    </div>
    <div class="search-wrap">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="7"/><path d="M20 20l-3.5-3.5"/></svg>
      <input class="search" id="search" placeholder="Rechercher un joueur..." />
    </div>

    <div class="flt-section">
      <div class="flt-label">Compétition</div>
      <div class="pills" id="leaguePills"></div>
    </div>

    <div class="flt-section">
      <div class="flt-label">Poste</div>
      <div class="pills" id="postPills"></div>
    </div>

    <div class="flt-section">
      <div class="flt-label">Rôle</div>
      <select class="flt-select" id="roleSelect"></select>
      <div class="flt-hint">Le score affiché correspond au rôle sélectionné. Sans rôle, le meilleur score du joueur est affiché.</div>
    </div>

    <div class="flt-section">
      <div class="flt-label">Score minimum <span class="val" id="scoreMinVal">0</span></div>
      <div class="range-wrap">
        <input type="range" min="0" max="100" value="0" class="flt-range score-track" id="scoreMin" />
        <div class="score-legend" id="scoreLegend"></div>
      </div>
    </div>

    <div class="flt-section">
      <div class="flt-label">Valeur marchande</div>
      <div class="dual-range" id="valRange"></div>
      <div class="dual-vals"><span id="valMinTxt">0 M€</span><span id="valMaxTxt">200 M€+</span></div>
    </div>

    <div class="flt-section">
      <div class="flt-label">Âge</div>
      <div class="dual-range" id="ageRange"></div>
      <div class="dual-vals"><span id="ageMinTxt">16 ans</span><span id="ageMaxTxt">40 ans</span></div>
    </div>

    <div class="flt-section">
      <div class="flt-label">Pied fort</div>
      <div class="pills" id="footPills"></div>
    </div>
  `;

  // ---- compétitions
  $("#leaguePills").innerHTML = LEAGUES.map(l =>
    `<div class="pill active" data-lg="${l}">${l}</div>`).join("");
  $$("#leaguePills .pill").forEach(p => p.addEventListener("click", () => {
    const lg = p.dataset.lg;
    if (STATE.leagues.has(lg)) STATE.leagues.delete(lg); else STATE.leagues.add(lg);
    p.classList.toggle("active");
    update();
  }));

  // ---- postes
  $("#postPills").innerHTML = POSITIONS.map(p =>
    `<div class="pill active" data-ps="${p}">${p}</div>`).join("");
  $$("#postPills .pill").forEach(p => p.addEventListener("click", () => {
    const ps = p.dataset.ps;
    if (STATE.positions.has(ps)) STATE.positions.delete(ps); else STATE.positions.add(ps);
    p.classList.toggle("active");
    renderRoleSelect();
    update();
  }));

  renderRoleSelect();
  $("#roleSelect").addEventListener("change", e => { STATE.role = e.target.value; update(); });

  // ---- score min
  const sm = $("#scoreMin");
  sm.addEventListener("input", () => {
    STATE.scoreMin = +sm.value;
    $("#scoreMinVal").textContent = STATE.scoreMin;
    updateScoreLegend();
    update();
  });
  renderScoreLegend();

  // ---- valeur
  buildDualRange("valRange", 0, 200, 0, 200,
    (lo, hi) => {
      STATE.valMin = lo; STATE.valMax = hi;
      $("#valMinTxt").textContent = `${lo} M€`;
      $("#valMaxTxt").textContent = `${hi >= 200 ? "200 M€+" : hi + " M€"}`;
      update();
    });

  // ---- âge
  buildDualRange("ageRange", 16, 40, 16, 40,
    (lo, hi) => {
      STATE.ageMin = lo; STATE.ageMax = hi;
      $("#ageMinTxt").textContent = `${lo} ans`;
      $("#ageMaxTxt").textContent = `${hi} ans`;
      update();
    });

  // ---- pied
  $("#footPills").innerHTML = [
    ["all", "Tous"], ["D", "Droit"], ["G", "Gauche"],
  ].map(([v, l]) => `<div class="pill ${STATE.foot === v ? "active" : ""}" data-ft="${v}">${l}</div>`).join("");
  $$("#footPills .pill").forEach(p => p.addEventListener("click", () => {
    STATE.foot = p.dataset.ft;
    $$("#footPills .pill").forEach(x => x.classList.toggle("active", x === p));
    update();
  }));

  $("#search").addEventListener("input", e => { STATE.query = e.target.value.trim().toLowerCase(); update(); });
  $("#btnReset").addEventListener("click", resetFilters);
}

function renderRoleSelect() {
  const sel = $("#roleSelect");
  let roles = [];
  STATE.positions.forEach(p => roles.push(...ROLES_BY_POSITION[p]));
  // dédoublonnage en gardant l'ordre
  roles = [...new Set(roles)];
  const cur = STATE.role;
  sel.innerHTML = `<option value="">Tous les rôles</option>` +
    roles.map(r => `<option value="${r}" ${cur === r ? "selected" : ""}>${r}</option>`).join("");
  if (cur && !roles.includes(cur)) { STATE.role = ""; sel.value = ""; }
}

function renderScoreLegend() {
  const stops = [
    { v: 0,   c: "#444441" },
    { v: 30,  c: "#D85A30" },
    { v: 50,  c: "#EF9F27" },
    { v: 70,  c: "#1D9E75" },
    { v: 90,  c: "#378ADD" },
    { v: 100, c: "#378ADD" },
  ];
  $("#scoreLegend").innerHTML = stops.map(s =>
    `<div data-v="${s.v}"><span class="dot" style="background:${s.c}"></span>${s.v}</div>`).join("");
  updateScoreLegend();
}
function updateScoreLegend() {
  $$("#scoreLegend > div").forEach(d => {
    d.classList.toggle("dim", +d.dataset.v < STATE.scoreMin);
  });
}

/* ---- Double slider générique ---- */
function buildDualRange(containerId, min, max, lo, hi, onChange) {
  const wrap = $("#" + containerId);
  wrap.innerHTML = `
    <div class="track"></div>
    <div class="fill"></div>
    <input type="range" min="${min}" max="${max}" value="${lo}" data-h="lo" />
    <input type="range" min="${min}" max="${max}" value="${hi}" data-h="hi" />`;
  const inputs = $$('input', wrap);
  const fill = $('.fill', wrap);
  function refresh() {
    let lo = +inputs[0].value, hi = +inputs[1].value;
    if (lo > hi) { const t = lo; lo = hi; hi = t; inputs[0].value = lo; inputs[1].value = hi; }
    const pLo = (lo - min) / (max - min) * 100;
    const pHi = (hi - min) / (max - min) * 100;
    fill.style.left = pLo + "%"; fill.style.width = (pHi - pLo) + "%";
    onChange(lo, hi);
  }
  inputs.forEach(i => i.addEventListener("input", refresh));
  refresh();
}

/* ===================== APPLIQUE LES FILTRES ===================== */
function filtered() {
  let arr = PLAYERS_DB.slice();
  if (STATE.query) {
    const q = STATE.query;
    arr = arr.filter(p => p.nom.toLowerCase().includes(q) || p.club.nom.toLowerCase().includes(q));
  }
  arr = arr.filter(p => STATE.leagues.has(p.club.ligue));
  arr = arr.filter(p => STATE.positions.has(p.poste));
  if (STATE.role) arr = arr.filter(p => p.role === STATE.role);
  arr = arr.filter(p => p.score >= STATE.scoreMin);
  arr = arr.filter(p => p.valeur >= STATE.valMin && (STATE.valMax >= 200 || p.valeur <= STATE.valMax));
  arr = arr.filter(p => p.age >= STATE.ageMin && p.age <= STATE.ageMax);
  if (STATE.foot !== "all") arr = arr.filter(p => p.pied === STATE.foot);

  const dir = STATE.sortDir;
  const key = {
    score: "score", val: "valeur", age: "age", min: "min90",
  }[STATE.sort] || "score";
  arr.sort((a, b) => dir * ((a[key] ?? 0) - (b[key] ?? 0)));
  return arr;
}

/* ===================== RENDU LISTE ===================== */
function renderListHead() {
  $("#listHead").innerHTML = `
    <div class="title"><strong id="countMain">0</strong> joueurs <span class="meta">· Big 5 · 2025-26</span></div>
    <div class="list-controls">
      <div class="sort-wrap">
        <label>Trier par</label>
        <select class="sort-select" id="sortSelect">
          <option value="score">Meilleur score</option>
          <option value="val">Valeur marchande</option>
          <option value="age">Âge</option>
          <option value="min">Minutes</option>
        </select>
      </div>
      <div class="view-toggle">
        <button data-view="list" class="active" title="Vue liste">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 6h16M4 12h16M4 18h16"/></svg>
        </button>
        <button data-view="grid" title="Vue grille">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/></svg>
        </button>
      </div>
    </div>`;
  $("#sortSelect").addEventListener("change", e => { STATE.sort = e.target.value; update(); });
  $$("#listHead .view-toggle button").forEach(b => b.addEventListener("click", () => {
    STATE.view = b.dataset.view;
    $$("#listHead .view-toggle button").forEach(x => x.classList.toggle("active", x === b));
    render();
  }));
}

function avatarHTML(p) {
  const initials = p.nom.split(" ").map(s => s[0]).slice(0, 2).join("").toUpperCase();
  const inner = p.photoUrl
    ? `<img src="${p.photoUrl}" alt="${p.nom}" loading="lazy"
            onerror="this.style.display='none';this.nextElementSibling.style.display='flex'">
       <span style="display:none">${initials}</span>`
    : initials;
  return `<div class="avatar">${inner}
    <div class="club-mini" style="background:${p.club.couleur}">${p.clubAbbr.slice(0,2)}</div>
  </div>`;
}

function rowHTML(p, idx) {
  const sc = scoreClass(p.score);
  return `
    <div class="row ${idx === 0 ? "first" : ""}" data-id="${p.id}">
      <div class="c-rank">${idx + 1}</div>
      <div class="c-player">
        ${avatarHTML(p)}
        <div>
          <div class="pn">${p.nom}</div>
          <div class="pnat"><span class="flag">${p.nationalite.flag}</span>${p.nationalite.code}</div>
        </div>
      </div>
      <div class="c-club">
        <div class="cl">${p.club.nom}</div>
        <div class="lg">${p.club.ligue}</div>
      </div>
      <div><span class="pos-badge ${p.poste}">${p.poste}</span></div>
      <div class="c-role">${p.role}</div>
      <div class="c-score">
        <div class="score-badge ${sc}"
             data-pos="${p.poste}"
             data-rl="${p.rangLigue}/${p.totalPosteLigue}"
             data-rb="${p.rangBig5}/${p.totalPosteBig5}"
             data-lg-abbr="${p.club.la}">${p.score}</div>
        <div class="score-rank">#${p.rangLigue} ${p.club.la}</div>
      </div>
      <div class="c-min">
        <div class="ctxbar"><i style="height:${Math.round(p.min90 / 90 * 100)}%"></i></div>
        ${p.min90}'
      </div>
      <div class="c-val">${formatVal(p.valeur)}</div>
      <div class="c-age">${p.age}</div>
    </div>`;
}

function formatVal(m) {
  if (m >= 1) return `${m} M€`;
  return `${Math.round(m * 1000)} K€`;
}

function renderTable(rows) {
  if (!rows.length) { renderEmpty(); return; }
  const headers = [
    ["", false, "c"],
    ["Joueur", false, "l"],
    ["Club / Ligue", false, "l"],
    ["Poste", false, "c"],
    ["Rôle principal", false, "l"],
    ["Score", "score", "c"],
    ["Min/90", "min", "l"],
    ["Valeur", "val", "r"],
    ["Âge", "age", "r"],
  ];
  const headHTML = headers.map(([lbl, sortKey, al]) => {
    const right = al === "r" ? "right" : al === "c" ? "center" : "";
    const sortable = sortKey ? "sortable" : "";
    const arrow = (sortKey && STATE.sort === sortKey) ? `<span class="arrow">${STATE.sortDir < 0 ? "▼" : "▲"}</span>` : "";
    return `<div class="ph ${right} ${sortable}" ${sortKey ? `data-sort="${sortKey}"` : ""}>${lbl}${arrow}</div>`;
  }).join("");

  $("#listBody").innerHTML = `<div class="player-table">${headHTML}${rows.map((r, i) => rowHTML(r, i)).join("")}</div>`;

  $$(".ph.sortable").forEach(h => h.addEventListener("click", () => {
    const k = h.dataset.sort;
    if (STATE.sort === k) STATE.sortDir = -STATE.sortDir;
    else { STATE.sort = k; STATE.sortDir = -1; }
    $("#sortSelect").value = k;
    update();
  }));
  attachRowHandlers();
  attachScoreTooltips();
}

function renderGrid(rows) {
  if (!rows.length) { renderEmpty(); return; }
  $("#listBody").innerHTML = `<div class="player-grid">${rows.map(p => {
    const sc = scoreClass(p.score);
    return `
    <div class="pcard" data-id="${p.id}">
      <div class="ptop">
        ${avatarHTML(p)}
        <div style="flex:1; min-width:0;">
          <div class="pn">${p.nom}</div>
          <div class="pcl">${p.club.nom} · ${p.club.la}</div>
        </div>
        <span class="pos-badge ${p.poste}">${p.poste}</span>
      </div>
      <div class="pmid">
        <div class="score-badge ${sc}"
          data-pos="${p.poste}" data-rl="${p.rangLigue}/${p.totalPosteLigue}" data-rb="${p.rangBig5}/${p.totalPosteBig5}" data-lg-abbr="${p.club.la}">${p.score}</div>
        <div class="pr">${p.role}</div>
      </div>
      <div class="pstats">
        <div class="ps"><div class="ps-l">Buts</div><div class="ps-v">${p.buts}</div></div>
        <div class="ps"><div class="ps-l">xG</div><div class="ps-v">${p.xg.toFixed(1)}</div></div>
        <div class="ps"><div class="ps-l">Min/90</div><div class="ps-v">${p.min90}'</div></div>
      </div>
      <div class="pfoot">
        <span class="pv">${formatVal(p.valeur)}</span>
        <span class="pa">${p.age} ans · ${p.nationalite.flag}</span>
      </div>
    </div>`;
  }).join("")}</div>`;
  attachRowHandlers();
  attachScoreTooltips();
}

function renderEmpty() {
  $("#listBody").innerHTML = `
    <div class="empty">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="11" cy="11" r="7"/><path d="M20 20l-3.5-3.5"/></svg>
      <p>Aucun joueur ne correspond à ces critères</p>
      <button class="btn-outline-green" id="emptyReset">Réinitialiser les filtres</button>
    </div>`;
  $("#emptyReset").addEventListener("click", resetFilters);
}

function attachRowHandlers() {
  $$("#listBody .row, #listBody .pcard").forEach(el => {
    el.addEventListener("click", () => {
      const id = el.dataset.id || "";
      window.location.href = `FootScout - Fiche Joueur.html${id ? "?id=" + encodeURIComponent(id) : ""}`;
    });
  });
}

function attachScoreTooltips() {
  const tip = $("#sTip");
  $$("#listBody .score-badge").forEach(b => {
    b.addEventListener("mouseenter", () => {
      const [rl, tl] = b.dataset.rl.split("/");
      const [rb, tb] = b.dataset.rb.split("/");
      tip.innerHTML = `
        <div class="tl">Rang ${b.dataset.pos} · ${b.dataset.lgAbbr}</div>
        <div class="tr">#${rl} sur ${tl} en ${b.dataset.lgAbbr}</div>
        <div class="tr">#${rb} sur ${tb} en Big 5</div>`;
      tip.classList.add("show");
    });
    b.addEventListener("mousemove", e => {
      const w = tip.offsetWidth || 200;
      const x = Math.min(e.clientX + 14, window.innerWidth - w - 12);
      tip.style.left = x + "px";
      tip.style.top = (e.clientY + 14) + "px";
    });
    b.addEventListener("mouseleave", () => tip.classList.remove("show"));
  });
}

/* ===================== UPDATE / RESET ===================== */
function update() {
  const rows = filtered();
  const n = rows.length;
  const target = $("#countMain");
  if (target) target.textContent = n;
  const c2 = $("#applyCount");
  if (c2) c2.innerHTML = `<strong>${n}</strong> joueur${n > 1 ? "s" : ""} correspond${n > 1 ? "ent" : ""}`;
  render(rows);
}
function render(rows) {
  rows = rows || filtered();
  if (STATE.view === "grid") renderGrid(rows);
  else renderTable(rows);
}

function resetFilters() {
  Object.assign(STATE, defaultsCopy());
  renderFiltersSkeleton();
  renderListHead();
  update();
}

/* ===================== INIT ===================== */
function init() {
  renderFiltersSkeleton();
  renderListHead();
  update();
}
document.addEventListener("DOMContentLoaded", init);
