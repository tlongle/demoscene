/**
 * DEMOSCENE - PlayStation Demo Collector & Collection Manager
 * Dedicated Views: Archive Explorer, PriceCharting Collection Manager, Settings Hub
 */

const API_BASE = "";

// Application State
const state = {
  currentPage: "archive", // 'archive', 'collection', 'settings'

  archive: {
    demos: [],
    total: 0,
    offset: 0,
    limit: 60,
    query: "",
    console: "ALL",
    section: "ALL",
    country: "ALL",
    layout: localStorage.getItem("demoscene_archive_layout") || localStorage.getItem("scene_archive_layout") || "grid",
    isLoading: false,
    debounceTimer: null
  },

  collection: {
    demos: [],
    total: 0,
    query: "",
    console: "ALL",
    condition: "ALL",
    checklist: "ALL",
    layout: localStorage.getItem("demoscene_collection_layout") || localStorage.getItem("scene_collection_layout") || "list",
    isBulkMode: false,
    selectedIds: new Set(),
    isLoading: false,
    debounceTimer: null
  },

  collectionGames: [],
  filteredGames: [],

  stats: null,
  activeDemo: null,
  activeVariantIndex: 0,
  editingDemoId: null
};

// DOM Elements
const elements = {
  // Navigation Tabs
  mainNavTabs: document.getElementById("mainNavTabs"),
  navTabArchive: document.getElementById("navTabArchive"),
  navTabCollection: document.getElementById("navTabCollection"),
  navTabSettings: document.getElementById("navTabSettings"),
  navCountArchive: document.getElementById("navCountArchive"),
  navCountOwned: document.getElementById("navCountOwned"),

  // Pages
  pageArchive: document.getElementById("pageArchive"),
  pageCollection: document.getElementById("pageCollection"),
  pageSettings: document.getElementById("pageSettings"),

  // --- Archive Page Elements ---
  archiveSearchInput: document.getElementById("archiveSearchInput"),
  btnArchiveClearSearch: document.getElementById("btnArchiveClearSearch"),
  archiveConsolePills: document.getElementById("archiveConsolePills"),
  archiveSelectSection: document.getElementById("archiveSelectSection"),
  archiveSelectCountry: document.getElementById("archiveSelectCountry"),
  archiveResultsCount: document.getElementById("archiveResultsCount"),
  btnArchiveViewGrid: document.getElementById("btnArchiveViewGrid"),
  btnArchiveViewList: document.getElementById("btnArchiveViewList"),
  archiveContainer: document.getElementById("archiveContainer"),
  archivePagination: document.getElementById("archivePagination"),
  btnArchiveLoadMore: document.getElementById("btnArchiveLoadMore"),
  archiveEmptyState: document.getElementById("archiveEmptyState"),
  btnArchiveResetFilters: document.getElementById("btnArchiveResetFilters"),

  // --- Collection Page Elements ---
  btnToggleMobileStats: document.getElementById("btnToggleMobileStats"),
  collectionSideCard: document.getElementById("collectionSideCard"),
  colStatOwnedCount: document.getElementById("colStatOwnedCount"),
  colStatTotalDemos: document.getElementById("colStatTotalDemos"),
  colStatCompletionRate: document.getElementById("colStatCompletionRate"),
  colStatBarTotal: document.getElementById("colStatBarTotal"),
  colStatPs1Summary: document.getElementById("colStatPs1Summary"),
  colStatBarPs1: document.getElementById("colStatBarPs1"),
  colStatPs2Summary: document.getElementById("colStatPs2Summary"),
  colStatBarPs2: document.getElementById("colStatBarPs2"),
  colStatCondDiscOnly: document.getElementById("colStatCondDiscOnly"),
  colStatBarDiscOnly: document.getElementById("colStatBarDiscOnly"),
  colStatCondMint: document.getElementById("colStatCondMint"),
  colStatBarMint: document.getElementById("colStatBarMint"),
  colStatCondGood: document.getElementById("colStatCondGood"),
  colStatBarGood: document.getElementById("colStatBarGood"),
  colStatWithSleeve: document.getElementById("colStatWithSleeve"),
  colStatBarWithSleeve: document.getElementById("colStatBarWithSleeve"),
  colStatInCase: document.getElementById("colStatInCase"),
  colStatBarInCase: document.getElementById("colStatBarInCase"),
  colStatWorking: document.getElementById("colStatWorking"),
  colStatBarWorking: document.getElementById("colStatBarWorking"),
  colStatSeriesBreakdown: document.getElementById("colStatSeriesBreakdown"),

  // Games in Collection Widget Elements
  colUniqueGamesCount: document.getElementById("colUniqueGamesCount"),
  colGameSearchInput: document.getElementById("colGameSearchInput"),
  btnColGameClearSearch: document.getElementById("btnColGameClearSearch"),
  collectionGamesList: document.getElementById("collectionGamesList"),

  colSearchInput: document.getElementById("colSearchInput"),
  btnColClearSearch: document.getElementById("btnColClearSearch"),
  colConsolePills: document.getElementById("colConsolePills"),
  colSelectCondition: document.getElementById("colSelectCondition"),
  colSelectChecklist: document.getElementById("colSelectChecklist"),
  btnColViewCards: document.getElementById("btnColViewCards"),
  btnColViewList: document.getElementById("btnColViewList"),
  btnColToggleBulk: document.getElementById("btnColToggleBulk"),
  collectionContainer: document.getElementById("collectionContainer"),
  colEmptyState: document.getElementById("colEmptyState"),
  btnColGoToArchive: document.getElementById("btnColGoToArchive"),

  // Bulk Edit Elements
  bulkActionBar: document.getElementById("bulkActionBar"),
  bulkSelectedCount: document.getElementById("bulkSelectedCount"),
  btnBulkSelectAll: document.getElementById("btnBulkSelectAll"),
  btnBulkDeselectAll: document.getElementById("btnBulkDeselectAll"),
  btnQuickDiscOnly: document.getElementById("btnQuickDiscOnly"),
  btnOpenBulkModal: document.getElementById("btnOpenBulkModal"),
  btnBulkRemove: document.getElementById("btnBulkRemove"),
  btnExitBulk: document.getElementById("btnExitBulk"),
  bulkEditModal: document.getElementById("bulkEditModal"),
  btnCloseBulkModal: document.getElementById("btnCloseBulkModal"),
  btnCancelBulkModal: document.getElementById("btnCancelBulkModal"),
  bulkConditionSelect: document.getElementById("bulkConditionSelect"),
  bulkChkSleeve: document.getElementById("bulkChkSleeve"),
  bulkChkCase: document.getElementById("bulkChkCase"),
  bulkChkWorking: document.getElementById("bulkChkWorking"),
  bulkTxtNotes: document.getElementById("bulkTxtNotes"),
  btnApplyBulkEdit: document.getElementById("btnApplyBulkEdit"),
  bulkModalFeedback: document.getElementById("bulkModalFeedback"),

  // Single Item Edit Modal
  singleEditModal: document.getElementById("singleEditModal"),
  singleEditModalTitle: document.getElementById("singleEditModalTitle"),
  btnCloseSingleEdit: document.getElementById("btnCloseSingleEdit"),
  btnCancelSingleEdit: document.getElementById("btnCancelSingleEdit"),
  singleEditCondition: document.getElementById("singleEditCondition"),
  singleEditChkSleeve: document.getElementById("singleEditChkSleeve"),
  singleEditChkCase: document.getElementById("singleEditChkCase"),
  singleEditChkWorking: document.getElementById("singleEditChkWorking"),
  singleEditNotes: document.getElementById("singleEditNotes"),
  btnSaveSingleEdit: document.getElementById("btnSaveSingleEdit"),

  // --- Settings Page Elements ---
  txtTwitchClientId: document.getElementById("txtTwitchClientId"),
  txtTwitchClientSecret: document.getElementById("txtTwitchClientSecret"),
  btnSaveSettings: document.getElementById("btnSaveSettings"),
  igdbStatusBadge: document.getElementById("igdbStatusBadge"),
  settingsFeedback: document.getElementById("settingsFeedback"),
  btnDownloadScans: document.getElementById("btnDownloadScans"),
  scansDownloadStatus: document.getElementById("scansDownloadStatus"),
  btnFetchBoxart: document.getElementById("btnFetchBoxart"),
  boxartFetchStatus: document.getElementById("boxartFetchStatus"),
  btnExportJson: document.getElementById("btnExportJson"),
  btnImportJson: document.getElementById("btnImportJson"),
  importFileInput: document.getElementById("importFileInput"),
  importStatus: document.getElementById("importStatus"),
  btnSyncScrape: document.getElementById("btnSyncScrape"),
  syncStatus: document.getElementById("syncStatus"),

  // Modals
  detailModal: document.getElementById("detailModal"),
  detailModalContent: document.getElementById("detailModalContent"),
  modalTitle: document.getElementById("modalTitle"),
  modalConsoleBadge: document.getElementById("modalConsoleBadge"),
  modalSectionBadge: document.getElementById("modalSectionBadge"),
  modalScedBadge: document.getElementById("modalScedBadge"),
  btnCloseDetail: document.getElementById("btnCloseDetail"),
  zoomModal: document.getElementById("zoomModal"),
  zoomImage: document.getElementById("zoomImage"),
  zoomCaption: document.getElementById("zoomCaption"),
  btnCloseZoom: document.getElementById("btnCloseZoom")
};

