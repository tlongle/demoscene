/**
 * PlayStation Demo Collector - Frontend Application
 * Clean PS1 Grey Theme, Real Box Art, Disc Scans & Collection Tracker
 */

const API_BASE = "";

// Application State
const state = {
  demos: [],
  total: 0,
  limit: 60,
  offset: 0,
  searchQuery: "",
  console: "ALL",
  section: "ALL",
  country: "ALL",
  status: "ALL",
  stats: null,
  activeDemo: null,
  activeVariantIndex: 0,
  debounceTimer: null,
  isLoading: false,
  isBulkMode: false,
  selectedIds: new Set()
};

// DOM Elements
const elements = {
  searchInput: document.getElementById("searchInput"),
  btnClearSearch: document.getElementById("btnClearSearch"),
  consolePills: document.getElementById("consolePills"),
  statusPills: document.getElementById("statusPills"),
  selectSection: document.getElementById("selectSection"),
  selectCountry: document.getElementById("selectCountry"),
  demoGrid: document.getElementById("demoGrid"),
  resultsCount: document.getElementById("resultsCount"),
  paginationContainer: document.getElementById("paginationContainer"),
  btnLoadMore: document.getElementById("btnLoadMore"),
  emptyState: document.getElementById("emptyState"),
  btnResetFilters: document.getElementById("btnResetFilters"),
  
  // Header Stats
  statTotalDemos: document.getElementById("statTotalDemos"),
  statOwnedDemos: document.getElementById("statOwnedDemos"),
  statWantedDemos: document.getElementById("statWantedDemos"),
  statCompletionRate: document.getElementById("statCompletionRate"),
  headerProgressFill: document.getElementById("headerProgressFill"),
  
  // Modals
  detailModal: document.getElementById("detailModal"),
  detailModalContent: document.getElementById("detailModalContent"),
  btnCloseDetail: document.getElementById("btnCloseDetail"),
  
  zoomModal: document.getElementById("zoomModal"),
  zoomImage: document.getElementById("zoomImage"),
  zoomCaption: document.getElementById("zoomCaption"),
  btnCloseZoom: document.getElementById("btnCloseZoom"),
  
  statsModal: document.getElementById("statsModal"),
  statsModalBody: document.getElementById("statsModalBody"),
  btnStats: document.getElementById("btnStats"),
  btnCloseStats: document.getElementById("btnCloseStats"),
  
  mobileModal: document.getElementById("mobileModal"),
  mobileUrlDisplay: document.getElementById("mobileUrlDisplay"),
  qrCodeImg: document.getElementById("qrCodeImg"),
  btnMobile: document.getElementById("btnMobile"),
  btnCloseMobile: document.getElementById("btnCloseMobile"),
  
  assetsModal: document.getElementById("assetsModal"),
  btnAssets: document.getElementById("btnAssets"),
  btnCloseAssets: document.getElementById("btnCloseAssets"),
  btnDownloadScans: document.getElementById("btnDownloadScans"),
  scansDownloadStatus: document.getElementById("scansDownloadStatus"),
  btnFetchBoxart: document.getElementById("btnFetchBoxart"),
  boxartFetchStatus: document.getElementById("boxartFetchStatus"),

  backupModal: document.getElementById("backupModal"),
  btnBackup: document.getElementById("btnBackup"),
  btnCloseBackup: document.getElementById("btnCloseBackup"),
  btnExportJson: document.getElementById("btnExportJson"),
  btnImportJson: document.getElementById("btnImportJson"),
  importFileInput: document.getElementById("importFileInput"),
  importStatus: document.getElementById("importStatus"),

  // Settings Modal
  btnSettings: document.getElementById("btnSettings"),
  settingsModal: document.getElementById("settingsModal"),
  btnCloseSettings: document.getElementById("btnCloseSettings"),
  txtTwitchClientId: document.getElementById("txtTwitchClientId"),
  txtTwitchClientSecret: document.getElementById("txtTwitchClientSecret"),
  btnSaveSettings: document.getElementById("btnSaveSettings"),
  igdbStatusBadge: document.getElementById("igdbStatusBadge"),
  settingsFeedback: document.getElementById("settingsFeedback"),

  // Collection & Bulk Edit Elements
  btnMyCollection: document.getElementById("btnMyCollection"),
  btnBulkEdit: document.getElementById("btnBulkEdit"),
  btnToggleBulk: document.getElementById("btnToggleBulk"),
  bulkActionBar: document.getElementById("bulkActionBar"),
  bulkSelectedCount: document.getElementById("bulkSelectedCount"),
  btnBulkSelectAll: document.getElementById("btnBulkSelectAll"),
  btnBulkDeselectAll: document.getElementById("btnBulkDeselectAll"),
  btnQuickDiscOnly: document.getElementById("btnQuickDiscOnly"),
  btnQuickOwned: document.getElementById("btnQuickOwned"),
  btnQuickWishlist: document.getElementById("btnQuickWishlist"),
  btnOpenBulkModal: document.getElementById("btnOpenBulkModal"),
  btnExitBulk: document.getElementById("btnExitBulk"),
  bulkEditModal: document.getElementById("bulkEditModal"),
  btnCloseBulkModal: document.getElementById("btnCloseBulkModal"),
  bulkModalHeader: document.getElementById("bulkModalHeader"),
  bulkStatusSelect: document.getElementById("bulkStatusSelect"),
  bulkConditionSelect: document.getElementById("bulkConditionSelect"),
  bulkChkSleeve: document.getElementById("bulkChkSleeve"),
  bulkChkCase: document.getElementById("bulkChkCase"),
  bulkChkWorking: document.getElementById("bulkChkWorking"),
  bulkTxtNotes: document.getElementById("bulkTxtNotes"),
  btnApplyBulkEdit: document.getElementById("btnApplyBulkEdit"),
  bulkModalFeedback: document.getElementById("bulkModalFeedback"),
  
  btnSync: document.getElementById("btnSync"),
  toast: document.getElementById("toast"),
  mobileNavItems: document.querySelectorAll(".dock-btn")
};

// ---------------------------------------------------------------------------
// Initialization & PWA
// ---------------------------------------------------------------------------
document.addEventListener("DOMContentLoaded", () => {
  registerServiceWorker();
  initEventListeners();
  loadFilterOptions();
  loadStats();
  fetchDemos(true);
});

function registerServiceWorker() {
  if ("serviceWorker" in navigator) {
    window.addEventListener("load", () => {
      navigator.serviceWorker.register("/sw.js").then(
        (reg) => console.log("[PWA] Service Worker active:", reg.scope),
        (err) => console.log("[PWA] Service Worker registration error:", err)
      );
    });
  }
}

