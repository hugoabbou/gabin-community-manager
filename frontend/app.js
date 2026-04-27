// ── Auth guard ───────────────────────────────────────────────────────────────
const TOKEN = localStorage.getItem("gabin_token");
if (!TOKEN) window.location.href = "/";

async function api(method, path, body = null) {
  const opts = {
    method,
    headers: {
      "Content-Type": "application/json",
      "Authorization": "Bearer " + TOKEN,
    },
  };
  if (body) opts.body = JSON.stringify(body);
  const res = await fetch(path, opts);
  if (res.status === 401) { logout(); return; }
  if (!res.ok) {
    const err = await res.text();
    throw new Error(err);
  }
  return res.json();
}

function logout() {
  localStorage.removeItem("gabin_token");
  localStorage.removeItem("gabin_user");
  window.location.href = "/";
}

// ── State ─────────────────────────────────────────────────────────────────────
const state = {
  themes: [],
  activeThemes: new Set(),
  selectedEvent: null,
  platforms: new Set(["instagram", "facebook"]),
  requireValidation: true,
  generatedPosts: [],
  currentTab: "generate",
};

// ── Init ──────────────────────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", async () => {
  setHeaderDate();
  const user = localStorage.getItem("gabin_user");
  if (user) document.getElementById("headerUser").textContent = user;
  initPlanningMonth();
  await Promise.all([loadThemes(), loadUpcomingEvents(), loadTeams(), loadSettings()]);
  await loadTabContent("queue");
  updateQueueBadge();
});

function setHeaderDate() {
  const d = new Date();
  const days = ["Dimanche", "Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi"];
  const months = ["jan", "fév", "mars", "avr", "mai", "juin", "juil", "août", "sep", "oct", "nov", "déc"];
  document.getElementById("headerDate").textContent =
    `${days[d.getDay()]} ${d.getDate()} ${months[d.getMonth()]} ${d.getFullYear()}`;
}

// ── API helpers (defined above in auth guard) ─────────────────────────────────

// ── Themes ────────────────────────────────────────────────────────────────────
async function loadThemes() {
  const themes = await api("GET", "/api/themes");
  state.themes = themes;
  const settings = await api("GET", "/api/settings");
  const active = settings.active_themes || ["sports_event", "daily_special", "ambiance"];
  active.forEach(t => state.activeThemes.add(t));
  renderThemes();
}

function renderThemes() {
  const container = document.getElementById("themeChips");
  container.innerHTML = state.themes.map(t => `
    <div class="theme-chip ${state.activeThemes.has(t.id) ? "active" : ""}"
         onclick="toggleTheme('${t.id}')">
      <span class="icon">${t.icon}</span>
      ${t.label}
    </div>
  `).join("");
}

function toggleTheme(id) {
  if (state.activeThemes.has(id)) {
    state.activeThemes.delete(id);
  } else {
    state.activeThemes.add(id);
  }
  renderThemes();
  api("PUT", "/api/settings", { active_themes: [...state.activeThemes] });
}

// ── Sports Events ─────────────────────────────────────────────────────────────
async function loadUpcomingEvents() {
  try {
    const events = await api("GET", "/api/sports/upcoming");
    renderEvents(events);
  } catch {
    document.getElementById("eventList").innerHTML =
      '<div class="event-empty">Impossible de charger les événements</div>';
  }
}

function renderEvents(events) {
  const container = document.getElementById("eventList");
  if (!events || events.length === 0) {
    container.innerHTML = '<div class="event-empty">Aucun événement à venir</div>';
    return;
  }
  container.innerHTML = events.slice(0, 10).map(e => `
    <div class="event-card ${state.selectedEvent?.id === e.id ? "selected" : ""}"
         onclick="selectEvent(${JSON.stringify(JSON.stringify(e))})">
      <div class="event-sport">${e.emoji || ""} ${e.sport}</div>
      <div class="event-teams">${e.name}</div>
      <div class="event-meta">${e.date_display} ${e.time_display ? "· " + e.time_display : ""} · ${e.league}</div>
    </div>
  `).join("");
}

function selectEvent(jsonStr) {
  const event = JSON.parse(jsonStr);
  if (state.selectedEvent?.id === event.id) {
    state.selectedEvent = null;
  } else {
    state.selectedEvent = event;
    // Auto-activate sports theme
    state.activeThemes.add("sports_event");
    renderThemes();
  }
  loadUpcomingEvents();
}