/* ==========================================================================
   App Initialization
   ========================================================================== */
document.addEventListener("DOMContentLoaded", () => {
  setupNavigation();
  setupArchiveListeners();
  setupCollectionListeners();
  setupSettingsListeners();
  setupModalListeners();

  loadArchiveFilters();
  loadStats();
  fetchArchiveDemos(true);
  checkSettingsStatus();
});

/* ==========================================================================
   Navigation (3 Dedicated Views)
   ========================================================================== */
function setupNavigation() {
  elements.mainNavTabs.querySelectorAll(".nav-tab").forEach(tab => {
    tab.addEventListener("click", () => {
      const targetPage = tab.getAttribute("data-page");
      navigateTo(targetPage);
    });
  });

  elements.btnColGoToArchive.addEventListener("click", () => {
    navigateTo("archive");
  });
}

function navigateTo(pageName) {
  state.currentPage = pageName;

  // Update nav tabs
  elements.mainNavTabs.querySelectorAll(".nav-tab").forEach(tab => {
    if (tab.getAttribute("data-page") === pageName) {
      tab.classList.add("active");
    } else {
      tab.classList.remove("active");
    }
  });

  // Switch visible page view
  elements.pageArchive.style.display = pageName === "archive" ? "block" : "none";
  elements.pageCollection.style.display = pageName === "collection" ? "block" : "none";
  elements.pageSettings.style.display = pageName === "settings" ? "block" : "none";

  if (pageName === "collection") {
    loadStats();
    fetchCollectionDemos();
    loadCollectionGames();
  } else if (pageName === "settings") {
    checkSettingsStatus();
  }
}

/* ==========================================================================
   PAGE 1: ARCHIVE EXPLORER
   ========================================================================== */
function setupArchiveListeners() {
  // Search
  elements.archiveSearchInput.addEventListener("input", (e) => {
    state.archive.query = e.target.value;
    elements.btnArchiveClearSearch.style.display = state.archive.query ? "block" : "none";
    clearTimeout(state.archive.debounceTimer);
    state.archive.debounceTimer = setTimeout(() => fetchArchiveDemos(true), 250);
  });

  elements.btnArchiveClearSearch.addEventListener("click", () => {
    elements.archiveSearchInput.value = "";
    state.archive.query = "";
    elements.btnArchiveClearSearch.style.display = "none";
    fetchArchiveDemos(true);
  });

  // Console Pills
  elements.archiveConsolePills.querySelectorAll(".btn-toggle").forEach(btn => {
    btn.addEventListener("click", () => {
      elements.archiveConsolePills.querySelectorAll(".btn-toggle").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      state.archive.console = btn.getAttribute("data-console");
      fetchArchiveDemos(true);
    });
  });

  // Select Filters
  elements.archiveSelectSection.addEventListener("change", (e) => {
    state.archive.section = e.target.value;
    fetchArchiveDemos(true);
  });

  elements.archiveSelectCountry.addEventListener("change", (e) => {
    state.archive.country = e.target.value;
    fetchArchiveDemos(true);
  });

  // Layout View Switcher
  elements.btnArchiveViewGrid.addEventListener("click", () => setArchiveLayout("grid"));
  elements.btnArchiveViewList.addEventListener("click", () => setArchiveLayout("list"));

  // Pagination & Reset
  elements.btnArchiveLoadMore.addEventListener("click", () => fetchArchiveDemos(false));
  elements.btnArchiveResetFilters.addEventListener("click", resetArchiveFilters);
}

function setArchiveLayout(layout) {
  state.archive.layout = layout;
  localStorage.setItem("demoscene_archive_layout", layout);
  
  if (layout === "list") {
    elements.btnArchiveViewList.classList.add("active");
    elements.btnArchiveViewGrid.classList.remove("active");
    elements.archiveContainer.className = "pc-list";
  } else {
    elements.btnArchiveViewGrid.classList.add("active");
    elements.btnArchiveViewList.classList.remove("active");
    elements.archiveContainer.className = "disc-grid";
  }

  renderArchiveDemos(state.archive.demos, false);
}

async function fetchArchiveDemos(reset = false) {
  if (state.archive.isLoading) return;
  state.archive.isLoading = true;

  if (reset) {
    state.archive.offset = 0;
    state.archive.demos = [];
    elements.archiveContainer.innerHTML = "";
    elements.archiveResultsCount.textContent = "Searching archive...";
    elements.archiveEmptyState.style.display = "none";
  }

  const params = new URLSearchParams({
    q: state.archive.query,
    console: state.archive.console,
    section: state.archive.section,
    country: state.archive.country,
    status: "ALL",
    limit: state.archive.limit,
    offset: state.archive.offset
  });

  try {
    const res = await fetch(`${API_BASE}/api/demos?${params.toString()}`);
    if (!res.ok) throw new Error("Failed to fetch archive discs");
    const data = await res.json();

    state.archive.total = data.total;
    if (reset) {
      state.archive.demos = data.results;
    } else {
      state.archive.demos = state.archive.demos.concat(data.results);
    }

    renderArchiveDemos(data.results, !reset);

    elements.archiveResultsCount.textContent = `Showing ${state.archive.demos.length} of ${state.archive.total} discs`;
    elements.navCountArchive.textContent = state.archive.total;

    if (state.archive.demos.length < state.archive.total) {
      elements.archivePagination.style.display = "block";
      state.archive.offset += state.archive.limit;
    } else {
      elements.archivePagination.style.display = "none";
    }

    elements.archiveEmptyState.style.display = state.archive.total === 0 ? "block" : "none";
  } catch (err) {
    console.error("Error fetching archive:", err);
    elements.archiveResultsCount.textContent = "Error loading discs.";
  } finally {
    state.archive.isLoading = false;
  }
}

function renderArchiveDemos(demos, append = false) {
  if (!append) {
    elements.archiveContainer.innerHTML = "";
  }

  const fragment = document.createDocumentFragment();
  demos.forEach(demo => {
    const el = state.archive.layout === "list"
      ? createArchiveListRow(demo)
      : createArchiveCard(demo);
    fragment.appendChild(el);
  });

  elements.archiveContainer.appendChild(fragment);
}

function createArchiveCard(demo) {
  const card = document.createElement("div");
  card.className = "ps-card";
  card.setAttribute("data-id", demo.id);

  const thumbUrl = demo.primary_thumbnail || "/assets/demopals/f-eur.jpg";
  const scedText = demo.sced_codes && demo.sced_codes.length > 0 ? demo.sced_codes.join(", ") : (demo.catalog_line || "");

  let flagsHtml = "";
  if (demo.variants && demo.variants.length > 0) {
    const seen = new Set();
    demo.variants.forEach(v => {
      if (v.flag_icon && !seen.has(v.flag_icon)) {
        seen.add(v.flag_icon);
        flagsHtml += `<img src="${v.flag_icon}" alt="" class="flag-mini" />`;
      }
    });
  }

  let trackClass = "";
  let trackText = "Track";
  if (demo.coll_status === "owned") {
    trackClass = "is-owned";
    trackText = "In Collection";
  } else if (demo.coll_status === "wanted") {
    trackClass = "is-wanted";
    trackText = "Wishlist";
  }

  const countsHtml = [];
  if (demo.playable_count > 0) countsHtml.push(`<span>${demo.playable_count} Playable</span>`);
  if (demo.trailer_count > 0) countsHtml.push(`<span>${demo.trailer_count} Video</span>`);

  card.innerHTML = `
    <div class="card-img-wrap">
      <img src="${thumbUrl}" alt="${demo.title}" class="card-img" loading="lazy" />
      <div class="card-tag-strip">
        <span class="tag-badge tag-${demo.console.toLowerCase()}">${demo.console}</span>
        <span class="tag-badge">${demo.section_name}</span>
      </div>
    </div>
    <div class="card-info">
      ${flagsHtml ? `<div class="card-flags">${flagsHtml}</div>` : ""}
      <div class="card-title" title="${demo.title}">${demo.title}</div>
      <div class="card-sced">${scedText}</div>
      <div class="card-footer">
        <div class="card-counts">
          ${countsHtml.join("")}
        </div>
        <button class="btn-card-track ${trackClass}" data-action="track">${trackText}</button>
      </div>
    </div>
  `;

  card.addEventListener("click", () => openDetailModal(demo.id));
  const trackBtn = card.querySelector('[data-action="track"]');
  if (trackBtn) {
    trackBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      quickToggleCollectionStatus(demo);
    });
  }

  return card;
}