function initEventListeners() {
  // Search
  elements.searchInput.addEventListener("input", (e) => {
    state.searchQuery = e.target.value;
    elements.btnClearSearch.style.display = state.searchQuery ? "block" : "none";
    clearTimeout(state.debounceTimer);
    state.debounceTimer = setTimeout(() => {
      fetchDemos(true);
    }, 200);
  });

  elements.btnClearSearch.addEventListener("click", () => {
    elements.searchInput.value = "";
    state.searchQuery = "";
    elements.btnClearSearch.style.display = "none";
    fetchDemos(true);
  });

  // Console Pills
  elements.consolePills.querySelectorAll(".btn-toggle").forEach(pill => {
    pill.addEventListener("click", () => {
      elements.consolePills.querySelectorAll(".btn-toggle").forEach(p => p.classList.remove("active"));
      pill.classList.add("active");
      state.console = pill.dataset.console;
      fetchDemos(true);
    });
  });

  // Status Pills
  elements.statusPills.querySelectorAll(".btn-toggle").forEach(pill => {
    pill.addEventListener("click", () => {
      setStatusFilter(pill.dataset.status);
    });
  });

  // Dropdown Selects
  elements.selectSection.addEventListener("change", (e) => {
    state.section = e.target.value;
    fetchDemos(true);
  });

  elements.selectCountry.addEventListener("change", (e) => {
    state.country = e.target.value;
    fetchDemos(true);
  });

  // Load More
  elements.btnLoadMore.addEventListener("click", () => {
    state.offset += state.limit;
    fetchDemos(false);
  });

  // Reset Filters
  elements.btnResetFilters.addEventListener("click", resetAllFilters);

  // Modals setup with null safety
  setupModalDismiss(elements.detailModal, elements.btnCloseDetail);
  setupModalDismiss(elements.zoomModal, elements.btnCloseZoom);
  setupModalDismiss(elements.statsModal, elements.btnCloseStats);
  setupModalDismiss(elements.mobileModal, elements.btnCloseMobile);
  setupModalDismiss(elements.assetsModal, elements.btnCloseAssets);
  setupModalDismiss(elements.backupModal, elements.btnCloseBackup);
  setupModalDismiss(elements.settingsModal, elements.btnCloseSettings);
  setupModalDismiss(elements.bulkEditModal, elements.btnCloseBulkModal);

  // My Collection & Bulk Edit header buttons
  if (elements.btnMyCollection) elements.btnMyCollection.addEventListener("click", () => setStatusFilter("owned"));
  if (elements.btnBulkEdit) elements.btnBulkEdit.addEventListener("click", toggleBulkMode);
  if (elements.btnToggleBulk) elements.btnToggleBulk.addEventListener("click", toggleBulkMode);
  if (elements.btnBulkSelectAll) elements.btnBulkSelectAll.addEventListener("click", bulkSelectAll);
  if (elements.btnBulkDeselectAll) elements.btnBulkDeselectAll.addEventListener("click", bulkDeselectAll);
  if (elements.btnExitBulk) elements.btnExitBulk.addEventListener("click", toggleBulkMode);

  // Quick bulk action buttons
  if (elements.btnQuickDiscOnly) {
    elements.btnQuickDiscOnly.addEventListener("click", () => {
      executeQuickBulkUpdate({ status: "owned", condition: "disc_only", has_sleeve: 0, has_case: 1, is_working: 1 });
    });
  }
  if (elements.btnQuickOwned) {
    elements.btnQuickOwned.addEventListener("click", () => {
      executeQuickBulkUpdate({ status: "owned" });
    });
  }
  if (elements.btnQuickWishlist) {
    elements.btnQuickWishlist.addEventListener("click", () => {
      executeQuickBulkUpdate({ status: "wanted" });
    });
  }

  // Custom Bulk Edit Modal
  if (elements.btnOpenBulkModal) elements.btnOpenBulkModal.addEventListener("click", openBulkEditModal);
  if (elements.btnApplyBulkEdit) elements.btnApplyBulkEdit.addEventListener("click", handleApplyBulkEditModal);

  // Header Modal Triggers (null-safe)
  if (elements.btnSettings) elements.btnSettings.addEventListener("click", openSettingsModal);
  if (elements.btnSaveSettings) elements.btnSaveSettings.addEventListener("click", handleSaveSettings);
  if (elements.btnStats) elements.btnStats.addEventListener("click", openStatsModal);
  if (elements.btnMobile) elements.btnMobile.addEventListener("click", openMobileModal);
  if (elements.btnAssets) elements.btnAssets.addEventListener("click", () => elements.assetsModal && elements.assetsModal.classList.add("active"));
  if (elements.btnBackup) elements.btnBackup.addEventListener("click", () => elements.backupModal && elements.backupModal.classList.add("active"));
  if (elements.btnSync) elements.btnSync.addEventListener("click", triggerSync);

  // Asset Downloads (null-safe)
  if (elements.btnDownloadScans) elements.btnDownloadScans.addEventListener("click", triggerDownloadAllScans);
  if (elements.btnFetchBoxart) elements.btnFetchBoxart.addEventListener("click", triggerFetchAllBoxart);

  // Backup & Restore (null-safe)
  if (elements.btnExportJson) elements.btnExportJson.addEventListener("click", exportCollection);
  if (elements.btnImportJson && elements.importFileInput) {
    elements.btnImportJson.addEventListener("click", () => elements.importFileInput.click());
    elements.importFileInput.addEventListener("change", handleImportFile);
  }

  // Mobile Bottom Dock
  if (elements.mobileNavItems) {
    elements.mobileNavItems.forEach(item => {
      item.addEventListener("click", () => {
        elements.mobileNavItems.forEach(i => i.classList.remove("active"));
        item.classList.add("active");
        const navTarget = item.dataset.nav;
        if (navTarget === "stats") {
          openStatsModal();
        } else {
          setStatusFilter(navTarget === "all" ? "ALL" : navTarget);
        }
      });
    });
  }
}

function setStatusFilter(status) {
  state.status = status;
  if (elements.statusPills) {
    elements.statusPills.querySelectorAll(".btn-toggle").forEach(p => {
      p.classList.toggle("active", p.dataset.status === status);
    });
  }
  if (elements.mobileNavItems) {
    elements.mobileNavItems.forEach(i => {
      if (i.dataset.nav !== "stats") {
        i.classList.toggle("active", (i.dataset.nav === "all" && status === "ALL") || i.dataset.nav === status);
      }
    });
  }
  fetchDemos(true);
}

