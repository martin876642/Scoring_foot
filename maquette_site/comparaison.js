/* ============ FootScout — Comparaison ============ */

const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];

/* ---- 4 couleurs slots ---- */
const SLOT_COLORS = [
  { fg: "#5DCAA5", bg: "rgba(93,202,165,0.18)", line: "rgba(93,202,165,0.95)", fill: "rgba(93,202,165,0.16)" },
  { fg: "#378ADD", bg: "rgba(55,138,221,0.18)", line: "rgba(55,138,221,0.95)", fill: "rgba(55,138,221,0.16)" },
  { fg: "#EF9F27", bg: "rgba(239,159,39,0.18)", line: "rgba(239,159,39,0.95)", fill: "rgba(239,159,39,0.16)" },
  { fg: "#D85A30", bg: "rgba(216,90,48,0.18)", line: "rgba(216,90,48,0.95)", fill: "rgba(216,90,48,0.16)" },
];

function scoreClass(v) {
  if (v >= 90) return "s90";
  if (v >= 70) return "s70";
  if (v >= 50) return "s50";
  if (v >= 30) return "s30";
  if (v >= 10) return "s10";
  return "s0";
}
function scoreColor(v) {
  if (v >= 90) return "#378ADD";
  if (v >= 70) return "#1D9E75";
  if (v >= 50) return "#EF9F27";
  if (v >= 30) return "#D85A30";
  if (v >= 10) return "#E24B4A";
  return "#444441";
}
const SCORE_BG = { s90:"#0C447C", s70:"#0F6E56", s50:"#633806", s30:"#4a2000", s10:"#4a0000", s0:"#1a2235" };
const SCORE_FG = { s90:"#378ADD", s70:"#5DCAA5", s50:"#EF9F27", s30:"#D85A30", s10:"#E24B4A", s0:"#444441" };

/* ROLE_FEATURES est défini dans players-data.js (généré par 07_export_web.py)
   Il contient les 6 indicateurs les plus pondérés par rôle, tirés directement
   de ROLE_FEATURES dans 05_features_v2.py */

/* poste auquel appartient un rôle */
const ROLE_POSITION = {};
Object.entries(ROLES_BY_POSITION).forEach(([pos, roles]) => roles.forEach(r => ROLE_POSITION[r] = pos));

/* hash déterministe */
function hash(s) {
  let h = 2166136261;
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return (h >>> 0);
}

/* ===================== VALEUR PERCENTILE (player, role, feature) =====================
   - Si le joueur n'a pas le bon poste → null (incompatible)
   - Si zFeats réels disponibles → utilise la valeur réelle (0-100)
   - Sinon → estimation déterministe à partir du score (fallback maquette)
*/
function featureValue(player, role, feature) {
  const rolePos = ROLE_POSITION[role];
  if (!rolePos || rolePos !== player.poste) return null;

  // Vraies valeurs issues du pipeline (zFeats[role][feature])
  if (player.zFeats && player.zFeats[role]) {
    const real = player.zFeats[role][feature];
    if (real != null) return real;
    // null = donnée manquante pour ce joueur → fallback hash ci-dessous
  }

  // Fallback : estimation déterministe basée sur le score du joueur
  const seed = hash(player.id + "|" + role + "|" + feature);
  const noise = ((seed % 23) - 11);
  const isMain = player.role === role;
  const offset = isMain ? 0 : -10 - (seed % 8);
  let v = player.score + noise + offset;
  v = Math.max(5, Math.min(98, Math.round(v)));
  return v;
}

/* ===================== ÉTAT ===================== */
const STATE = {
  slots: [null, null, null, null],   // joueurs sélectionnés
  role: null,                          // rôle de comparaison
  pickerSlot: null,                    // index du slot en cours de sélection
  pickerQuery: "",
  pickerPos: "ALL",                    // filtre poste dans le picker
};