function createArchiveListRow(demo) {
  const row = document.createElement("div");
  row.className = "pc-row";
  row.setAttribute("data-id", demo.id);

  const thumbUrl = demo.primary_thumbnail || "/assets/demopals/f-eur.jpg";
  const scedText = demo.sced_codes && demo.sced_codes.length > 0 ? demo.sced_codes.join(", ") : (demo.catalog_line || "");

  let flagsHtml = "";
  if (demo.variants && demo.variants.length > 0) {
    const seen = new Set();
    const flagImgs = [];
    demo.variants.forEach(v => {
      if (v.flag_icon && !seen.has(v.flag_icon)) {
        seen.add(v.flag_icon);
        flagImgs.push(`<img src="${v.flag_icon}" alt="${v.country || ''}" class="flag-mini" title="${v.country || ''}" />`);
      }
    });
    if (flagImgs.length > 0) {
      flagsHtml = `<span class="pc-flags">${flagImgs.join("")}</span>`;
    }
  }

  let trackClass = "";
  let trackText = "Track";
  if (demo.coll_status === "owned") {
    trackClass = "is-owned";
    trackText = "In Collection";
  } else if (demo.coll_status === "wanted") {
    trackClass = "is-wanted";
    trackText = "Wishlist";
  }

  const countsHtml = [];
  if (demo.playable_count > 0) countsHtml.push(`<span>${demo.playable_count} Playable</span>`);
  if (demo.trailer_count > 0) countsHtml.push(`<span>${demo.trailer_count} Video</span>`);

  row.innerHTML = `
    <img src="${thumbUrl}" alt="${demo.title}" class="pc-thumb" loading="lazy" />
    <div class="pc-main">
      <div class="pc-title" title="${demo.title}">${demo.title}</div>
      <div class="pc-sub">
        <span class="tag-badge tag-${demo.console.toLowerCase()}">${demo.console}</span>
        <span class="pc-sec-name">${demo.section_name}</span>
        <span class="sced-mono">${scedText}</span>
        ${flagsHtml}
      </div>
    </div>
    <div class="pc-counts">
      ${countsHtml.join("")}
    </div>
    <div class="pc-actions">
      <button class="btn-card-track ${trackClass}" data-action="track">${trackText}</button>
    </div>
  `;

  row.addEventListener("click", () => openDetailModal(demo.id));
  const trackBtn = row.querySelector('[data-action="track"]');
  if (trackBtn) {
    trackBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      quickToggleCollectionStatus(demo);
    });
  }

  return row;
}

function resetArchiveFilters() {
  state.archive.query = "";
  state.archive.console = "ALL";
  state.archive.section = "ALL";
  state.archive.country = "ALL";

  elements.archiveSearchInput.value = "";
  elements.btnArchiveClearSearch.style.display = "none";
  elements.archiveConsolePills.querySelectorAll(".btn-toggle").forEach(b => {
    if (b.getAttribute("data-console") === "ALL") b.classList.add("active");
    else b.classList.remove("active");
  });
  elements.archiveSelectSection.value = "ALL";
  elements.archiveSelectCountry.value = "ALL";

  fetchArchiveDemos(true);
}

/* ==========================================================================
   PAGE 2: MY COLLECTION (PriceCharting Manager & Stats Widget)
   ========================================================================== */
function setupCollectionListeners() {
  // Mobile Stats Toggle
  elements.btnToggleMobileStats.addEventListener("click", () => {
    elements.collectionSideCard.classList.toggle("show-mobile");
  });

  // Search
  elements.colSearchInput.addEventListener("input", (e) => {
    state.collection.query = e.target.value;
    elements.btnColClearSearch.style.display = state.collection.query ? "block" : "none";
    clearTimeout(state.collection.debounceTimer);
    state.collection.debounceTimer = setTimeout(() => fetchCollectionDemos(), 250);
  });

  elements.btnColClearSearch.addEventListener("click", () => {
    elements.colSearchInput.value = "";
    state.collection.query = "";
    elements.btnColClearSearch.style.display = "none";
    fetchCollectionDemos();
  });

  // Games in Collection Widget Search
  if (elements.colGameSearchInput) {
    elements.colGameSearchInput.addEventListener("input", (e) => {
      const q = e.target.value.toLowerCase().trim();
      if (elements.btnColGameClearSearch) {
        elements.btnColGameClearSearch.style.display = q ? "block" : "none";
      }
      if (!q) {
        state.filteredGames = state.collectionGames;
      } else {
        state.filteredGames = state.collectionGames.filter(g => 
          g.name.toLowerCase().includes(q) || 
          (g.genre && g.genre.toLowerCase().includes(q)) ||
          (g.console && g.console.toLowerCase().includes(q))
        );
      }
      renderCollectionGamesList(state.filteredGames);
    });
  }

  if (elements.btnColGameClearSearch) {
    elements.btnColGameClearSearch.addEventListener("click", () => {
      elements.colGameSearchInput.value = "";
      elements.btnColGameClearSearch.style.display = "none";
      state.filteredGames = state.collectionGames;
      renderCollectionGamesList(state.filteredGames);
    });
  }

  // Console Pills
  elements.colConsolePills.querySelectorAll(".btn-toggle").forEach(btn => {
    btn.addEventListener("click", () => {
      elements.colConsolePills.querySelectorAll(".btn-toggle").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      state.collection.console = btn.getAttribute("data-console");
      fetchCollectionDemos();
    });
  });

  // Condition Filter
  elements.colSelectCondition.addEventListener("change", (e) => {
    state.collection.condition = e.target.value;
    fetchCollectionDemos();
  });

  // Checklist Filter
  elements.colSelectChecklist.addEventListener("change", (e) => {
    state.collection.checklist = e.target.value;
    fetchCollectionDemos();
  });

  // View Switcher (Cards vs PriceCharting 1-Line List)
  elements.btnColViewCards.addEventListener("click", () => setCollectionLayout("grid"));
  elements.btnColViewList.addEventListener("click", () => setCollectionLayout("list"));

  // Bulk Edit Toggle
  elements.btnColToggleBulk.addEventListener("click", toggleCollectionBulkMode);
  elements.btnExitBulk.addEventListener("click", toggleCollectionBulkMode);
  elements.btnBulkSelectAll.addEventListener("click", selectAllCollectionDemos);
  elements.btnBulkDeselectAll.addEventListener("click", deselectAllCollectionDemos);

  // Quick Bulk Actions
  elements.btnQuickDiscOnly.addEventListener("click", () => handleQuickCollectionBulkUpdate("disc_only"));
  elements.btnBulkRemove.addEventListener("click", handleBulkRemoveCollection);

  // Advanced Bulk Modal
  elements.btnOpenBulkModal.addEventListener("click", () => openModal(elements.bulkEditModal));
  elements.btnCloseBulkModal.addEventListener("click", () => closeModal(elements.bulkEditModal));
  elements.btnCancelBulkModal.addEventListener("click", () => closeModal(elements.bulkEditModal));
  elements.btnApplyBulkEdit.addEventListener("click", handleApplyAdvancedBulkEdit);

  // Single Item Edit Modal
  elements.btnCloseSingleEdit.addEventListener("click", () => closeModal(elements.singleEditModal));
  elements.btnCancelSingleEdit.addEventListener("click", () => closeModal(elements.singleEditModal));
  elements.btnSaveSingleEdit.addEventListener("click", handleSaveSingleEdit);
}

function setCollectionLayout(layout) {
  state.collection.layout = layout;
  localStorage.setItem("demoscene_collection_layout", layout);

  if (layout === "grid") {
    elements.btnColViewCards.classList.add("active");
    elements.btnColViewList.classList.remove("active");
    elements.collectionContainer.className = "disc-grid";
  } else {
    elements.btnColViewList.classList.add("active");
    elements.btnColViewCards.classList.remove("active");
    elements.collectionContainer.className = "pc-list";
  }

  renderCollectionDemos(state.collection.demos);
}