function setupModalDismiss(modal, closeBtn) {
  if (!modal) return;
  if (closeBtn) {
    closeBtn.addEventListener("click", () => modal.classList.remove("active"));
  }
  modal.addEventListener("click", (e) => {
    if (e.target === modal) modal.classList.remove("active");
  });
}

// ---------------------------------------------------------------------------
// Data Fetching
// ---------------------------------------------------------------------------
async function fetchDemos(reset = false) {
  if (reset) {
    state.offset = 0;
    state.demos = [];
  }

  state.isLoading = true;
  elements.resultsCount.textContent = "Searching discs...";

  const params = new URLSearchParams({
    q: state.searchQuery,
    console: state.console,
    section: state.section,
    country: state.country,
    status: state.status,
    limit: state.limit,
    offset: state.offset
  });

  try {
    const res = await fetch(`${API_BASE}/api/demos?${params.toString()}`);
    const data = await res.json();

    state.total = data.total;
    if (reset) {
      state.demos = data.results;
    } else {
      state.demos = [...state.demos, ...data.results];
    }

    renderDemoGrid();
    updateResultsCount();
  } catch (err) {
    console.error("Error fetching demos:", err);
    showToast("⚠️ Could not load demos.");
  } finally {
    state.isLoading = false;
  }
}

async function loadStats() {
  try {
    const res = await fetch(`${API_BASE}/api/stats`);
    const data = await res.json();
    state.stats = data;

    elements.statTotalDemos.textContent = data.total_demos;
    elements.statOwnedDemos.textContent = data.owned_demos;
    elements.statWantedDemos.textContent = data.wanted_demos;
    elements.statCompletionRate.textContent = `${data.completion_rate}%`;
    elements.headerProgressFill.style.width = `${Math.min(data.completion_rate, 100)}%`;
  } catch (err) {
    console.error("Error loading stats:", err);
  }
}

async function loadFilterOptions() {
  try {
    const res = await fetch(`${API_BASE}/api/filters`);
    const data = await res.json();

    elements.selectSection.innerHTML = '<option value="ALL">All Series / Magazines</option>';
    data.sections.forEach(s => {
      const opt = document.createElement("option");
      opt.value = s.name;
      opt.textContent = `[${s.console}] ${s.name}`;
      elements.selectSection.appendChild(opt);
    });

    elements.selectCountry.innerHTML = '<option value="ALL">All Regions</option>';
    data.countries.forEach(c => {
      if (c) {
        const opt = document.createElement("option");
        opt.value = c;
        opt.textContent = c;
        elements.selectCountry.appendChild(opt);
      }
    });
  } catch (err) {
    console.error("Error loading filters:", err);
  }
}

// ---------------------------------------------------------------------------
// Rendering
// ---------------------------------------------------------------------------
function renderDemoGrid() {
  if (state.demos.length === 0) {
    elements.demoGrid.innerHTML = "";
    elements.emptyState.style.display = "block";
    elements.paginationContainer.style.display = "none";
    return;
  }

  elements.emptyState.style.display = "none";
  
  const cardsHtml = state.demos.map(demo => createDemoCardHtml(demo)).join("");
  elements.demoGrid.innerHTML = cardsHtml;

  elements.demoGrid.querySelectorAll(".ps-card").forEach(card => {
    const demoId = card.dataset.id;

    // Card click
    card.addEventListener("click", (e) => {
      if (e.target.closest(".btn-card-track")) return;
      if (e.target.closest(".card-select-chk") || e.target.closest(".card-select-wrap")) return;

      if (state.isBulkMode) {
        toggleSelectDemo(demoId, card);
      } else {
        openDetailModal(demoId);
      }
    });

    // Checkbox click in bulk mode
    const chk = card.querySelector(".card-select-chk");
    if (chk) {
      chk.addEventListener("change", (e) => {
        e.stopPropagation();
        toggleSelectDemo(demoId, card, chk.checked);
      });
    }

    // Quick track toggle button
    const toggleBtn = card.querySelector(".btn-card-track");
    if (toggleBtn) {
      toggleBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        cycleCollectionStatus(demoId, card);
      });
    }
  });

  elements.paginationContainer.style.display = state.demos.length < state.total ? "flex" : "none";
  updateBulkActionBar();
}

function createDemoCardHtml(demo) {
  const isOwned = demo.coll_status === "owned";
  const isWanted = demo.coll_status === "wanted";
  const isSelected = state.selectedIds.has(demo.id);

  let statusBadge = "";
  if (isOwned) {
    statusBadge = `<div class="card-status-tag owned">OWNED</div>`;
  } else if (isWanted) {
    statusBadge = `<div class="card-status-tag wanted">WANTED</div>`;
  }

  // Bulk Selection Checkbox
  let selectBoxHtml = "";
  if (state.isBulkMode) {
    selectBoxHtml = `
      <div class="card-select-wrap">
        <input type="checkbox" class="card-select-chk" data-id="${escapeHtml(demo.id)}" ${isSelected ? "checked" : ""} />
      </div>
    `;
  }

  // Condition and Checklist Badges
  let conditionBadges = "";
  if (isOwned) {
    const cond = demo.coll_condition || "good";
    const condLabels = {
      disc_only: "💿 Disc Only (Loose)",
      mint: "✨ Mint",
      good: "👍 Good",
      acceptable: "👌 Acceptable",
      poor: "⚠️ Poor"
    };
    conditionBadges += `<span class="card-cond-tag card-cond-${cond}">${condLabels[cond] || cond}</span> `;
    if (demo.coll_has_sleeve === 0 && cond !== "disc_only") {
      conditionBadges += `<span class="card-cond-tag" style="background:#fee2e2; border-color:#fca5a5; color:#991b1b;">No Sleeve</span> `;
    }
  }

  const thumbUrl = demo.primary_thumbnail || "/demopals/noimg.jpg";
  const fallbackSvg = createDiscPlaceholder(demo.console, demo.title);

  const flags = demo.variants.filter(v => v.flag_icon).map(v => 
    `<img class="flag-mini" src="${v.flag_icon}" alt="${v.country}" title="${v.country}" onerror="this.style.display='none'" />`
  ).slice(0, 4).join("");

  const scedText = demo.sced_codes && demo.sced_codes.length > 0 ? demo.sced_codes[0] : (demo.catalog_line || "");

  let toggleClass = "";
  let toggleText = "+ Track";
  if (isOwned) {
    toggleClass = "is-owned";
    toggleText = "🟢 Owned";
  } else if (isWanted) {
    toggleClass = "is-wanted";
    toggleText = "🟡 Wanted";
  }

  return `
    <div class="ps-card ${isSelected ? "is-selected" : ""}" data-id="${escapeHtml(demo.id)}">
      <div class="card-img-wrap">
        ${selectBoxHtml}
        <img class="card-img" src="${thumbUrl}" alt="${escapeHtml(demo.title)}" loading="lazy" onerror="this.src='${fallbackSvg}'" />
        <div class="card-tag-strip">
          <span class="tag-badge tag-${demo.console.toLowerCase()}">${demo.console}</span>
          <span class="tag-badge">${escapeHtml(demo.section_name)}</span>
        </div>
        ${statusBadge}
      </div>

      <div class="card-info">
        <div class="card-flags">${flags}</div>
        <div class="card-title">${escapeHtml(demo.title)}</div>
        <div class="card-sced">${escapeHtml(scedText)}</div>
        ${conditionBadges ? `<div class="mb-1" style="margin-top:2px;">${conditionBadges}</div>` : ""}

        <div class="card-footer">
          <div class="card-counts">
            ${demo.playable_count > 0 ? `<span>🎮 ${demo.playable_count}</span>` : ""}
            ${demo.trailer_count > 0 ? `<span>🎬 ${demo.trailer_count}</span>` : ""}
          </div>
          <button class="btn-card-track ${toggleClass}">${toggleText}</button>
        </div>
      </div>
    </div>
  `;
}