/* ===================== SLOTS ===================== */
function renderSlots() {
  const root = $("#slots");
  root.innerHTML = STATE.slots.map((p, i) => {
    if (!p) {
      return `
        <div class="slot empty" data-idx="${i}">
          <div class="plus">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 5v14M5 12h14"/></svg>
          </div>
          <div class="ph">Joueur ${String.fromCharCode(65 + i)}</div>
        </div>`;
    }
    const cls = scoreClass(p.score);
    const initials = p.nom.split(" ").map(w => w[0]).slice(0,2).join("");
    return `
      <div class="slot filled" data-idx="${i}">
        <button class="slot-close" data-clear="${i}" title="Retirer">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 6l12 12M18 6L6 18"/></svg>
        </button>
        <div class="slot-top">
          <div class="slot-avatar">
            ${initials}
            <span class="cm" style="background:${p.club.couleur}">${p.clubAbbr}</span>
          </div>
          <div class="slot-id">
            <div class="sname">${p.nom}</div>
            <div class="sclub"><span class="flag">${p.nationalite.flag}</span>${p.club.nom}</div>
          </div>
        </div>
        <div class="slot-mid">
          <div class="spos">
            <span class="pb ${p.poste}">${p.poste}</span>
            ${p.posteLabel}
          </div>
          <div class="srole" title="${p.role}">${p.role}</div>
        </div>
        <div class="slot-bot">
          <div>
            <div class="sval mono">${p.valeur} M€</div>
            <div class="sage">${p.age} ans · Pied ${p.pied === "D" ? "droit" : "gauche"}</div>
          </div>
          <div style="display:flex;flex-direction:column;align-items:flex-end;gap:6px">
            <div class="sscore" style="background:${SCORE_BG[cls]};color:${SCORE_FG[cls]}">${p.score}</div>
            <a class="slot-fiche-link" href="FootScout - Fiche Joueur.html?id=${encodeURIComponent(p.id)}&v=4" title="Voir la fiche">Fiche →</a>
          </div>
        </div>
      </div>`;
  }).join("");

  $$("#slots .slot.empty").forEach(el => {
    el.addEventListener("click", () => openPicker(+el.dataset.idx));
  });
  $$("#slots .slot-close").forEach(el => {
    el.addEventListener("click", e => {
      e.stopPropagation();
      const idx = +el.dataset.clear;
      STATE.slots[idx] = null;
      onSelectionChanged();
    });
  });
}

/* ===================== PICKER ===================== */
function openPicker(idx) {
  STATE.pickerSlot = idx;
  STATE.pickerQuery = "";
  STATE.pickerPos = "ALL";
  $("#picker").classList.add("show");
  renderPicker();
  setTimeout(() => $("#pickerSearch").focus(), 30);
}
function closePicker() {
  $("#picker").classList.remove("show");
  STATE.pickerSlot = null;
}