// ── Teams ─────────────────────────────────────────────────────────────────────
async function loadTeams() {
  const teams = await api("GET", "/api/sports/teams");
  renderTeams(teams);
}

function renderTeams(teams) {
  const container = document.getElementById("teamList");
  container.innerHTML = teams.map(t => `
    <div class="team-item">
      <span>${t.name}</span>
      <span class="sport-badge">${t.sport}</span>
      <button class="team-remove" onclick="removeTeam(${t.id}, event)" title="Retirer">×</button>
    </div>
  `).join("") || '<div style="color:var(--gray);font-size:13px">Aucune équipe configurée</div>';
}

async function removeTeam(id, evt) {
  evt.stopPropagation();
  await api("DELETE", `/api/sports/teams/${id}`);
  loadTeams();
  loadUpcomingEvents();
  toast("Équipe retirée");
}

async function searchTeams() {
  const q = document.getElementById("teamSearchInput").value.trim();
  if (!q) return;
  const results = await api("GET", `/api/sports/search?q=${encodeURIComponent(q)}`);
  const container = document.getElementById("searchResults");
  if (!results || results.length === 0) {
    container.innerHTML = '<div style="color:var(--gray);font-size:13px;padding:8px">Aucun résultat</div>';
    return;
  }
  container.innerHTML = results.map(t => `
    <div class="search-result-item" onclick='addTeam(${JSON.stringify(JSON.stringify(t))})'>
      ${t.name}
      <span class="sport-badge">${t.sport}</span>
      <span style="color:var(--gray);font-size:11px;margin-left:auto">${t.country || ""}</span>
    </div>
  `).join("");
}

document.getElementById("teamSearchInput").addEventListener("keydown", e => {
  if (e.key === "Enter") searchTeams();
});

async function addTeam(jsonStr) {
  const t = JSON.parse(jsonStr);
  await api("POST", "/api/sports/teams", {
    name: t.name,
    sport: t.sport,
    external_id: t.external_id,
    badge_url: t.badge_url || "",
  });
  document.getElementById("teamSearchInput").value = "";
  document.getElementById("searchResults").innerHTML = "";
  loadTeams();
  loadUpcomingEvents();
  toast(`${t.name} ajouté !`);
}

// ── Settings ──────────────────────────────────────────────────────────────────
async function loadSettings() {
  const s = await api("GET", "/api/settings");
  const autoPublish = String(s.auto_publish).toLowerCase() === "true";
  state.requireValidation = !autoPublish;
  document.getElementById("requireValidation").checked = state.requireValidation;
  if (s.daily_story_time) {
    document.getElementById("dailyTime").value = s.daily_story_time;
  }
  // AI provider
  const provider = s.ai_provider || "gemini";
  highlightAiProvider(provider);
  document.getElementById("apiStatus").textContent =
    provider === "gemini" ? "GEMINI_API_KEY" : "ANTHROPIC_API_KEY";
}

function highlightAiProvider(provider) {
  document.getElementById("aiGemini").classList.toggle("active", provider === "gemini");
  document.getElementById("aiClaude").classList.toggle("active", provider === "claude");
}

async function setAiProvider(provider) {
  await api("PUT", "/api/settings", { ai_provider: provider });
  highlightAiProvider(provider);
  document.getElementById("apiStatus").textContent =
    provider === "gemini" ? "GEMINI_API_KEY" : "ANTHROPIC_API_KEY";
  toast(`Provider IA : ${provider === "gemini" ? "Gemini ✦" : "Claude ◆"}`);
}

function savePublishMode() {
  state.requireValidation = document.getElementById("requireValidation").checked;
  api("PUT", "/api/settings", { auto_publish: !state.requireValidation ? "true" : "false" });
  toast(state.requireValidation ? "Validation requise activée" : "Publication automatique activée");
}

function saveDailyTime() {
  const t = document.getElementById("dailyTime").value;
  api("PUT", "/api/settings", { daily_story_time: t });
  toast(`Post quotidien programmé à ${t}`);
}