function updateResultsCount() {
  if (state.total === 0) {
    elements.resultsCount.textContent = "0 demo discs found";
  } else {
    elements.resultsCount.textContent = `Showing ${state.demos.length} of ${state.total} demo discs`;
  }
}

// ---------------------------------------------------------------------------
// Quick Status Cycle on Card
// ---------------------------------------------------------------------------
async function cycleCollectionStatus(demoId, cardElement) {
  const demo = state.demos.find(d => d.id === demoId);
  if (!demo) return;

  let newStatus = "owned";
  if (demo.coll_status === "owned") newStatus = "wanted";
  else if (demo.coll_status === "wanted") newStatus = "unowned";
  else newStatus = "owned";

  demo.coll_status = newStatus;

  const toggleBtn = cardElement.querySelector(".btn-card-track");
  toggleBtn.className = "btn-card-track";
  if (newStatus === "owned") {
    toggleBtn.classList.add("is-owned");
    toggleBtn.textContent = "🟢 Owned";
  } else if (newStatus === "wanted") {
    toggleBtn.classList.add("is-wanted");
    toggleBtn.textContent = "🟡 Wanted";
  } else {
    toggleBtn.textContent = "+ Track";
  }

  let statusIndicator = cardElement.querySelector(".card-status-tag");
  if (statusIndicator) statusIndicator.remove();
  
  if (newStatus === "owned") {
    cardElement.querySelector(".card-img-wrap").insertAdjacentHTML("beforeend", `<div class="card-status-tag owned">OWNED</div>`);
  } else if (newStatus === "wanted") {
    cardElement.querySelector(".card-img-wrap").insertAdjacentHTML("beforeend", `<div class="card-status-tag wanted">WANTED</div>`);
  }

  try {
    await fetch(`${API_BASE}/api/collection/${demoId}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ variant_id: "default", status: newStatus })
    });
    loadStats();
    showToast(newStatus === "owned" ? "Added to Owned collection" : (newStatus === "wanted" ? "Added to Wishlist" : "Removed from collection"));
  } catch (err) {
    console.error("Error updating collection status:", err);
  }
}

// ---------------------------------------------------------------------------
// Full Detail Modal
// ---------------------------------------------------------------------------
async function openDetailModal(demoId) {
  elements.detailModalContent.innerHTML = `<div class="text-center p-4">Loading details...</div>`;
  elements.detailModal.classList.add("active");

  try {
    const res = await fetch(`${API_BASE}/api/demos/${demoId}`);
    const demo = await res.json();
    state.activeDemo = demo;
    state.activeVariantIndex = 0;
    renderDetailModalContent(demo);
  } catch (err) {
    console.error("Error fetching detail:", err);
    elements.detailModalContent.innerHTML = `<div class="text-center text-red p-4">Failed to load demo details.</div>`;
  }
}

function renderDetailModalContent(demo) {
  const coll = demo.collection && demo.collection["default"] ? demo.collection["default"] : {
    status: demo.coll_status || "unowned",
    condition: "good",
    has_sleeve: 1,
    has_case: 1,
    is_working: 1,
    notes: ""
  };

  const scedCode = demo.sced_codes && demo.sced_codes.length > 0 ? demo.sced_codes.join(", ") : (demo.catalog_line || "N/A");

  // Variant selector tabs
  const variants = demo.variants || [];
  const variantTabsHtml = variants.length > 1 ? `
    <div class="variant-tabs-bar">
      ${variants.map((v, idx) => `
        <button class="var-tab-btn ${idx === state.activeVariantIndex ? 'active' : ''}" data-idx="${idx}">
          ${v.flag_icon ? `<img src="${v.flag_icon}" class="flag-mini" />` : ''}
          ${escapeHtml(v.country || `Edition ${idx+1}`)}
        </button>
      `).join("")}
    </div>
  ` : "";

  // Active Variant Scans & Artwork Filmstrip
  const activeVar = variants[state.activeVariantIndex] || {};
  const scansList = activeVar.scans || [];

  let scansHtml = "";
  if (scansList.length > 0) {
    scansHtml = `
      <div class="scans-row">
        ${scansList.map(s => `
          <div class="scan-card" data-src="${s.local_url || s.remote_url}" data-caption="${escapeHtml(s.label)}">
            <img class="scan-img" src="${s.local_url || s.remote_url}" alt="${escapeHtml(s.label)}" />
            <div class="scan-caption">${escapeHtml(s.label)}</div>
          </div>
        `).join("")}
      </div>
    `;
  } else {
    const previews = activeVar.scan_previews || [];
    const scanLabels = {
      0: "Slipcase / Cover Front",
      1: "Disc Scan / Inlay",
      2: "Slipcase / Cover Back",
      3: "Inlay / Booklet Scan",
      4: "Alternate Scan"
    };

    scansHtml = `
      <div class="scans-row">
        ${previews.map((url, i) => `
          <div class="scan-card" data-src="${url}" data-caption="${scanLabels[i] || `Scan #${i+1}`}">
            <img class="scan-img" src="${url}" alt="Scan #${i+1}" onerror="this.closest('.scan-card').style.display='none'" />
            <div class="scan-caption">${scanLabels[i] || `Scan #${i+1}`}</div>
          </div>
        `).join("")}
        ${activeVar.thumbnail ? `
          <div class="scan-card" data-src="${activeVar.thumbnail}" data-caption="Overview Thumbnail (Low-Res)">
            <img class="scan-img" src="${activeVar.thumbnail}" alt="Thumbnail" />
            <div class="scan-caption">Overview Thumbnail (Low-Res)</div>
          </div>
        ` : ""}
      </div>
    `;
  }

  // Categories with Box Art
  const enrichedCats = demo.enriched_categories || {};
  const categoriesHtml = Object.keys(enrichedCats).map(catName => {
    const games = enrichedCats[catName];
    const icon = catName.toLowerCase().includes("playable") ? "🎮" : (catName.toLowerCase().includes("trailer") ? "🎬" : "💾");

    return `
      <div class="scans-section">
        <div class="section-head">
          <span>${icon} ${escapeHtml(catName)} (${games.length})</span>
        </div>
        <div class="games-grid">
          ${games.map(g => createBoxartCardHtml(g)).join("")}
        </div>
      </div>
    `;
  }).join("");

  const notesHtml = demo.notes ? `
    <div class="notes-box">
      <strong>📜 Archival Notes:</strong> ${escapeHtml(demo.notes)}
    </div>
  ` : "";

  elements.detailModalContent.innerHTML = `
    <div class="detail-top">
      <h2 class="detail-heading">${escapeHtml(demo.title)}</h2>
      <div class="detail-meta-bar">
        <span class="tag-badge tag-${demo.console.toLowerCase()}">${demo.console}</span>
        <span class="tag-badge">${escapeHtml(demo.section_name)}</span>
        <span class="sced-pill">SCED: ${escapeHtml(scedCode)}</span>
        <a href="${demo.section_url}" target="_blank" rel="noopener" class="intel-link">
          🔗 Crimson Ceremony ↗
        </a>
      </div>
    </div>

    <!-- Collector Status Station -->
    <div class="collector-box">
      <div class="collector-box-title">Collection &amp; Physical Condition</div>
      
      <div class="status-btn-row">
        <button class="status-pick-btn ${coll.status === 'owned' ? 'selected-owned' : ''}" data-val="owned">🟢 Owned</button>
        <button class="status-pick-btn ${coll.status === 'wanted' ? 'selected-wanted' : ''}" data-val="wanted">🟡 Wishlist</button>
        <button class="status-pick-btn ${coll.status === 'unowned' ? 'selected-unowned' : ''}" data-val="unowned">⚪ Not Owned</button>
      </div>

      <div class="collector-options">
        <label class="collector-chk-label">
          <input type="checkbox" id="chkSleeve" ${coll.has_sleeve ? 'checked' : ''} />
          <span>Original Sleeve / Inlay</span>
        </label>
        <label class="collector-chk-label">
          <input type="checkbox" id="chkCase" ${coll.has_case ? 'checked' : ''} />
          <span>Jewel / DVD Case</span>
        </label>
        <label class="collector-chk-label">
          <input type="checkbox" id="chkWorking" ${coll.is_working ? 'checked' : ''} />
          <span>Tested &amp; Working</span>
        </label>
        <div>
          <select id="selCondition" class="ps-select" style="width: 100%;">
            <option value="mint" ${coll.condition === 'mint' ? 'selected' : ''}>Mint (Flawless)</option>
            <option value="good" ${coll.condition === 'good' ? 'selected' : ''}>Good (Minor scratches)</option>
            <option value="acceptable" ${coll.condition === 'acceptable' ? 'selected' : ''}>Acceptable (Plays fine)</option>
            <option value="poor" ${coll.condition === 'poor' ? 'selected' : ''}>Poor (Heavy marks)</option>
            <option value="disc_only" ${coll.condition === 'disc_only' ? 'selected' : ''}>Disc Only (Loose)</option>
          </select>
        </div>
      </div>

      <textarea id="txtCollectorNotes" class="collector-notes-area mt-1" placeholder="Collector notes (e.g. boot sale find, missing slipcase)...">${escapeHtml(coll.notes || "")}</textarea>
    </div>

    <!-- Scans & Slipcases -->
    <div class="scans-section">
      <div class="section-head">
        <span>Disc Scans &amp; Slipcase Art</span>
        <span class="text-sm text-muted">${escapeHtml(activeVar.disc_title || "")}</span>
      </div>
      ${variantTabsHtml}
      ${scansHtml}
    </div>

    ${notesHtml}

    <!-- Content Showcase with Box Art -->
    <div>
      ${categoriesHtml || `<p class="text-muted">No game items listed.</p>`}
    </div>
  `;

  attachDetailModalListeners(demo);
}

function createBoxartCardHtml(game) {
  let boxartHtml = "";
  if (game.boxart_url) {
    boxartHtml = `<img class="boxart-img" src="${game.boxart_url}" alt="${escapeHtml(game.name)}" loading="lazy" />`;
  } else {
    boxartHtml = `
      <div class="boxart-badge" style="background: ${game.palette.bg}; border: 1px solid ${game.palette.accent};">
        <div class="boxart-badge-console">${game.console}</div>
        <div class="boxart-badge-init">${escapeHtml(game.initials)}</div>
        <div class="boxart-badge-genre">${escapeHtml(game.genre)}</div>
      </div>
    `;
  }

  return `
    <div class="game-card">
      <div class="boxart-wrap">
        ${boxartHtml}
      </div>

      <div class="game-meta">
        <div>
          <div class="game-title">${escapeHtml(game.name)}</div>
          <div class="game-genre">${escapeHtml(game.genre)}</div>
        </div>

        <div class="game-links">
          <a href="${game.links.youtube}" target="_blank" rel="noopener" class="intel-link">▶ YouTube</a>
          <a href="${game.links.mobygames}" target="_blank" rel="noopener" class="intel-link">🌐 MobyGames</a>
          <a href="${game.links.wikipedia}" target="_blank" rel="noopener" class="intel-link">📖 Wiki</a>
        </div>
      </div>
    </div>
  `;
}

function attachDetailModalListeners(demo) {
  elements.detailModalContent.querySelectorAll(".status-pick-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      elements.detailModalContent.querySelectorAll(".status-pick-btn").forEach(b => {
        b.className = "status-pick-btn";
      });
      const val = btn.dataset.val;
      if (val === "owned") btn.classList.add("selected-owned");
      else if (val === "wanted") btn.classList.add("selected-wanted");
      else btn.classList.add("selected-unowned");

      saveCurrentModalCollectionState(demo.id);
    });
  });

  const chkSleeve = document.getElementById("chkSleeve");
  const chkCase = document.getElementById("chkCase");
  const chkWorking = document.getElementById("chkWorking");
  const selCondition = document.getElementById("selCondition");
  const txtNotes = document.getElementById("txtCollectorNotes");

  [chkSleeve, chkCase, chkWorking, selCondition].forEach(el => {
    if (el) el.addEventListener("change", () => saveCurrentModalCollectionState(demo.id));
  });

  if (txtNotes) {
    txtNotes.addEventListener("input", () => {
      clearTimeout(state.notesSaveTimer);
      state.notesSaveTimer = setTimeout(() => {
        saveCurrentModalCollectionState(demo.id);
      }, 500);
    });
  }

  elements.detailModalContent.querySelectorAll(".var-tab-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      state.activeVariantIndex = parseInt(btn.dataset.idx, 10);
      renderDetailModalContent(demo);
    });
  });

  elements.detailModalContent.querySelectorAll(".scan-card").forEach(card => {
    card.addEventListener("click", () => {
      const src = card.dataset.src;
      const caption = card.dataset.caption;
      openZoomModal(src, caption);
    });
  });
}