async function fetchCollectionDemos() {
  if (state.collection.isLoading) return;
  state.collection.isLoading = true;

  const params = new URLSearchParams({
    q: state.collection.query,
    console: state.collection.console,
    status: "owned",
    limit: 200,
    offset: 0
  });

  try {
    const res = await fetch(`${API_BASE}/api/demos?${params.toString()}`);
    if (!res.ok) throw new Error("Failed to fetch collection");
    const data = await res.json();

    let list = data.results || [];

    // Client-side condition filter
    if (state.collection.condition !== "ALL") {
      list = list.filter(d => (d.coll_condition || "good") === state.collection.condition);
    }

    // Client-side checklist filter
    if (state.collection.checklist === "no_sleeve") {
      list = list.filter(d => d.coll_has_sleeve === 0);
    } else if (state.collection.checklist === "has_sleeve") {
      list = list.filter(d => d.coll_has_sleeve !== 0);
    } else if (state.collection.checklist === "has_case") {
      list = list.filter(d => d.coll_has_case !== 0);
    } else if (state.collection.checklist === "not_working") {
      list = list.filter(d => d.coll_is_working === 0);
    }

    state.collection.demos = list;
    state.collection.total = list.length;

    renderCollectionDemos(list);
    elements.colEmptyState.style.display = list.length === 0 ? "block" : "none";
  } catch (err) {
    console.error("Error fetching collection:", err);
  } finally {
    state.collection.isLoading = false;
  }
}

function renderCollectionDemos(demos) {
  elements.collectionContainer.innerHTML = "";
  const fragment = document.createDocumentFragment();

  demos.forEach(demo => {
    const el = state.collection.layout === "grid"
      ? createCollectionCard(demo)
      : createPriceChartingListRow(demo);
    fragment.appendChild(el);
  });

  elements.collectionContainer.appendChild(fragment);
}

/* PriceCharting 1-Line Row */
function createPriceChartingListRow(demo) {
  const row = document.createElement("div");
  row.className = "pc-row";
  row.setAttribute("data-id", demo.id);

  const isSelected = state.collection.selectedIds.has(demo.id);
  if (isSelected) {
    row.classList.add("is-selected");
  }

  const thumbUrl = demo.primary_thumbnail || "/assets/demopals/f-eur.jpg";
  const scedText = demo.sced_codes && demo.sced_codes.length > 0 ? demo.sced_codes.join(", ") : (demo.catalog_line || "");

  // Region Flags
  let flagsHtml = "";
  if (demo.variants && demo.variants.length > 0) {
    const seen = new Set();
    const flagImgs = [];
    demo.variants.forEach(v => {
      if (v.flag_icon && !seen.has(v.flag_icon)) {
        seen.add(v.flag_icon);
        flagImgs.push(`<img src="${v.flag_icon}" alt="${v.country || ''}" class="flag-mini" title="${v.country || ''}" />`);
      }
    });
    if (flagImgs.length > 0) {
      flagsHtml = `<span class="pc-flags">${flagImgs.join("")}</span>`;
    }
  }

  // Condition Badge
  const cond = demo.coll_condition || "good";
  let condLabel = cond.replace("_", " ").toUpperCase();
  if (cond === "disc_only") condLabel = "DISC ONLY";
  else if (cond === "mint") condLabel = "MINT";
  else if (cond === "good") condLabel = "GOOD";
  else if (cond === "acceptable") condLabel = "ACCEPTABLE";
  else if (cond === "poor") condLabel = "POOR";
  const condBadge = `<span class="pc-cond-tag pc-cond-${cond}">${condLabel}</span>`;

  // Checklist indicators (clean retro text badges)
  const sleevePill = demo.coll_has_sleeve !== 0
    ? `<span class="pc-check-pill pill-active" title="Has Original Slipcover">SLV</span>`
    : `<span class="pc-check-pill pill-dim" title="Missing Slipcover">NO SLV</span>`;

  const casePill = demo.coll_has_case !== 0
    ? `<span class="pc-check-pill pill-active" title="In Jewel/DVD Case">CASE</span>`
    : `<span class="pc-check-pill pill-dim" title="Missing Case">NO CASE</span>`;

  const workingPill = demo.coll_is_working !== 0
    ? `<span class="pc-check-pill pill-ok" title="Tested & Working">OK</span>`
    : `<span class="pc-check-pill pill-warn" title="Needs Testing / Not Working">TEST</span>`;

  // Checkbox (bulk mode)
  let selectCell = "";
  if (state.collection.isBulkMode) {
    selectCell = `
      <div class="pc-select-cell" onclick="event.stopPropagation();">
        <input type="checkbox" class="card-checkbox" data-id="${demo.id}" ${isSelected ? "checked" : ""} />
      </div>
    `;
  }

  const countsHtml = [];
  if (demo.playable_count > 0) countsHtml.push(`<span>${demo.playable_count} Playable</span>`);
  if (demo.trailer_count > 0) countsHtml.push(`<span>${demo.trailer_count} Video</span>`);

  row.innerHTML = `
    ${selectCell}
    <img src="${thumbUrl}" alt="${demo.title}" class="pc-thumb" loading="lazy" />
    <div class="pc-main">
      <div class="pc-title" title="${demo.title}">${demo.title}</div>
      <div class="pc-sub">
        <span class="tag-badge tag-${demo.console.toLowerCase()}">${demo.console}</span>
        <span class="pc-sec-name">${demo.section_name}</span>
        <span class="sced-mono">${scedText}</span>
        ${flagsHtml}
        ${demo.coll_notes ? `<span class="pc-note-snippet">"${demo.coll_notes}"</span>` : ""}
      </div>
    </div>
    <div class="pc-counts">
      ${countsHtml.join("")}
    </div>
    ${condBadge}
    <div class="pc-checklist">
      ${sleevePill}
      ${casePill}
      ${workingPill}
    </div>
    <div class="pc-actions">
      <button class="btn-pc-action btn-pc-edit" data-action="edit" title="Edit Condition & Notes">Edit</button>
      <button class="btn-pc-action btn-pc-remove" data-action="remove" title="Remove from Collection">Remove</button>
    </div>
  `;

  row.addEventListener("click", () => {
    if (state.collection.isBulkMode) {
      toggleCollectionSelection(demo.id);
    } else {
      openDetailModal(demo.id);
    }
  });

  const editBtn = row.querySelector('[data-action="edit"]');
  if (editBtn) {
    editBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      openSingleEditModal(demo);
    });
  }

  const removeBtn = row.querySelector('[data-action="remove"]');
  if (removeBtn) {
    removeBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      handleRemoveSingleFromCollection(demo);
    });
  }

  const chk = row.querySelector(".card-checkbox");
  if (chk) {
    chk.addEventListener("change", (e) => {
      e.stopPropagation();
      toggleCollectionSelection(demo.id, chk.checked);
    });
  }

  return row;
}