// ── Platform toggles ──────────────────────────────────────────────────────────
function togglePlatform(platform) {
  const btn = document.getElementById(platform === "instagram" ? "pltInsta" : "pltFb");
  if (state.platforms.has(platform)) {
    if (state.platforms.size > 1) {
      state.platforms.delete(platform);
      btn.classList.remove("active");
    }
  } else {
    state.platforms.add(platform);
    btn.classList.add("active");
  }
}

// ── Generate ──────────────────────────────────────────────────────────────────
async function generate() {
  if (state.activeThemes.size === 0) {
    toast("Sélectionne au moins une thématique", "error");
    return;
  }
  const btn = document.getElementById("generateBtn");
  btn.innerHTML = '<div class="spinner"></div><span>Génération…</span>';
  btn.disabled = true;

  try {
    const post = await api("POST", "/api/generate", {
      themes: [...state.activeThemes],
      event_id: state.selectedEvent ? String(state.selectedEvent.id) : null,
      custom_context: document.getElementById("customContext").value.trim() || null,
      platforms: [...state.platforms],
    });
    state.generatedPosts.unshift(post);
    renderGeneratedPosts();

    if (!state.requireValidation) {
      await publishPost(post.id);
    }

    toast("Contenu généré ✨");
    updateQueueBadge();
  } catch (e) {
    toast("Erreur : " + e.message, "error");
  } finally {
    btn.innerHTML = '<span>✨ Générer</span>';
    btn.disabled = false;
  }
}

function renderGeneratedPosts() {
  const container = document.getElementById("generatedPosts");
  if (state.generatedPosts.length === 0) {
    container.innerHTML = "";
    return;
  }
  container.innerHTML = state.generatedPosts.map(p => renderPostCard(p, "generate")).join("");
}

// ── Post cards ────────────────────────────────────────────────────────────────
function renderPostCard(p, context = "queue") {
  const tags = Array.isArray(p.hashtags) ? p.hashtags.map(h => `#${h}`).join(" ") : "";
  const imgSrc = p.image_path ? `/${p.image_path}` : "";
  const eventLabel = p.sport_event ? `${p.sport_event.emoji || ""} ${p.sport_event.name}` : "";
  const date = p.created_at ? new Date(p.created_at).toLocaleDateString("fr-FR", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }) : "";

  const actions = buildActions(p, context);

  return `
    <div class="post-card" id="postcard-${p.id}">
      <div class="post-preview-large" onclick="openLightbox('${imgSrc}')">
        ${imgSrc ? `<img src="${imgSrc}" alt="Story preview" loading="lazy">` : '<div style="display:flex;align-items:center;justify-content:center;height:100%;color:var(--gray)">✨</div>'}
      </div>
      <div class="post-info">
        <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">
          <span class="post-status status-${p.status}">${statusLabel(p.status)}</span>
          ${eventLabel ? `<span class="post-event">${eventLabel}</span>` : ""}
          <span class="post-meta">${date}</span>
        </div>
        <div class="post-hook">${esc(p.hook || "")}</div>
        <div class="post-body">${esc(p.body || "")}</div>
        ${p.cta ? `<div style="color:var(--gold);font-size:13px;font-weight:500">${esc(p.cta)}</div>` : ""}
        <div class="post-hashtags">${tags}</div>
        <div class="post-actions">${actions}</div>
      </div>
    </div>
  `;
}

function buildActions(p, context) {
  const imgSrc = p.image_path ? `/${p.image_path}` : "";
  const edit = `<button class="btn btn-outline btn-sm" onclick="openEditModal(${p.id})">✏️ Modifier</button>`;
  const del = `<button class="btn btn-danger btn-sm" onclick="deletePost(${p.id})">🗑</button>`;

  if (p.status === "published") {
    return `
      <span style="color:var(--gold);font-size:13px;font-weight:600">✓ Partagé</span>
      <button class="btn btn-outline btn-sm" onclick="sharePost('${imgSrc}', ${p.id})">📤 Partager encore</button>
      ${edit} ${del}
    `;
  }

  return `
    <div style="display:flex;flex-direction:column;gap:12px;width:100%">
      <div style="display:flex;gap:10px;flex-wrap:wrap">
        <button class="btn btn-primary" onclick="sharePost('${imgSrc}', ${p.id})"
          style="font-size:15px;padding:12px 24px;flex:1;min-width:180px">
          📤 Partager sur Instagram / Facebook
        </button>
        <button class="btn btn-outline btn-sm" onclick="copyCaption(${p.id})" style="padding:12px 18px">
          📋 Copier la légende
        </button>
      </div>
      <div style="display:flex;gap:8px">${edit} ${del}</div>
    </div>
  `;
}