async function saveCurrentModalCollectionState(demoId) {
  const selectedBtn = elements.detailModalContent.querySelector(".status-pick-btn[class*='selected-']");
  const status = selectedBtn ? selectedBtn.dataset.val : "unowned";
  
  const chkSleeve = document.getElementById("chkSleeve");
  const chkCase = document.getElementById("chkCase");
  const chkWorking = document.getElementById("chkWorking");
  const selCondition = document.getElementById("selCondition");
  const txtNotes = document.getElementById("txtCollectorNotes");

  const payload = {
    variant_id: "default",
    status: status,
    condition: selCondition ? selCondition.value : "good",
    has_sleeve: chkSleeve && chkSleeve.checked ? 1 : 0,
    has_case: chkCase && chkCase.checked ? 1 : 0,
    is_working: chkWorking && chkWorking.checked ? 1 : 0,
    notes: txtNotes ? txtNotes.value : ""
  };

  try {
    await fetch(`${API_BASE}/api/collection/${demoId}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });

    const d = state.demos.find(item => item.id === demoId);
    if (d) {
      d.coll_status = status;
      d.coll_condition = payload.condition;
      d.coll_notes = payload.notes;
      const card = elements.demoGrid.querySelector(`.ps-card[data-id="${demoId}"]`);
      if (card) {
        const toggleBtn = card.querySelector(".btn-card-track");
        if (toggleBtn) {
          toggleBtn.className = `btn-card-track ${status === 'owned' ? 'is-owned' : (status === 'wanted' ? 'is-wanted' : '')}`;
          toggleBtn.textContent = status === "owned" ? "🟢 Owned" : (status === "wanted" ? "🟡 Wanted" : "+ Track");
        }
      }
    }
    loadStats();
  } catch (err) {
    console.error("Error saving collection state:", err);
  }
}

// ---------------------------------------------------------------------------
// Image Zoom Modal
// ---------------------------------------------------------------------------
function openZoomModal(src, caption) {
  elements.zoomImage.src = src;
  elements.zoomCaption.textContent = caption || "";
  elements.zoomModal.classList.add("active");
}

// ---------------------------------------------------------------------------
// Stats & Breakdown Modal
// ---------------------------------------------------------------------------
function openStatsModal() {
  if (!state.stats) {
    elements.statsModalBody.innerHTML = `<p class="text-center p-4">Loading stats...</p>`;
  } else {
    const s = state.stats;
    const seriesRows = s.series_breakdown.map(sb => {
      const pct = sb.total ? Math.round((sb.owned / sb.total) * 100) : 0;
      return `
        <div class="mb-2">
          <div style="display: flex; justify-content: space-between; font-size: 12px; margin-bottom: 2px;">
            <span>[${sb.console}] <strong>${escapeHtml(sb.section_name)}</strong></span>
            <span>${sb.owned} / ${sb.total} (${pct}%)</span>
          </div>
          <div class="stat-meter" style="height: 6px;">
            <div class="stat-meter-fill" style="width: ${pct}%;"></div>
          </div>
        </div>
      `;
    }).join("");

    elements.statsModalBody.innerHTML = `
      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 12px;">
        <div class="section-box text-center">
          <div class="text-muted text-sm">OWNED</div>
          <div class="txt-green" style="font-size: 22px; font-weight: 700;">${s.owned_demos}</div>
        </div>
        <div class="section-box text-center">
          <div class="text-muted text-sm">WISHLIST</div>
          <div class="txt-amber" style="font-size: 22px; font-weight: 700;">${s.wanted_demos}</div>
        </div>
      </div>

      <div class="section-box">
        <h4 style="margin-bottom: 8px;">Series Completion</h4>
        ${seriesRows}
      </div>
    `;
  }
  elements.statsModal.classList.add("active");
}

// ---------------------------------------------------------------------------
// Mobile Pairing Modal
// ---------------------------------------------------------------------------
async function openMobileModal() {
  if (!elements.mobileModal) return;
  try {
    const res = await fetch(`${API_BASE}/api/network-info`);
    const data = await res.json();
    if (elements.mobileUrlDisplay) elements.mobileUrlDisplay.textContent = data.mobile_url;
    if (elements.qrCodeImg) {
      const qrUrl = `https://api.qrserver.com/v1/create-qr-code/?size=180x180&data=${encodeURIComponent(data.mobile_url)}&color=2a2a2a&bgcolor=ebebeb`;
      elements.qrCodeImg.src = qrUrl;
      elements.qrCodeImg.style.display = "block";
    }
  } catch (err) {
    if (elements.mobileUrlDisplay) elements.mobileUrlDisplay.textContent = window.location.href;
  }
}