function createCollectionCard(demo) {
  const card = document.createElement("div");
  card.className = "ps-card";
  card.setAttribute("data-id", demo.id);

  const isSelected = state.collection.selectedIds.has(demo.id);
  if (isSelected) {
    card.classList.add("is-selected");
  }

  const thumbUrl = demo.primary_thumbnail || "/assets/demopals/f-eur.jpg";
  const scedText = demo.sced_codes && demo.sced_codes.length > 0 ? demo.sced_codes.join(", ") : (demo.catalog_line || "");

  // Region Flags
  let flagsHtml = "";
  if (demo.variants && demo.variants.length > 0) {
    const seen = new Set();
    const flagImgs = [];
    demo.variants.forEach(v => {
      if (v.flag_icon && !seen.has(v.flag_icon)) {
        seen.add(v.flag_icon);
        flagImgs.push(`<img src="${v.flag_icon}" alt="${v.country || ''}" class="flag-mini" title="${v.country || ''}" />`);
      }
    });
    if (flagImgs.length > 0) {
      flagsHtml = `<span class="pc-flags">${flagImgs.join("")}</span>`;
    }
  }

  // Condition Badge
  const cond = demo.coll_condition || "good";
  let condLabel = cond.replace("_", " ").toUpperCase();
  if (cond === "disc_only") condLabel = "DISC ONLY";
  else if (cond === "mint") condLabel = "MINT";
  else if (cond === "good") condLabel = "GOOD";
  else if (cond === "acceptable") condLabel = "ACCEPTABLE";
  else if (cond === "poor") condLabel = "POOR";
  const condBadge = `<span class="pc-cond-tag pc-cond-${cond}">${condLabel}</span>`;

  // Checklist indicators (clean retro text badges)
  const sleevePill = demo.coll_has_sleeve !== 0
    ? `<span class="pc-check-pill pill-active" title="Has Original Slipcover">SLV</span>`
    : `<span class="pc-check-pill pill-dim" title="Missing Slipcover">NO SLV</span>`;

  const casePill = demo.coll_has_case !== 0
    ? `<span class="pc-check-pill pill-active" title="In Jewel/DVD Case">CASE</span>`
    : `<span class="pc-check-pill pill-dim" title="Missing Case">NO CASE</span>`;

  const workingPill = demo.coll_is_working !== 0
    ? `<span class="pc-check-pill pill-ok" title="Tested & Working">OK</span>`
    : `<span class="pc-check-pill pill-warn" title="Needs Testing / Not Working">TEST</span>`;

  let selectBox = "";
  if (state.collection.isBulkMode) {
    selectBox = `
      <div class="card-select-wrap" onclick="event.stopPropagation();">
        <input type="checkbox" class="card-checkbox" data-id="${demo.id}" ${isSelected ? "checked" : ""} />
      </div>
    `;
  }

  const countsHtml = [];
  if (demo.playable_count > 0) countsHtml.push(`<span>${demo.playable_count} Playable</span>`);
  if (demo.trailer_count > 0) countsHtml.push(`<span>${demo.trailer_count} Video</span>`);

  card.innerHTML = `
    <div class="card-img-wrap">
      ${selectBox}
      <img src="${thumbUrl}" alt="${demo.title}" class="card-img" loading="lazy" />
      <div class="card-tag-strip">
        <span class="tag-badge tag-${demo.console.toLowerCase()}">${demo.console}</span>
        <span class="tag-badge">${demo.section_name}</span>
      </div>
    </div>
    <div class="card-info">
      <div class="card-title" title="${demo.title}">${demo.title}</div>
      <div class="card-sced">${scedText} ${flagsHtml}</div>
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;gap:4px;">
        ${condBadge}
        <div class="pc-checklist">
          ${sleevePill}
          ${casePill}
          ${workingPill}
        </div>
      </div>
      ${demo.coll_notes ? `<div class="pc-note-snippet mb-1" style="font-size:11px;color:#666;font-style:italic;margin-bottom:6px;">"${demo.coll_notes}"</div>` : ''}
      <div class="card-footer">
        <div class="card-counts">
          ${countsHtml.join("")}
        </div>
        <div style="display:flex;gap:4px;">
          <button class="btn-pc-action btn-pc-edit" data-action="edit" title="Edit Condition & Notes">Edit</button>
          <button class="btn-pc-action btn-pc-remove" data-action="remove" title="Remove from Collection">Remove</button>
        </div>
      </div>
    </div>
  `;

  card.addEventListener("click", () => {
    if (state.collection.isBulkMode) {
      toggleCollectionSelection(demo.id);
    } else {
      openDetailModal(demo.id);
    }
  });

  const editBtn = card.querySelector('[data-action="edit"]');
  if (editBtn) {
    editBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      openSingleEditModal(demo);
    });
  }

  const removeBtn = card.querySelector('[data-action="remove"]');
  if (removeBtn) {
    removeBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      handleRemoveSingleFromCollection(demo);
    });
  }

  return card;
}

/* ==========================================================================
   Single Disc Quick Edit Modal
   ========================================================================== */
function openSingleEditModal(demo) {
  state.editingDemoId = demo.id;
  elements.singleEditModalTitle.textContent = `Edit: ${demo.title}`;
  elements.singleEditCondition.value = demo.coll_condition || "good";
  elements.singleEditChkSleeve.checked = demo.coll_has_sleeve !== 0;
  elements.singleEditChkCase.checked = demo.coll_has_case !== 0;
  elements.singleEditChkWorking.checked = demo.coll_is_working !== 0;
  elements.singleEditNotes.value = demo.coll_notes || "";
  openModal(elements.singleEditModal);
}

async function handleSaveSingleEdit() {
  if (!state.editingDemoId) return;

  const payload = {
    status: "owned",
    condition: elements.singleEditCondition.value,
    has_sleeve: elements.singleEditChkSleeve.checked ? 1 : 0,
    has_case: elements.singleEditChkCase.checked ? 1 : 0,
    is_working: elements.singleEditChkWorking.checked ? 1 : 0,
    notes: elements.singleEditNotes.value.trim()
  };

  try {
    const res = await fetch(`${API_BASE}/api/collection/${encodeURIComponent(state.editingDemoId)}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });

    if (res.ok) {
      closeModal(elements.singleEditModal);
      fetchCollectionDemos();
      loadStats();
      loadCollectionGames();
    }
  } catch (err) {
    console.error("Failed to save edit:", err);
  }
}

async function handleRemoveSingleFromCollection(demo) {
  if (!confirm(`Remove "${demo.title}" from your collection?`)) return;

  try {
    const res = await fetch(`${API_BASE}/api/collection/${encodeURIComponent(demo.id)}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status: "unowned" })
    });

    if (res.ok) {
      fetchCollectionDemos();
      loadStats();
      loadCollectionGames();
    }
  } catch (err) {
    console.error("Failed to remove:", err);
  }
}

/* ==========================================================================
   Collection Bulk Operations
   ========================================================================== */
function toggleCollectionBulkMode() {
  state.collection.isBulkMode = !state.collection.isBulkMode;

  if (state.collection.isBulkMode) {
    elements.bulkActionBar.style.display = "flex";
    elements.btnColToggleBulk.classList.add("ps-btn-dark");
    elements.btnColToggleBulk.textContent = "Exit Bulk";
  } else {
    elements.bulkActionBar.style.display = "none";
    elements.btnColToggleBulk.classList.remove("ps-btn-dark");
    elements.btnColToggleBulk.textContent = "Bulk Edit";
    state.collection.selectedIds.clear();
  }

  updateCollectionBulkCount();
  renderCollectionDemos(state.collection.demos);
}

function toggleCollectionSelection(demoId, force = null) {
  if (force !== null) {
    if (force) state.collection.selectedIds.add(demoId);
    else state.collection.selectedIds.delete(demoId);
  } else {
    if (state.collection.selectedIds.has(demoId)) {
      state.collection.selectedIds.delete(demoId);
    } else {
      state.collection.selectedIds.add(demoId);
    }
  }

  updateCollectionBulkCount();

  const item = document.querySelector(`[data-id="${demoId}"]`);
  if (item) {
    const isSel = state.collection.selectedIds.has(demoId);
    if (isSel) item.classList.add("is-selected");
    else item.classList.remove("is-selected");
    const chk = item.querySelector(".card-checkbox");
    if (chk) chk.checked = isSel;
  }
}

function selectAllCollectionDemos() {
  state.collection.demos.forEach(d => state.collection.selectedIds.add(d.id));
  updateCollectionBulkCount();
  renderCollectionDemos(state.collection.demos);
}

function deselectAllCollectionDemos() {
  state.collection.selectedIds.clear();
  updateCollectionBulkCount();
  renderCollectionDemos(state.collection.demos);
}

function updateCollectionBulkCount() {
  elements.bulkSelectedCount.textContent = `${state.collection.selectedIds.size} Discs Selected`;
}

async function handleQuickCollectionBulkUpdate(actionType) {
  if (state.collection.selectedIds.size === 0) {
    alert("Please select at least one disc.");
    return;
  }

  const ids = Array.from(state.collection.selectedIds);
  let payload = { demo_ids: ids };

  if (actionType === "disc_only") {
    payload.status = "owned";
    payload.condition = "disc_only";
    payload.has_sleeve = 0;
    payload.has_case = 1;
    payload.is_working = 1;
  }

  try {
    const res = await fetch(`${API_BASE}/api/collection/bulk`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });

    if (res.ok) {
      state.collection.selectedIds.clear();
      updateCollectionBulkCount();
      fetchCollectionDemos();
      loadStats();
      loadCollectionGames();
    }
  } catch (err) {
    console.error("Bulk update error:", err);
  }
}

async function handleBulkRemoveCollection() {
  if (state.collection.selectedIds.size === 0) return;
  if (!confirm(`Remove ${state.collection.selectedIds.size} selected discs from your collection?`)) return;

  const payload = {
    demo_ids: Array.from(state.collection.selectedIds),
    status: "unowned"
  };

  try {
    const res = await fetch(`${API_BASE}/api/collection/bulk`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });

    if (res.ok) {
      state.collection.selectedIds.clear();
      updateCollectionBulkCount();
      fetchCollectionDemos();
      loadStats();
      loadCollectionGames();
    }
  } catch (err) {
    console.error("Bulk remove error:", err);
  }
}