async function sharePost(imgSrc, postId) {
  // Copy caption to clipboard first
  const post = await api("GET", `/api/posts/${postId}`);
  const parts = [post.hook, post.body, post.cta];
  if (Array.isArray(post.hashtags)) parts.push(post.hashtags.map(h => `#${h}`).join(" "));
  const captionText = parts.filter(Boolean).join("\n\n");

  try { await navigator.clipboard.writeText(captionText); } catch {}

  // Try native share (works great on iPhone)
  if (navigator.share) {
    try {
      const response = await fetch(imgSrc);
      const blob = await response.blob();
      const file = new File([blob], `gabin-story-${postId}.png`, { type: "image/png" });

      if (navigator.canShare && navigator.canShare({ files: [file] })) {
        await navigator.share({ files: [file], title: "Gabin" });
        updatePostStatus(postId, "published");
        toast("Partagé ✓");
        return;
      }
    } catch (e) {
      if (e.name !== "AbortError") console.warn("Share failed:", e);
      else return; // User cancelled
    }
  }

  // Fallback: download image
  const a = document.createElement("a");
  a.href = imgSrc;
  a.download = `gabin-story-${postId}.png`;
  a.click();
  toast("Image téléchargée · Légende copiée dans le presse-papier 📋");
  updatePostStatus(postId, "published");
}

function updatePostStatus(postId, status) {
  api("PUT", `/api/posts/${postId}/approve`);
  const card = document.getElementById(`postcard-${postId}`);
  if (card) api("GET", `/api/posts/${postId}`).then(p => { card.outerHTML = renderPostCard({...p, status}, state.currentTab); });
}

async function copyCaption(postId) {
  const post = await api("GET", `/api/posts/${postId}`);
  const parts = [post.hook, post.body, post.cta];
  if (Array.isArray(post.hashtags)) parts.push(post.hashtags.map(h => `#${h}`).join(" "));
  const text = parts.filter(Boolean).join("\n\n");
  await navigator.clipboard.writeText(text);
  toast("Légende copiée 📋 — colle-la dans Instagram après avoir posté la photo");
}

async function downloadPost(imgSrc, postId) {
  const a = document.createElement("a");
  a.href = imgSrc;
  a.download = `gabin-story-${postId}.png`;
  a.click();
}

function statusLabel(s) {
  return { draft: "Brouillon", approved: "Approuvé", published: "Publié" }[s] || s;
}