// ---------------------------------------------------------------------------
// Settings Modal (IGDB Integration)
// ---------------------------------------------------------------------------
async function openSettingsModal() {
  if (!elements.settingsModal) return;
  if (elements.settingsFeedback) elements.settingsFeedback.innerHTML = "";
  if (elements.igdbStatusBadge) {
    elements.igdbStatusBadge.innerHTML = `<span class="text-muted">Checking IGDB connection...</span>`;
  }
  elements.settingsModal.classList.add("active");

  try {
    const res = await fetch(`${API_BASE}/api/settings`);
    const data = await res.json();
    if (elements.igdbStatusBadge) {
      if (data.configured) {
        elements.igdbStatusBadge.innerHTML = `<span class="txt-green">🟢 IGDB Connected</span> (Client ID: ${data.client_id_masked || "Configured"})`;
      } else {
        elements.igdbStatusBadge.innerHTML = `<span class="txt-amber">⚪ IGDB Not Configured</span> (Using clean placeholder badges)`;
      }
    }
  } catch (err) {
    if (elements.igdbStatusBadge) {
      elements.igdbStatusBadge.innerHTML = `<span class="text-muted">Could not query settings status.</span>`;
    }
  }
}

async function handleSaveSettings() {
  const clientId = elements.txtTwitchClientId ? elements.txtTwitchClientId.value.trim() : "";
  const clientSecret = elements.txtTwitchClientSecret ? elements.txtTwitchClientSecret.value.trim() : "";

  if (!clientId || !clientSecret) {
    if (elements.settingsFeedback) {
      elements.settingsFeedback.innerHTML = `<span class="text-red">Please enter both Client ID and Client Secret.</span>`;
    }
    return;
  }

  if (elements.btnSaveSettings) elements.btnSaveSettings.disabled = true;
  if (elements.settingsFeedback) {
    elements.settingsFeedback.innerHTML = `<span class="text-muted">Verifying credentials with Twitch OAuth...</span>`;
  }

  try {
    const res = await fetch(`${API_BASE}/api/settings`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        twitch_client_id: clientId,
        twitch_client_secret: clientSecret
      })
    });

    const data = await res.json();
    if (res.ok && data.success) {
      if (elements.settingsFeedback) {
        elements.settingsFeedback.innerHTML = `<span class="txt-green">✅ ${data.message}</span>`;
      }
      if (elements.igdbStatusBadge) {
        elements.igdbStatusBadge.innerHTML = `<span class="txt-green">🟢 IGDB Connected &amp; Saved</span>`;
      }
      if (elements.txtTwitchClientSecret) elements.txtTwitchClientSecret.value = "";
      showToast("✅ IGDB credentials verified and saved!");
    } else {
      if (elements.settingsFeedback) {
        elements.settingsFeedback.innerHTML = `<span class="text-red">❌ ${data.detail || "Failed to verify credentials."}</span>`;
      }
    }
  } catch (err) {
    if (elements.settingsFeedback) {
      elements.settingsFeedback.innerHTML = `<span class="text-red">❌ Connection error.</span>`;
    }
  } finally {
    if (elements.btnSaveSettings) elements.btnSaveSettings.disabled = false;
  }
}