function renderPicker() {
  const positions = ["ALL", "GK", "CB", "FB", "DM", "CM", "AM", "W", "CF"];
  $("#pickerPills").innerHTML = positions.map(p =>
    `<button class="ph-pill ${STATE.pickerPos === p ? "active" : ""}" data-pos="${p}">${p === "ALL" ? "Tous postes" : p}</button>`
  ).join("");
  $$("#pickerPills .ph-pill").forEach(b => {
    b.addEventListener("click", () => { STATE.pickerPos = b.dataset.pos; renderPicker(); });
  });

  const q = STATE.pickerQuery.trim().toLowerCase();
  const selectedIds = new Set(STATE.slots.filter(Boolean).map(p => p.id));
  const list = PLAYERS_DB
    .filter(p => STATE.pickerPos === "ALL" || p.poste === STATE.pickerPos)
    .filter(p => !q || p.nom.toLowerCase().includes(q) || p.club.nom.toLowerCase().includes(q) || p.role.toLowerCase().includes(q))
    .sort((a, b) => b.score - a.score)
    .slice(0, 80);

  const html = list.length === 0
    ? `<div class="pl-empty">Aucun joueur trouvé.</div>`
    : list.map(p => {
        const disabled = selectedIds.has(p.id);
        const cls = scoreClass(p.score);
        const ini = p.nom.split(" ").map(w => w[0]).slice(0,2).join("");
        return `
          <div class="pl-row ${disabled ? "dis" : ""}" data-id="${p.id}">
            <div class="pla">${ini}</div>
            <div>
              <div class="pln">${p.nom}</div>
              <div class="pls"><span>${p.nationalite.flag}</span>${p.club.nom} · ${p.role}</div>
            </div>
            <div class="plpos ${p.poste}">${p.poste}</div>
            <div class="plsc" style="background:${SCORE_BG[cls]};color:${SCORE_FG[cls]}">${p.score}</div>
          </div>`;
      }).join("");
  $("#pickerList").innerHTML = html;

  $$("#pickerList .pl-row").forEach(r => {
    r.addEventListener("click", () => {
      if (r.classList.contains("dis")) return;
      const p = PLAYERS_DB.find(x => x.id === r.dataset.id);
      STATE.slots[STATE.pickerSlot] = p;
      closePicker();
      onSelectionChanged();
    });
  });
}

/* ===================== APRÈS CHANGEMENT SÉLECTION ===================== */
function onSelectionChanged() {
  renderSlots();
  renderRoleBar();
  renderComparison();
}

/* ===================== BARRE DE RÔLES ===================== */
function availableRoles() {
  if (typeof ROLES_BY_POSITION === "undefined") return [];
  const selected = STATE.slots.filter(Boolean);
  if (selected.length === 0) {
    return (ROLES_BY_POSITION.CF || []).map(r => ({ role: r, pos: "CF" }));
  }
  const postes = [];
  selected.forEach(p => { if (!postes.includes(p.poste)) postes.push(p.poste); });
  const roles = [];
  postes.forEach(pos => {
    (ROLES_BY_POSITION[pos] || []).forEach(r => roles.push({ role: r, pos }));
  });
  return roles;
}

function renderRoleBar() {
  const roles = availableRoles();
  if (roles.length === 0) return;

  if (!STATE.role || !roles.find(r => r.role === STATE.role)) {
    const first = STATE.slots.find(Boolean);
    STATE.role = first ? first.role : roles[0].role;
  }

  $("#roleBar").innerHTML = `
    <div class="rb-label">Comparer sur</div>
    <div class="rb-pills">
      ${roles.map(r => `
        <button class="role-pill ${r.role === STATE.role ? "active" : ""}" data-role="${r.role}">
          <span class="rp-pos">${r.pos}</span>${r.role}
        </button>`
      ).join("")}
    </div>`;

  $$("#roleBar .role-pill").forEach(b => {
    b.addEventListener("click", () => {
      STATE.role = b.dataset.role;
      renderRoleBar();
      renderComparison();
    });
  });
}

/* ===================== RADAR ===================== */
const CX = 230, CY = 230, MAXR = 150, SVGW = 460;
function polar(r, deg) {
  const a = (deg - 90) * Math.PI / 180;
  return [CX + r * Math.cos(a), CY + r * Math.sin(a)];
}