async function handleApplyAdvancedBulkEdit() {
  if (state.collection.selectedIds.size === 0) {
    showFormFeedback(elements.bulkModalFeedback, "No discs selected.", "error");
    return;
  }

  const condVal = elements.bulkConditionSelect.value;
  const notesVal = elements.bulkTxtNotes.value.trim();

  const payload = {
    demo_ids: Array.from(state.collection.selectedIds),
    status: "owned",
    has_sleeve: elements.bulkChkSleeve.checked ? 1 : 0,
    has_case: elements.bulkChkCase.checked ? 1 : 0,
    is_working: elements.bulkChkWorking.checked ? 1 : 0
  };

  if (condVal !== "keep") payload.condition = condVal;
  if (notesVal) payload.notes = notesVal;

  try {
    const res = await fetch(`${API_BASE}/api/collection/bulk`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });

    if (res.ok) {
      closeModal(elements.bulkEditModal);
      state.collection.selectedIds.clear();
      updateCollectionBulkCount();
      fetchCollectionDemos();
      loadStats();
      loadCollectionGames();
    } else {
      showFormFeedback(elements.bulkModalFeedback, "Failed to apply changes.", "error");
    }
  } catch (err) {
    showFormFeedback(elements.bulkModalFeedback, "Error applying batch edit.", "error");
  }
}

/* ==========================================================================
   Statistics & Collection Ledger
   ========================================================================== */
async function loadStats() {
  try {
    const res = await fetch(`${API_BASE}/api/stats`);
    if (!res.ok) return;
    const stats = await res.json();
    state.stats = stats;

    const totalDemos = stats.total_demos || 872;
    const ownedDemos = stats.owned_demos || 0;
    const completionRate = stats.completion_rate || 0;

    // Header Badges
    if (elements.navCountArchive) elements.navCountArchive.textContent = totalDemos;
    if (elements.navCountOwned) elements.navCountOwned.textContent = ownedDemos;

    // Overall Progress Bar
    if (elements.colStatCompletionRate) elements.colStatCompletionRate.textContent = `${completionRate}%`;
    if (elements.colStatBarTotal) elements.colStatBarTotal.style.width = `${Math.min(completionRate, 100)}%`;
    if (elements.colStatOwnedCount) elements.colStatOwnedCount.textContent = ownedDemos;
    if (elements.colStatTotalDemos) elements.colStatTotalDemos.textContent = totalDemos;

    // PS1 & PS2 Platform Bars
    const ps1Owned = stats.owned_ps1 || 0;
    const ps1Total = stats.total_ps1 || 590;
    const ps1Rate = ps1Total > 0 ? ((ps1Owned / ps1Total) * 100).toFixed(1) : 0;
    if (elements.colStatPs1Summary) elements.colStatPs1Summary.textContent = `${ps1Owned} / ${ps1Total} (${ps1Rate}%)`;
    if (elements.colStatBarPs1) elements.colStatBarPs1.style.width = `${Math.min(ps1Rate, 100)}%`;

    const ps2Owned = stats.owned_ps2 || 0;
    const ps2Total = stats.total_ps2 || 282;
    const ps2Rate = ps2Total > 0 ? ((ps2Owned / ps2Total) * 100).toFixed(1) : 0;
    if (elements.colStatPs2Summary) elements.colStatPs2Summary.textContent = `${ps2Owned} / ${ps2Total} (${ps2Rate}%)`;
    if (elements.colStatBarPs2) elements.colStatBarPs2.style.width = `${Math.min(ps2Rate, 100)}%`;

    // Physical Conditions (Bars proportional to total owned)
    const c = stats.conditions || {};
    const discOnly = c.disc_only || 0;
    const mint = c.mint || 0;
    const good = (c.good || 0) + (c.acceptable || 0);
    const safeOwned = Math.max(ownedDemos, 1);

    if (elements.colStatCondDiscOnly) elements.colStatCondDiscOnly.textContent = discOnly;
    if (elements.colStatBarDiscOnly) elements.colStatBarDiscOnly.style.width = ownedDemos > 0 ? `${(discOnly / safeOwned) * 100}%` : '0%';

    if (elements.colStatCondMint) elements.colStatCondMint.textContent = mint;
    if (elements.colStatBarMint) elements.colStatBarMint.style.width = ownedDemos > 0 ? `${(mint / safeOwned) * 100}%` : '0%';

    if (elements.colStatCondGood) elements.colStatCondGood.textContent = good;
    if (elements.colStatBarGood) elements.colStatBarGood.style.width = ownedDemos > 0 ? `${(good / safeOwned) * 100}%` : '0%';

    // Packaging & Testing Checklist Bars
    const withSleeve = c.with_sleeve || 0;
    const inCase = c.in_case || 0;
    const working = c.working || 0;

    if (elements.colStatWithSleeve) elements.colStatWithSleeve.textContent = withSleeve;
    if (elements.colStatBarWithSleeve) elements.colStatBarWithSleeve.style.width = ownedDemos > 0 ? `${(withSleeve / safeOwned) * 100}%` : '0%';

    if (elements.colStatInCase) elements.colStatInCase.textContent = inCase;
    if (elements.colStatBarInCase) elements.colStatBarInCase.style.width = ownedDemos > 0 ? `${(inCase / safeOwned) * 100}%` : '0%';

    if (elements.colStatWorking) elements.colStatWorking.textContent = working;
    if (elements.colStatBarWorking) elements.colStatBarWorking.style.width = ownedDemos > 0 ? `${(working / safeOwned) * 100}%` : '0%';

    // Series Breakdown with Mini Bars
    if (stats.series_breakdown && elements.colStatSeriesBreakdown) {
      elements.colStatSeriesBreakdown.innerHTML = stats.series_breakdown
        .map(s => {
          const sRate = s.total > 0 ? ((s.owned / s.total) * 100).toFixed(0) : 0;
          return `
            <div class="series-row-item">
              <div class="series-row-header">
                <span>[${s.console}] ${s.section_name}</span>
                <strong>${s.owned} / ${s.total} (${sRate}%)</strong>
              </div>
              <div class="stat-bar" style="height: 4px;">
                <div class="stat-bar-fill fill-green" style="width: ${sRate}%;"></div>
              </div>
            </div>
          `;
        }).join("");
    }
  } catch (err) {
    console.error("Failed to load stats:", err);
  }
}

/* ==========================================================================
   Games in Collection Widget
   ========================================================================== */
async function loadCollectionGames() {
  try {
    const res = await fetch(`${API_BASE}/api/collection/games`);
    if (!res.ok) return;
    const games = await res.json();
    state.collectionGames = games;
    state.filteredGames = games;

    if (elements.colUniqueGamesCount) {
      elements.colUniqueGamesCount.textContent = `${games.length} Games`;
    }

    renderCollectionGamesList(games);
  } catch (err) {
    console.error("Failed to load collection games:", err);
    if (elements.collectionGamesList) {
      elements.collectionGamesList.innerHTML = '<p class="text-muted" style="font-size:11px;">No games loaded.</p>';
    }
  }
}

function renderCollectionGamesList(games) {
  if (!elements.collectionGamesList) return;

  if (games.length === 0) {
    elements.collectionGamesList.innerHTML = '<p class="text-muted" style="font-size:11px;padding:8px 0;">No games found in your collection.</p>';
    return;
  }

  elements.collectionGamesList.innerHTML = games.map(g => {
    const thumbHtml = g.boxart_url
      ? `<img src="${g.boxart_url}" alt="${g.name}" class="col-game-thumb" loading="lazy" />`
      : `<div class="col-game-retro-badge">${g.initials || 'PS'}</div>`;

    const demoPills = (g.found_in || []).map(d => `
      <span class="col-game-demo-pill" data-demo-id="${d.demo_id}" title="Found on: ${d.demo_title} (${d.sced})">
        ${d.demo_title}
      </span>
    `).join("");

    return `
      <div class="col-game-item">
        ${thumbHtml}
        <div class="col-game-info">
          <div class="col-game-title" title="${g.name}">${g.name}</div>
          <div class="col-game-meta">
            <span class="tag-badge tag-${g.console.toLowerCase()}">${g.console}</span>
            <span>${g.genre}</span>
            <a href="${g.links.youtube}" target="_blank" rel="noopener" class="game-link-btn">Play</a>
            <a href="${g.links.wikipedia}" target="_blank" rel="noopener" class="game-link-btn">Wiki</a>
          </div>
          <div class="col-game-demos-pills">
            ${demoPills}
          </div>
        </div>
      </div>
    `;
  }).join("");

  // Attach click listener on demo pills to open detail modal
  elements.collectionGamesList.querySelectorAll(".col-game-demo-pill").forEach(pill => {
    pill.addEventListener("click", (e) => {
      e.stopPropagation();
      const demoId = pill.getAttribute("data-demo-id");
      if (demoId) openDetailModal(demoId);
    });
  });
}

/* ==========================================================================
   Quick Collection Toggle
   ========================================================================== */