// ---------------------------------------------------------------------------
// Bulk Collection Editing
// ---------------------------------------------------------------------------
function toggleBulkMode() {
  state.isBulkMode = !state.isBulkMode;
  if (!state.isBulkMode) {
    state.selectedIds.clear();
  }
  if (elements.btnToggleBulk) {
    elements.btnToggleBulk.textContent = state.isBulkMode ? "✓ Done Selecting" : "✏️ Bulk Edit Mode";
  }
  renderDemoGrid();
  updateBulkActionBar();
}

function toggleSelectDemo(demoId, cardElement, forcedState = null) {
  const isSelected = forcedState !== null ? forcedState : !state.selectedIds.has(demoId);
  if (isSelected) {
    state.selectedIds.add(demoId);
    if (cardElement) cardElement.classList.add("is-selected");
  } else {
    state.selectedIds.delete(demoId);
    if (cardElement) cardElement.classList.remove("is-selected");
  }
  const chk = cardElement ? cardElement.querySelector(".card-select-chk") : null;
  if (chk) chk.checked = isSelected;
  updateBulkActionBar();
}

function bulkSelectAll() {
  state.demos.forEach(d => state.selectedIds.add(d.id));
  renderDemoGrid();
  updateBulkActionBar();
}

function bulkDeselectAll() {
  state.selectedIds.clear();
  renderDemoGrid();
  updateBulkActionBar();
}

function updateBulkActionBar() {
  if (!elements.bulkActionBar) return;
  if (state.isBulkMode) {
    elements.bulkActionBar.style.display = "flex";
    if (elements.bulkSelectedCount) {
      elements.bulkSelectedCount.textContent = `${state.selectedIds.size} Discs Selected`;
    }
  } else {
    elements.bulkActionBar.style.display = "none";
  }
}

async function executeQuickBulkUpdate(updates) {
  if (state.selectedIds.size === 0) {
    showToast("⚠️ Select at least one demo disc first.");
    return;
  }

  const ids = Array.from(state.selectedIds);
  try {
    const res = await fetch(`${API_BASE}/api/collection/bulk`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        demo_ids: ids,
        ...updates
      })
    });

    const data = await res.json();
    if (res.ok && data.success) {
      showToast(`✅ Updated ${data.updated_count} discs in collection!`);
      state.selectedIds.clear();
      await loadStats();
      await fetchDemos(false);
    } else {
      showToast(`❌ Error: ${data.detail || "Failed to update"}`);
    }
  } catch (err) {
    showToast("❌ Network error during bulk update");
  }
}

function openBulkEditModal() {
  if (state.selectedIds.size === 0) {
    showToast("⚠️ Select at least one demo disc first.");
    return;
  }
  if (elements.bulkModalHeader) {
    elements.bulkModalHeader.textContent = `Batch Edit (${state.selectedIds.size} Discs Selected)`;
  }
  if (elements.bulkModalFeedback) {
    elements.bulkModalFeedback.innerHTML = "";
  }
  if (elements.bulkEditModal) {
    elements.bulkEditModal.classList.add("active");
  }
}