function renderRadar(role, features, playerValues) {
  const ns = "http://www.w3.org/2000/svg";
  const svg = $("#radarSvg");
  svg.setAttribute("viewBox", `0 0 ${SVGW} ${SVGW}`);
  svg.innerHTML = "";

  const mk = (tag, attrs) => {
    const e = document.createElementNS(ns, tag);
    for (const k in attrs) e.setAttribute(k, attrs[k]);
    return e;
  };

  // fond
  svg.appendChild(mk("circle", { cx: CX, cy: CY, r: MAXR, fill: "#080d15" }));
  // grilles concentriques
  [0.25, 0.5, 0.75, 1].forEach(t => {
    svg.appendChild(mk("circle", {
      cx: CX, cy: CY, r: MAXR * t, fill: "none",
      stroke: "#2a3548", "stroke-width": t === 1 ? 1 : 0.6,
      "stroke-dasharray": t === 1 ? "none" : "2 3", opacity: 0.7,
    }));
  });

  const n = features.length;
  // rayons
  for (let i = 0; i < n; i++) {
    const [x, y] = polar(MAXR, i * 360 / n);
    svg.appendChild(mk("line", { x1: CX, y1: CY, x2: x, y2: y, stroke: "#2a3548", "stroke-width": 0.5, opacity: 0.6 }));
  }

  // polygones par joueur (du moins prio au plus prio pour z-order : on dessine d'abord les surfaces, puis traits, puis points)
  // surfaces
  playerValues.forEach((pv, pi) => {
    if (!pv) return;
    const col = SLOT_COLORS[pi];
    const pts = pv.values.map((v, i) => {
      if (v == null) return null;
      const r = (v / 100) * MAXR;
      return polar(r, i * 360 / n);
    });
    if (pts.some(p => p === null)) return;
    const d = pts.map((p, i) => (i === 0 ? "M" : "L") + p[0].toFixed(2) + " " + p[1].toFixed(2)).join(" ") + " Z";
    svg.appendChild(mk("path", { d, fill: col.fill, stroke: "none" }));
  });

  // traits
  playerValues.forEach((pv, pi) => {
    if (!pv) return;
    const col = SLOT_COLORS[pi];
    const pts = pv.values.map((v, i) => {
      if (v == null) return null;
      const r = (v / 100) * MAXR;
      return polar(r, i * 360 / n);
    });
    if (pts.some(p => p === null)) return;
    const d = pts.map((p, i) => (i === 0 ? "M" : "L") + p[0].toFixed(2) + " " + p[1].toFixed(2)).join(" ") + " Z";
    svg.appendChild(mk("path", { d, fill: "none", stroke: col.line, "stroke-width": 1.6, "stroke-linejoin": "round" }));
  });

  // points
  playerValues.forEach((pv, pi) => {
    if (!pv) return;
    const col = SLOT_COLORS[pi];
    pv.values.forEach((v, i) => {
      if (v == null) return;
      const r = (v / 100) * MAXR;
      const [x, y] = polar(r, i * 360 / n);
      svg.appendChild(mk("circle", { cx: x, cy: y, r: 3, fill: col.line, stroke: "#080d15", "stroke-width": 1 }));
    });
  });

  // labels extérieurs
  features.forEach((label, i) => {
    const mid = i * 360 / n;
    const [lx, ly] = polar(MAXR + 18, mid);
    const dx = lx - CX;
    const anchor = Math.abs(dx) < 10 ? "middle" : dx > 0 ? "start" : "end";
    const t = mk("text", {
      x: lx.toFixed(1), y: ly.toFixed(1), "text-anchor": anchor,
      "dominant-baseline": "middle", "font-size": 11, fill: "#9aa4b2", "font-weight": 500,
      "font-family": "IBM Plex Sans, sans-serif",
    });
    t.textContent = label;
    svg.appendChild(t);
  });
}

/* ===================== LÉGENDE ===================== */
function renderLegend(playerValues) {
  $("#cmpLegend").innerHTML = STATE.slots.map((p, i) => {
    if (!p) return "";
    const col = SLOT_COLORS[i];
    const pv = playerValues[i];
    const avg = pv && pv.values.length ? Math.round(pv.values.reduce((a,b)=>a+b,0) / pv.values.length) : null;
    return `
      <div class="cmp-lg">
        <span class="swatch" style="background:${col.fg}"></span>
        <div style="min-width:0">
          <div class="lgn">${p.nom}</div>
          <div class="lgnsub">${p.club.nom} · ${p.role}</div>
        </div>
        <div class="lgavg" style="color:${col.fg}">${avg != null ? avg : "—"}</div>
      </div>`;
  }).join("");
}