function esc(str) {
  return String(str).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

// ── Tab management ────────────────────────────────────────────────────────────
function switchTab(tab) {
  state.currentTab = tab;
  document.querySelectorAll(".tab").forEach((el, i) => el.classList.remove("active"));
  const tabs = ["generate", "queue", "published", "planning", "library", "settings"];
  tabs.forEach((t, i) => {
    const el = document.querySelectorAll(".tab")[i];
    if (el) el.classList.toggle("active", t === tab);
    const panel = document.getElementById(`tab-${t}`);
    if (panel) panel.style.display = t === tab ? "" : "none";
  });
  loadTabContent(tab);
}

async function loadTabContent(tab) {
  if (tab === "queue") {
    const posts = await api("GET", "/api/posts?status=draft");
    const approved = await api("GET", "/api/posts?status=approved");
    const all = [...approved, ...posts];
    const container = document.getElementById("queuePosts");
    container.innerHTML = all.length
      ? all.map(p => renderPostCard(p, "queue")).join("")
      : emptyState("📋", "File vide", "Génère du contenu et approuve-le pour le retrouver ici.");
    updateQueueBadge(all.length);
  } else if (tab === "published") {
    const posts = await api("GET", "/api/posts?status=published");
    document.getElementById("publishedPosts").innerHTML = posts.length
      ? posts.map(p => renderPostCard(p, "published")).join("")
      : emptyState("🚀", "Aucun post publié", "Tes posts publiés apparaîtront ici.");
  } else if (tab === "planning") {
    loadPlanning();
  } else if (tab === "library") {
    loadLibrary();
  }
}

function emptyState(icon, title, desc) {
  return `<div class="empty-state"><div class="icon">${icon}</div><h3>${title}</h3><p>${desc}</p></div>`;
}

async function updateQueueBadge(count = null) {
  if (count === null) {
    const posts = await api("GET", "/api/posts?status=draft");
    const approved = await api("GET", "/api/posts?status=approved");
    count = posts.length + approved.length;
  }
  const badge = document.getElementById("queueBadge");
  badge.textContent = count;
  badge.style.display = count > 0 ? "" : "none";
}

// ── Post actions ──────────────────────────────────────────────────────────────
async function approvePost(id) {
  await api("PUT", `/api/posts/${id}/approve`);
  toast("Post approuvé ✅");
  refreshCard(id, { status: "approved" });
  updateQueueBadge();
}

async function publishPost(id) {
  try {
    await api("POST", `/api/publish/${id}`);
    toast("Publié 🚀");
    refreshCard(id, { status: "published" });
    updateQueueBadge();
  } catch (e) {
    toast("Erreur publication : " + e.message, "error");
  }
}

async function deletePost(id) {
  await api("DELETE", `/api/posts/${id}`);
  document.getElementById(`postcard-${id}`)?.remove();
  state.generatedPosts = state.generatedPosts.filter(p => p.id !== id);
  toast("Supprimé");
  updateQueueBadge();
}

function refreshCard(id, updates) {
  // Update in state
  const post = state.generatedPosts.find(p => p.id === id);
  if (post) Object.assign(post, updates);

  // Re-render card inline if visible
  const card = document.getElementById(`postcard-${id}`);
  if (!card) return;
  api("GET", `/api/posts/${id}`).then(p => {
    card.outerHTML = renderPostCard(p, state.currentTab);
  });
}

// ── Edit modal ────────────────────────────────────────────────────────────────
async function openEditModal(id) {
  const post = await api("GET", `/api/posts/${id}`);
  document.getElementById("editPostId").value = id;
  document.getElementById("editHook").value = post.hook || "";
  document.getElementById("editBody").value = post.body || "";
  document.getElementById("editCta").value = post.cta || "";
  document.getElementById("editHashtags").value = Array.isArray(post.hashtags)
    ? post.hashtags.join(" ") : "";
  document.getElementById("editModal").style.display = "flex";
}

function closeEditModal(evt) {
  if (!evt || evt.target.id === "editModal") {
    document.getElementById("editModal").style.display = "none";
  }
}

async function saveEdit() {
  const id = document.getElementById("editPostId").value;
  const hashInput = document.getElementById("editHashtags").value;
  const hashtags = hashInput.split(/[\s,]+/).map(h => h.replace(/^#/, "")).filter(Boolean);
  await api("PUT", `/api/posts/${id}`, {
    hook: document.getElementById("editHook").value,
    body: document.getElementById("editBody").value,
    cta: document.getElementById("editCta").value,
    hashtags,
  });
  document.getElementById("editModal").style.display = "none";
  refreshCard(Number(id), {});
  toast("Contenu mis à jour ✓");
}

// ── Planning ──────────────────────────────────────────────────────────────────

function initPlanningMonth() {
  const d = new Date();
  d.setMonth(d.getMonth() + 1);
  const val = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
  document.getElementById("planningMonth").value = val;
}

async function loadPlanning() {
  const month = document.getElementById("planningMonth").value;
  if (!month) return;
  const container = document.getElementById("planningList");
  container.innerHTML = `<div style="color:var(--gray);padding:20px">Chargement des événements…</div>`;

  const events = await api("GET", `/api/planning/${month}`);
  if (!events || events.length === 0) {
    container.innerHTML = emptyState("🏆", "Aucun événement trouvé", "Aucun match prévu pour tes équipes ce mois-ci. Ajoute des équipes dans la sidebar.");
    return;
  }

  // Group by sport
  const bySport = {};
  events.forEach(e => {
    const sport = e.event_data?.sport || "Autre";
    if (!bySport[sport]) bySport[sport] = [];
    bySport[sport].push(e);
  });

  container.innerHTML = Object.entries(bySport).map(([sport, evts]) => `
    <div style="margin-bottom:24px">
      <h3 style="font-size:13px;font-weight:600;color:var(--gold);text-transform:uppercase;letter-spacing:0.08em;margin-bottom:12px">
        ${evts[0].event_data?.emoji || "🏆"} ${sport}
      </h3>
      <div style="display:flex;flex-direction:column;gap:8px">
        ${evts.map(e => renderPlanningCard(e)).join("")}
      </div>
    </div>
  `).join("");
}

function renderPlanningCard(e) {
  const ev = e.event_data;
  const selected = e.selected === 1;
  return `
    <div id="plan-${e.event_id}" class="post-card" style="padding:14px;gap:14px;border-color:${selected ? "var(--gold)" : "var(--border)"}">
      <div style="flex:1">
        <div style="display:flex;align-items:center;gap:10px;margin-bottom:4px">
          <span style="font-size:14px;font-weight:600;color:var(--white)">${esc(ev.name)}</span>
        </div>
        <div style="font-size:12px;color:var(--gray)">${ev.league} · ${ev.date_display} ${ev.time_display ? "à " + ev.time_display : ""}</div>
        ${selected ? `<div style="font-size:12px;color:var(--gold);margin-top:4px">✓ Sélectionné pour communication</div>` : ""}
      </div>
      <div>
        <button class="btn ${selected ? "btn-outline" : "btn-primary"} btn-sm"
          onclick="togglePlanEvent('${e.event_id}', ${selected ? "false" : "true"})">
          ${selected ? "✓ Sélectionné" : "+ Sélectionner"}
        </button>
      </div>
    </div>
  `;
}

async function togglePlanEvent(eventId, selected) {
  await api("PUT", `/api/planning/${eventId}/select`, { selected, notes: "" });
  const month = document.getElementById("planningMonth").value;
  loadPlanning();
  toast(selected === true || selected === "true" ? "Événement ajouté au planning ✓" : "Événement retiré");
}

// ── Library ───────────────────────────────────────────────────────────────────
async function loadLibrary() {
  const images = await api("GET", "/api/library");
  const grid = document.getElementById("libraryGrid");
  grid.innerHTML = images.length
    ? images.map(img => `
        <div class="library-item">
          <img src="/${img.url}" alt="${img.filename}" loading="lazy"
               onclick="openLightbox('/${img.url}')">
          <button class="lib-del" onclick="deleteLibrary('${img.filename}', event)">×</button>
          <div class="lib-name">${img.filename}</div>
        </div>
      `).join("")
    : '<div style="color:var(--gray);font-size:14px">Aucune image dans la bibliothèque</div>';
}

async function uploadFiles(files) {
  const formData = new FormData();
  Array.from(files).forEach(f => formData.append("files", f));
  const res = await fetch("/api/library/upload", { method: "POST", body: formData });
  const data = await res.json();
  toast(`${data.uploaded.length} image(s) ajoutée(s) 📷`);
  loadLibrary();
}

async function deleteLibrary(filename, evt) {
  evt.stopPropagation();
  await api("DELETE", `/api/library/${filename}`);
  loadLibrary();
  toast("Image supprimée");
}

// Drag & drop on upload zone
const uploadZone = document.getElementById("uploadZone");
uploadZone.addEventListener("dragover", e => { e.preventDefault(); uploadZone.classList.add("drag-over"); });
uploadZone.addEventListener("dragleave", () => uploadZone.classList.remove("drag-over"));
uploadZone.addEventListener("drop", e => {
  e.preventDefault();
  uploadZone.classList.remove("drag-over");
  uploadFiles(e.dataTransfer.files);
});

// ── Lightbox ──────────────────────────────────────────────────────────────────
function openLightbox(src) {
  document.getElementById("lightboxImg").src = src;
  document.getElementById("lightbox").style.display = "flex";
}
function closeLightbox() {
  document.getElementById("lightbox").style.display = "none";
}
document.addEventListener("keydown", e => { if (e.key === "Escape") { closeLightbox(); closeEditModal(); } });

// ── Toasts ────────────────────────────────────────────────────────────────────
function toast(msg, type = "success") {
  const container = document.getElementById("toastContainer");
  const el = document.createElement("div");
  el.className = `toast ${type}`;
  el.textContent = msg;
  container.appendChild(el);
  setTimeout(() => el.remove(), 3000);
}