async function handleApplyBulkEditModal() {
  if (state.selectedIds.size === 0) {
    if (elements.bulkModalFeedback) {
      elements.bulkModalFeedback.innerHTML = `<span class="text-red">No discs selected.</span>`;
    }
    return;
  }

  const ids = Array.from(state.selectedIds);
  const statusVal = elements.bulkStatusSelect ? elements.bulkStatusSelect.value : "keep";
  const condVal = elements.bulkConditionSelect ? elements.bulkConditionSelect.value : "keep";
  const hasSleeve = elements.bulkChkSleeve ? (elements.bulkChkSleeve.checked ? 1 : 0) : 0;
  const hasCase = elements.bulkChkCase ? (elements.bulkChkCase.checked ? 1 : 0) : 1;
  const isWorking = elements.bulkChkWorking ? (elements.bulkChkWorking.checked ? 1 : 0) : 1;
  const notesVal = elements.bulkTxtNotes ? elements.bulkTxtNotes.value.trim() : "";

  const payload = { demo_ids: ids };
  if (statusVal !== "keep") payload.status = statusVal;
  if (condVal !== "keep") payload.condition = condVal;
  payload.has_sleeve = hasSleeve;
  payload.has_case = hasCase;
  payload.is_working = isWorking;
  if (notesVal) payload.notes = notesVal;

  if (elements.btnApplyBulkEdit) elements.btnApplyBulkEdit.disabled = true;
  if (elements.bulkModalFeedback) {
    elements.bulkModalFeedback.innerHTML = `<span class="text-muted">Applying updates to ${ids.length} discs...</span>`;
  }

  try {
    const res = await fetch(`${API_BASE}/api/collection/bulk`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });

    const data = await res.json();
    if (res.ok && data.success) {
      if (elements.bulkModalFeedback) {
        elements.bulkModalFeedback.innerHTML = `<span class="txt-green">✅ Successfully updated ${data.updated_count} discs!</span>`;
      }
      showToast(`✅ Updated ${data.updated_count} discs!`);
      setTimeout(() => {
        if (elements.bulkEditModal) elements.bulkEditModal.classList.remove("active");
        state.selectedIds.clear();
        loadStats();
        fetchDemos(false);
      }, 700);
    } else {
      if (elements.bulkModalFeedback) {
        elements.bulkModalFeedback.innerHTML = `<span class="text-red">❌ ${data.detail || "Error applying updates"}</span>`;
      }
    }
  } catch (err) {
    if (elements.bulkModalFeedback) {
      elements.bulkModalFeedback.innerHTML = `<span class="text-red">❌ Network error</span>`;
    }
  } finally {
    if (elements.btnApplyBulkEdit) elements.btnApplyBulkEdit.disabled = false;
  }
}

// ---------------------------------------------------------------------------
// Asset Downloads
// ---------------------------------------------------------------------------
async function triggerDownloadAllScans() {
  elements.btnDownloadScans.disabled = true;
  elements.scansDownloadStatus.innerHTML = `<span class="text-muted">⏳ Downloading scans in background...</span>`;
  try {
    await fetch(`${API_BASE}/api/assets/download-all`, { method: "POST" });
    showToast("Offline scans download started in background");
  } catch (err) {
    elements.scansDownloadStatus.innerHTML = `<span class="text-red">❌ Failed to start download.</span>`;
  }
}

async function triggerFetchAllBoxart() {
  elements.btnFetchBoxart.disabled = true;
  elements.boxartFetchStatus.innerHTML = `<span class="text-muted">⏳ Fetching PAL box art in background...</span>`;
  try {
    await fetch(`${API_BASE}/api/boxart/fetch-all`, { method: "POST" });
    showToast("Box art download started");
  } catch (err) {
    elements.boxartFetchStatus.innerHTML = `<span class="text-red">❌ Failed to start box art fetch.</span>`;
  }
}

// ---------------------------------------------------------------------------
// Backup & Restore
// ---------------------------------------------------------------------------
async function exportCollection() {
  try {
    const res = await fetch(`${API_BASE}/api/export`);
    const data = await res.json();
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `ps-demo-collection-backup-${new Date().toISOString().slice(0, 10)}.json`;
    a.click();
    URL.revokeObjectURL(url);
    showToast("💾 Backup downloaded!");
  } catch (err) {
    showToast("❌ Export failed.");
  }
}

async function handleImportFile(e) {
  const file = e.target.files[0];
  if (!file) return;

  const reader = new FileReader();
  reader.onload = async (event) => {
    try {
      const json = JSON.parse(event.target.result);
      const res = await fetch(`${API_BASE}/api/import`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(json)
      });
      const resData = await res.json();
      elements.importStatus.innerHTML = `<span class="txt-green">✅ Restored ${resData.imported_records} records!</span>`;
      loadStats();
      fetchDemos(true);
      showToast(`Restored ${resData.imported_records} records`);
    } catch (err) {
      elements.importStatus.innerHTML = `<span class="text-red">❌ Invalid JSON file.</span>`;
    }
  };
  reader.readAsText(file);
}

// ---------------------------------------------------------------------------
// Sync / Re-scrape
// ---------------------------------------------------------------------------
async function triggerSync() {
  elements.btnSync.disabled = true;
  elements.btnSync.textContent = "Syncing...";
  try {
    await fetch(`${API_BASE}/api/scrape`, { method: "POST" });
    showToast("Archive sync started");
    setTimeout(() => {
      elements.btnSync.disabled = false;
      elements.btnSync.textContent = "🔄 Sync";
      loadStats();
      fetchDemos(true);
    }, 4000);
  } catch (err) {
    elements.btnSync.disabled = false;
    elements.btnSync.textContent = "🔄 Sync";
    showToast("❌ Sync failed.");
  }
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function resetAllFilters() {
  state.searchQuery = "";
  elements.searchInput.value = "";
  elements.btnClearSearch.style.display = "none";
  state.console = "ALL";
  elements.consolePills.querySelectorAll(".btn-toggle").forEach(p => p.classList.toggle("active", p.dataset.console === "ALL"));
  state.status = "ALL";
  elements.statusPills.querySelectorAll(".btn-toggle").forEach(p => p.classList.toggle("active", p.dataset.status === "ALL"));
  state.section = "ALL";
  elements.selectSection.value = "ALL";
  state.country = "ALL";
  elements.selectCountry.value = "ALL";
  fetchDemos(true);
}

function showToast(message) {
  elements.toast.textContent = message;
  elements.toast.classList.add("show");
  clearTimeout(state.toastTimer);
  state.toastTimer = setTimeout(() => {
    elements.toast.classList.remove("show");
  }, 2500);
}

function escapeHtml(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function createDiscPlaceholder(consoleType, title) {
  const isPs1 = consoleType === "PS1";
  const bg = isPs1 ? "#555" : "#00439c";
  return `data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="300" height="200" viewBox="0 0 300 200"><rect width="300" height="200" fill="%23222222"/><circle cx="150" cy="100" r="70" fill="${encodeURIComponent(bg)}" stroke="%23888888" stroke-width="2"/><circle cx="150" cy="100" r="22" fill="%23222222" stroke="%23888888" stroke-width="2"/><text x="150" y="105" fill="%23ffffff" font-family="sans-serif" font-weight="bold" font-size="14" text-anchor="middle">${encodeURIComponent(consoleType)}</text></svg>`;
}