/* ===================== TABLE COMPARAISON ===================== */
function renderTable(features, playerValues) {
  const slots = STATE.slots;
  const filled = slots.map((p, i) => p ? i : null).filter(i => i !== null);
  const ncols = Math.max(1, filled.length);
  const colTemplate = `minmax(150px, 1.5fr) ${"1fr ".repeat(ncols)}`.trim();

  // en-tête
  const colHead = `
    <div class="ct-col-head" style="grid-template-columns:${colTemplate}">
      <div class="h-feat">Indicateur</div>
      ${filled.map(i => {
        const p = slots[i]; const col = SLOT_COLORS[i];
        return `<div class="h-pl"><span class="h-sw" style="background:${col.fg}"></span><span class="h-name">${p.nom.split(" ").slice(-1)[0]}</span></div>`;
      }).join("")}
    </div>`;

  // lignes
  const rows = features.map((feat, fi) => {
    // déterminer la meilleure valeur pour cette feature
    const vals = filled.map(i => playerValues[i] ? playerValues[i].values[fi] : null);
    const valid = vals.filter(v => v != null);
    const best = valid.length ? Math.max(...valid) : null;
    return `
      <div class="cmp-row" style="grid-template-columns:${colTemplate}">
        <div class="cf">${feat}</div>
        ${filled.map((i, k) => {
          const v = vals[k]; const col = SLOT_COLORS[i];
          if (v == null) return `<div class="cv empty">—</div>`;
          const isBest = (v === best && best != null);
          return `
            <div class="cv ${isBest ? "best" : ""}" style="${isBest ? "color:" + col.fg : ""}">
              <div class="cvval" style="color:${col.fg}">${v}</div>
              <div class="cvbar"><i style="width:${v}%;background:${col.fg}"></i></div>
            </div>`;
        }).join("")}
      </div>`;
  }).join("");

  $("#cmpTable").innerHTML = colHead + rows;
}

/* ===================== ORCHESTRATEUR ===================== */
function renderComparison() {
  const role = STATE.role;
  const features = ROLE_FEATURES[role] || [];
  $("#radarRole").textContent = role || "—";
  const pos = ROLE_POSITION[role];
  const compatible = STATE.slots.filter(p => p && p.poste === pos).length;
  const total = STATE.slots.filter(Boolean).length;
  $("#radarSub").textContent = `${features.length} indicateurs · ${compatible}/${total} compatibles ${pos || ""}`;

  // valeurs joueurs : null si poste incompatible ou slot vide
  const playerValues = STATE.slots.map(p => {
    if (!p) return null;
    const values = features.map(f => featureValue(p, role, f));
    if (values.some(v => v == null)) return null;
    return { player: p, values };
  });

  // état vide global
  if (total === 0) {
    $("#cmpMain").style.display = "none";
    $("#cmpEmpty").style.display = "block";
    return;
  }
  $("#cmpEmpty").style.display = "none";
  $("#cmpMain").style.display = "grid";

  renderRadar(role, features, playerValues);
  renderLegend(playerValues);
  renderTable(features, playerValues);
}

/* ===================== INIT ===================== */
function init() {
  // Aucune pré-sélection — écran vide par défaut
  STATE.slots = [null, null, null, null];
  STATE.role = null;

  // picker listeners
  $("#pickerSearch").addEventListener("input", e => {
    STATE.pickerQuery = e.target.value;
    renderPicker();
  });
  $("#pickerClose").addEventListener("click", closePicker);
  $("#picker").addEventListener("click", e => {
    if (e.target.id === "picker") closePicker();
  });
  document.addEventListener("keydown", e => {
    if (e.key === "Escape" && $("#picker").classList.contains("show")) closePicker();
  });

  onSelectionChanged();
}
document.addEventListener("DOMContentLoaded", init);