async function quickToggleCollectionStatus(demo) {
  const nextStatus = demo.coll_status === "owned" ? "unowned" : "owned";
  try {
    const res = await fetch(`${API_BASE}/api/collection/${encodeURIComponent(demo.id)}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        status: nextStatus,
        condition: demo.coll_condition || "good",
        has_sleeve: demo.coll_has_sleeve !== undefined ? demo.coll_has_sleeve : 1,
        has_case: demo.coll_has_case !== undefined ? demo.coll_has_case : 1,
        is_working: demo.coll_is_working !== undefined ? demo.coll_is_working : 1,
        notes: demo.coll_notes || ""
      })
    });

    if (res.ok) {
      demo.coll_status = nextStatus;
      renderArchiveDemos(state.archive.demos, false);
      loadStats();
    }
  } catch (err) {
    console.error("Failed to update status:", err);
  }
}

/* ==========================================================================
   PAGE 3: SETTINGS HUB
   ========================================================================== */
function setupSettingsListeners() {
  elements.btnSaveSettings.addEventListener("click", handleSaveSettings);
  elements.btnDownloadScans.addEventListener("click", handleDownloadScans);
  elements.btnFetchBoxart.addEventListener("click", handleFetchBoxart);
  elements.btnExportJson.addEventListener("click", handleExportBackup);
  elements.btnImportJson.addEventListener("click", () => elements.importFileInput.click());
  elements.importFileInput.addEventListener("change", handleImportBackup);
  elements.btnSyncScrape.addEventListener("click", handleSyncScrape);
}

async function checkSettingsStatus() {
  try {
    const res = await fetch(`${API_BASE}/api/settings`);
    if (!res.ok) return;
    const data = await res.json();

    if (data.configured) {
      elements.igdbStatusBadge.textContent = "IGDB Online";
      elements.igdbStatusBadge.className = "status-badge-online";
    } else {
      elements.igdbStatusBadge.textContent = "Not Configured";
      elements.igdbStatusBadge.className = "status-badge-offline";
    }
  } catch (err) {
    console.error("Could not check settings:", err);
  }
}

async function handleSaveSettings() {
  const clientId = elements.txtTwitchClientId.value.trim();
  const clientSecret = elements.txtTwitchClientSecret.value.trim();

  if (!clientId || !clientSecret) {
    showFormFeedback(elements.settingsFeedback, "Both Client ID and Secret are required.", "error");
    return;
  }

  elements.btnSaveSettings.textContent = "Verifying with Twitch...";
  elements.btnSaveSettings.disabled = true;

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
    if (res.ok) {
      showFormFeedback(elements.settingsFeedback, "Credentials verified and saved successfully.", "success");
      checkSettingsStatus();
    } else {
      showFormFeedback(elements.settingsFeedback, data.detail || "Failed to authenticate.", "error");
    }
  } catch (err) {
    showFormFeedback(elements.settingsFeedback, "Connection error saving settings.", "error");
  } finally {
    elements.btnSaveSettings.textContent = "Verify & Save Credentials";
    elements.btnSaveSettings.disabled = false;
  }
}

async function handleDownloadScans() {
  elements.btnDownloadScans.disabled = true;
  elements.scansDownloadStatus.textContent = "Scans download running in background...";
  try {
    await fetch(`${API_BASE}/api/assets/download-all`, { method: "POST" });
    elements.scansDownloadStatus.textContent = "Download queued! Scans are caching to volume in background.";
  } catch (err) {
    elements.scansDownloadStatus.textContent = "Failed to queue download.";
  }
}

async function handleFetchBoxart() {
  elements.btnFetchBoxart.disabled = true;
  elements.boxartFetchStatus.textContent = "Cover fetch running in background...";
  try {
    await fetch(`${API_BASE}/api/boxart/fetch-all`, { method: "POST" });
    elements.boxartFetchStatus.textContent = "Box art batch fetch queued!";
  } catch (err) {
    elements.boxartFetchStatus.textContent = "Failed to queue box art fetch.";
  }
}

async function handleExportBackup() {
  try {
    const res = await fetch(`${API_BASE}/api/export`);
    const data = await res.json();
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `demoscene-collection-backup-${new Date().toISOString().slice(0, 10)}.json`;
    a.click();
    URL.revokeObjectURL(url);
  } catch (err) {
    alert("Export failed: " + err.message);
  }
}

async function handleImportBackup(e) {
  const file = e.target.files[0];
  if (!file) return;

  const reader = new FileReader();
  reader.onload = async (evt) => {
    try {
      const data = JSON.parse(evt.target.result);
      const res = await fetch(`${API_BASE}/api/import`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data)
      });
      const result = await res.json();
      if (res.ok) {
        elements.importStatus.textContent = `Restored ${result.imported_count} records successfully.`;
        loadStats();
      } else {
        elements.importStatus.textContent = `Import failed.`;
      }
    } catch (err) {
      elements.importStatus.textContent = `Invalid JSON file.`;
    }
  };
  reader.readAsText(file);
}

async function handleSyncScrape() {
  if (!confirm("Re-sync catalog with Crimson Ceremony archive in the background?")) return;
  elements.btnSyncScrape.disabled = true;
  elements.syncStatus.textContent = "Scraping archive sections...";
  try {
    await fetch(`${API_BASE}/api/scrape`, { method: "POST" });
    elements.syncStatus.textContent = "Sync task queued. The database will update shortly.";
  } catch (err) {
    elements.syncStatus.textContent = `Error: ${err.message}`;
  }
}

/* ==========================================================================
   Filter Loading & Modals
   ========================================================================== */
async function loadArchiveFilters() {
  try {
    const res = await fetch(`${API_BASE}/api/filters`);
    if (!res.ok) return;
    const data = await res.json();

    elements.archiveSelectSection.innerHTML = '<option value="ALL">All Series / Magazines</option>';
    data.sections.forEach(sec => {
      const opt = document.createElement("option");
      opt.value = sec.name;
      opt.textContent = `[${sec.console}] ${sec.name}`;
      elements.archiveSelectSection.appendChild(opt);
    });

    elements.archiveSelectCountry.innerHTML = '<option value="ALL">All Regions</option>';
    data.countries.forEach(country => {
      const opt = document.createElement("option");
      opt.value = country;
      opt.textContent = country;
      elements.archiveSelectCountry.appendChild(opt);
    });
  } catch (err) {
    console.error("Failed to load archive filters:", err);
  }
}

function setupModalListeners() {
  elements.btnCloseDetail.addEventListener("click", () => closeModal(elements.detailModal));
  elements.btnCloseZoom.addEventListener("click", () => closeModal(elements.zoomModal));

  window.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      closeAllModals();
    }
  });

  document.querySelectorAll(".ps-modal-backdrop").forEach(backdrop => {
    backdrop.addEventListener("click", (e) => {
      if (e.target === backdrop) {
        closeModal(backdrop);
      }
    });
  });
}

async function openDetailModal(demoId) {
  openModal(elements.detailModal);
  elements.detailModalContent.innerHTML = "<p>Loading disc details &amp; box art...</p>";

  try {
    const res = await fetch(`${API_BASE}/api/demos/${encodeURIComponent(demoId)}`);
    if (!res.ok) throw new Error("Could not load demo disc");
    const demo = await res.json();
    state.activeDemo = demo;
    state.activeVariantIndex = 0;

    elements.modalTitle.textContent = demo.title;
    elements.modalConsoleBadge.textContent = demo.console;
    elements.modalConsoleBadge.className = `tag-badge tag-${demo.console.toLowerCase()}`;
    elements.modalSectionBadge.textContent = demo.section_name;
    
    const sceds = demo.sced_codes && demo.sced_codes.length > 0 ? demo.sced_codes.join(", ") : (demo.catalog_line || "");
    elements.modalScedBadge.textContent = sceds;

    renderDetailModalContent(demo);
  } catch (err) {
    elements.detailModalContent.innerHTML = `<p class="txt-red">Error: ${err.message}</p>`;
  }
}

function renderDetailModalContent(demo) {
  const currentVariant = (demo.variants && demo.variants[state.activeVariantIndex]) || {};
  const scans = currentVariant.scans || [];
  
  const mainScanUrl = scans.length > 0 
    ? (scans[0].local_url || scans[0].remote_url) 
    : (demo.primary_thumbnail || "/assets/demopals/f-eur.jpg");

  let scanThumbsHtml = "";
  if (scans.length > 1) {
    scanThumbsHtml = `
      <div class="scans-thumbs mt-2">
        ${scans.map((s, idx) => `
          <button class="scan-thumb-btn ${idx === 0 ? 'active' : ''}" data-scan-idx="${idx}" title="${s.label}">
            <img src="${s.local_url || s.remote_url}" alt="${s.label}" />
          </button>
        `).join("")}
      </div>
    `;
  }

  let variantTabsHtml = "";
  if (demo.variants && demo.variants.length > 1) {
    variantTabsHtml = `
      <div class="variant-tabs mb-2">
        <label style="font-size:11px;font-weight:700;color:var(--text-muted);display:block;margin-bottom:4px;">RELEASES &amp; SCANS:</label>
        <div class="btn-group">
          ${demo.variants.map((v, idx) => `
            <button class="btn-toggle ${idx === state.activeVariantIndex ? 'active' : ''}" data-variant-idx="${idx}">
              ${v.country || 'Release'} (${v.sced || 'Scan'})
            </button>
          `).join("")}
        </div>
      </div>
    `;
  }

  const coll = demo.collection ? (demo.collection[currentVariant.sced || "default"] || demo.collection["default"] || {}) : {};
  const currentStatus = coll.status || "unowned";
  const currentCond = coll.condition || "good";

  let gamesHtml = "";
  const cats = demo.enriched_categories || {};
  for (const [catName, gameList] of Object.entries(cats)) {
    gamesHtml += `
      <div class="game-category-block">
        <h4 class="game-category-title">${catName} (${gameList.length})</h4>
        <div class="games-list">
          ${gameList.map(g => `
            <div class="game-item-card">
              ${g.boxart_url ? `
                <img src="${g.boxart_url}" alt="${g.name}" class="game-boxart-thumb" loading="lazy" />
              ` : `
                <div class="game-retro-badge">${g.initials || 'PS'}</div>
              `}
              <div class="game-meta">
                <div class="game-title" title="${g.name}">${g.name}</div>
                <div class="game-genre">${g.genre}</div>
                <div class="game-links">
                  <a href="${g.links.youtube}" target="_blank" rel="noopener" class="game-link-btn">YouTube</a>
                  <a href="${g.links.wikipedia}" target="_blank" rel="noopener" class="game-link-btn">Wiki</a>
                </div>
              </div>
            </div>
          `).join("")}
        </div>
      </div>
    `;
  }

  elements.detailModalContent.innerHTML = `
    <div class="detail-grid">
      <div class="detail-left">
        ${variantTabsHtml}
        <div class="scans-section">
          <div class="scans-main-view" id="mainScanView">
            <img id="detailMainImage" src="${mainScanUrl}" alt="${demo.title}" />
          </div>
          ${scanThumbsHtml}
        </div>

        <div class="collector-box">
          <h4>Collection Ledger</h4>
          <div class="collector-actions">
            <button class="ps-btn ps-btn-sm ${currentStatus === 'owned' ? 'ps-btn-dark' : ''}" id="btnModalOwned">
              ${currentStatus === 'owned' ? 'In Collection' : 'Mark Owned'}
            </button>
            <button class="ps-btn ps-btn-sm ${currentStatus === 'wanted' ? 'ps-btn-dark' : ''}" id="btnModalWanted">
              ${currentStatus === 'wanted' ? 'Wishlist' : 'Wishlist'}
            </button>
          </div>

          <div class="form-group mt-2">
            <label>Physical Condition</label>
            <select id="modalConditionSelect" class="ps-select">
              <option value="disc_only" ${currentCond === 'disc_only' ? 'selected' : ''}>Disc Only (Loose CD/DVD)</option>
              <option value="mint" ${currentCond === 'mint' ? 'selected' : ''}>Mint (Flawless)</option>
              <option value="good" ${currentCond === 'good' ? 'selected' : ''}>Good (Light signs of use)</option>
              <option value="acceptable" ${currentCond === 'acceptable' ? 'selected' : ''}>Acceptable</option>
              <option value="poor" ${currentCond === 'poor' ? 'selected' : ''}>Poor</option>
            </select>
          </div>

          <div class="form-group">
            <div class="chk-group">
              <label class="chk-label">
                <input type="checkbox" id="modalChkSleeve" ${coll.has_sleeve !== 0 ? 'checked' : ''} /> 
                Has Original Sleeve
              </label>
              <label class="chk-label">
                <input type="checkbox" id="modalChkCase" ${coll.has_case !== 0 ? 'checked' : ''} /> 
                In Jewel / DVD Case
              </label>
              <label class="chk-label">
                <input type="checkbox" id="modalChkWorking" ${coll.is_working !== 0 ? 'checked' : ''} /> 
                Tested &amp; Working
              </label>
            </div>
          </div>

          <div class="form-group">
            <label>Notes</label>
            <input type="text" id="modalTxtNotes" class="ps-input" value="${coll.notes || ''}" placeholder="e.g. Boot sale find" />
          </div>

          <button class="ps-btn ps-btn-sm ps-btn-dark mt-2" id="btnSaveModalCollection">Save Ledger Entry</button>
        </div>
      </div>

      <div class="detail-right">
        ${demo.notes ? `
          <div class="demo-notes-box mb-3" style="background:#f5f5f5;padding:8px 10px;border-left:3px solid #333;font-size:12px;margin-bottom:12px;">
            <strong>Archive Notes:</strong> ${demo.notes}
          </div>
        ` : ''}
        ${gamesHtml || '<p class="text-muted">No games catalogued for this demo.</p>'}
      </div>
    </div>
  `;

  // Attach Detail Event Handlers
  const mainView = document.getElementById("mainScanView");
  const mainImg = document.getElementById("detailMainImage");
  if (mainView && mainImg) {
    mainView.addEventListener("click", () => {
      openZoomModal(mainImg.src, demo.title);
    });
  }

  document.querySelectorAll(".scan-thumb-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      const idx = parseInt(btn.getAttribute("data-scan-idx"), 10);
      document.querySelectorAll(".scan-thumb-btn").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      if (scans[idx] && mainImg) {
        mainImg.src = scans[idx].local_url || scans[idx].remote_url;
      }
    });
  });

  document.querySelectorAll("[data-variant-idx]").forEach(btn => {
    btn.addEventListener("click", () => {
      state.activeVariantIndex = parseInt(btn.getAttribute("data-variant-idx"), 10);
      renderDetailModalContent(demo);
    });
  });

  const btnOwned = document.getElementById("btnModalOwned");
  const btnWanted = document.getElementById("btnModalWanted");
  const btnSave = document.getElementById("btnSaveModalCollection");

  if (btnOwned) btnOwned.addEventListener("click", () => saveModalCollectionState(demo, "owned"));
  if (btnWanted) btnWanted.addEventListener("click", () => saveModalCollectionState(demo, "wanted"));
  if (btnSave) btnSave.addEventListener("click", () => saveModalCollectionState(demo, null));
}

async function saveModalCollectionState(demo, overrideStatus = null) {
  const currentVariant = (demo.variants && demo.variants[state.activeVariantIndex]) || {};
  const variantId = currentVariant.sced || "default";

  const condVal = document.getElementById("modalConditionSelect").value;
  const hasSleeve = document.getElementById("modalChkSleeve").checked ? 1 : 0;
  const hasCase = document.getElementById("modalChkCase").checked ? 1 : 0;
  const isWorking = document.getElementById("modalChkWorking").checked ? 1 : 0;
  const notesVal = document.getElementById("modalTxtNotes").value.trim();

  let statusVal = "owned";
  if (overrideStatus) {
    statusVal = overrideStatus;
  } else {
    const existingColl = demo.collection ? (demo.collection[variantId] || {}) : {};
    statusVal = existingColl.status || "owned";
  }

  const payload = {
    variant_id: variantId,
    status: statusVal,
    condition: condVal,
    has_sleeve: hasSleeve,
    has_case: hasCase,
    is_working: isWorking,
    notes: notesVal
  };

  try {
    const res = await fetch(`${API_BASE}/api/collection/${encodeURIComponent(demo.id)}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });

    if (res.ok) {
      loadStats();
      loadCollectionGames();
      if (state.currentPage === "archive") fetchArchiveDemos(false);
      else if (state.currentPage === "collection") fetchCollectionDemos();
      openDetailModal(demo.id);
    }
  } catch (err) {
    console.error("Failed to save ledger:", err);
  }
}

/* ==========================================================================
   Modal Helpers
   ========================================================================== */
function openZoomModal(imgUrl, captionText) {
  elements.zoomImage.src = imgUrl;
  elements.zoomCaption.textContent = captionText;
  openModal(elements.zoomModal);
}

function openModal(modal) {
  modal.style.display = "flex";
}

function closeModal(modal) {
  modal.style.display = "none";
}

function closeAllModals() {
  document.querySelectorAll(".ps-modal-backdrop").forEach(m => m.style.display = "none");
}

function showFormFeedback(el, msg, type = "success") {
  el.textContent = msg;
  el.className = `form-feedback ${type}`;
  el.style.display = "block";
}
