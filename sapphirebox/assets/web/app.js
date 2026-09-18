const ICON_MANGA = '<path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><path d="M9 22V12h6v10"/>';
const ICON_BOOKS = '<path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/>';
const ICON_SUN = '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>';
const ICON_MOON = '<path d="M21 12.8A9 9 0 1 1 11.2 3 7 7 0 0 0 21 12.8z"/>';

const THEME_KEY = "sapphirebox-theme";
const READER_LAYOUT_KEY = "sapphirebox-reader-layout";
const JOB_POLL_MS = 1500;

// PDF pages are rendered to a <canvas> by pdf.js — never an <iframe> onto
// the browser's own PDF plugin, which some target environments (e.g. an
// e-reader's stripped-down browser) don't have at all.
if (window.pdfjsLib) {
  window.pdfjsLib.GlobalWorkerOptions.workerSrc = "vendor/pdf.worker.min.js";
}

const views = {
  "library": {
    title: "Biblioteca",
    sub: "Tudo que já foi baixado nesta máquina — mangás e livros juntos.",
    mode: "library",
  },
  "discover": {
    title: "Descobrir",
    sub: "Todas as fontes ligadas, num só lugar — clique numa pra ver o catálogo dela na hora, sem precisar buscar.",
    mode: "discover",
    panelId: "discover-sources",
  },
  "search": {
    title: "Buscar",
    sub: "Escolha o tipo acima, depois busque ao vivo na fonte selecionada.",
    mode: "search",
  },
  "downloads": {
    title: "Downloads",
    sub: "Fila de downloads em andamento.",
    mode: "downloads",
    panelId: "downloads-panel",
  },
  "settings": {
    title: "Configurações",
    sub: "Preferências locais e pasta de armazenamento.",
    mode: "settings",
    panelId: "settings-panel",
  },
  "about": {
    title: "Sobre",
    sub: "",
    mode: "panel",
    panelId: "about-panel",
  },
};

const SEARCH_CATEGORY_KEY = "sapphirebox-search-category";
const SEARCH_CATEGORIES = {
  manga: {
    domain: "manga",
    sourcesUrl: "/api/manga/sources",
    searchUrl: (q, source) => `/api/manga/search?q=${encodeURIComponent(q)}${source ? `&source=${encodeURIComponent(source)}` : ""}`,
    resultsKey: "results",
    emptyText: "Digite um título pra buscar — \"Todas as fontes\" já vem selecionado.",
  },
  livro: {
    domain: "books",
    category: "livro",
    sourcesUrl: "/api/books/sources?category=livro",
    searchUrl: (q, source) => `/api/books/search?q=${encodeURIComponent(q)}&category=livro${source ? `&source=${encodeURIComponent(source)}` : ""}`,
    resultsKey: "results",
    emptyText: "Digite um título ou autor pra buscar.",
  },
  quadrinho: {
    domain: "books",
    category: "quadrinho",
    sourcesUrl: "/api/books/sources?category=quadrinho",
    searchUrl: (q, source) => `/api/books/search?q=${encodeURIComponent(q)}&category=quadrinho${source ? `&source=${encodeURIComponent(source)}` : ""}`,
    resultsKey: "results",
    emptyText: "Digite o nome de uma HQ, edição ou personagem pra buscar.",
  },
};

const el = {
  navItems: document.querySelectorAll(".nav-item, .fab-item"),
  brandHome: document.getElementById("brand-home"),
  mobileFab: document.getElementById("mobile-fab"),
  fabMain: document.getElementById("fab-main"),
  main: document.querySelector(".main"),
  content: document.querySelector(".main .content"),
  viewTitle: document.getElementById("view-title"),
  viewSub: document.getElementById("view-sub"),
  searchbar: document.getElementById("searchbar"),
  searchCategoryToggle: document.getElementById("search-category-toggle"),
  query: document.getElementById("query"),
  sourceSelect: document.getElementById("source-select"),
  libraryToolbar: document.getElementById("library-toolbar"),
  libraryFilterbar: document.getElementById("library-filterbar"),
  libraryQuery: document.getElementById("library-query"),
  libraryKind: document.getElementById("library-kind"),
  libraryViewToggle: document.getElementById("library-view-toggle"),
  librarySections: document.getElementById("library-sections"),
  grid: document.getElementById("grid"),
  stateEmpty: document.getElementById("state-empty"),
  stateLoading: document.getElementById("state-loading"),
  stateError: document.getElementById("state-error"),
  panels: document.querySelectorAll("[data-panel]"),
  template: document.getElementById("card-template"),
  listRowTemplate: document.getElementById("list-row-template"),
  jobRowTemplate: document.getElementById("job-row-template"),
  discoverSources: document.getElementById("discover-sources"),
  discoverBack: document.getElementById("discover-back"),
  sourceGrid: document.getElementById("source-grid"),
  sourceTileTemplate: document.getElementById("source-tile-template"),
  themeToggle: document.getElementById("theme-toggle"),
  updateCheckBtn: document.getElementById("update-check-btn"),
  updateModal: document.getElementById("update-modal"),
  updateClose: document.getElementById("update-close"),
  updateCloseBtn: document.getElementById("update-close-btn"),
  updateStatus: document.getElementById("update-status"),
  updateDownloadLink: document.getElementById("update-download-link"),
  updateInstallBtn: document.getElementById("update-install-btn"),
  updateCancelBtn: document.getElementById("update-cancel-btn"),
  updateProgress: document.getElementById("update-progress"),
  updateProgressBar: document.getElementById("update-progress-bar"),
  themeIcon: document.getElementById("theme-icon"),
  themeSegmented: document.getElementById("theme-segmented"),
  pagination: document.getElementById("pagination"),
  pagePrev: document.getElementById("page-prev"),
  pageNext: document.getElementById("page-next"),
  pageIndicator: document.getElementById("page-indicator"),
  libraryPathInput: document.getElementById("library-path-input"),
  libraryPathBrowse: document.getElementById("library-path-browse"),
  libraryPathSave: document.getElementById("library-path-save"),
  libraryPathHint: document.getElementById("library-path-hint"),
  settingsClearLibrary: document.getElementById("settings-clear-library"),
  settingsClearHint: document.getElementById("settings-clear-hint"),
  statFiles: document.getElementById("stat-files"),
  statSize: document.getElementById("stat-size"),
  downloadsEmpty: document.getElementById("downloads-empty"),
  jobList: document.getElementById("job-list"),
  readerView: document.getElementById("reader-view"),
  detailView: document.getElementById("detail-view"),
  detailBack: document.getElementById("detail-back"),
  detailLayout: document.querySelector(".detail-layout"),
  detailLoading: document.getElementById("detail-loading"),
  detailError: document.getElementById("detail-error"),
  detailCover: document.getElementById("detail-cover"),
  detailSource: document.getElementById("detail-source"),
  detailTitle: document.getElementById("detail-title"),
  detailAuthor: document.getElementById("detail-author"),
  detailMeta: document.getElementById("detail-meta"),
  detailDownload: document.getElementById("detail-download"),
  detailRead: document.getElementById("detail-read"),
  detailSynopsis: document.getElementById("detail-synopsis"),
  readerBack: document.getElementById("reader-back"),
  readerFullscreen: document.getElementById("reader-fullscreen"),
  readerFullscreenExit: document.getElementById("reader-fullscreen-exit"),
  readerTitle: document.getElementById("reader-title"),
  readerToc: document.getElementById("reader-toc"),
  readerViewer: document.getElementById("reader-viewer"),
  readerPrev: document.getElementById("reader-prev"),
  readerNext: document.getElementById("reader-next"),
  readerManga: document.getElementById("reader-manga"),
  readerStrip: document.getElementById("reader-strip"),
  readerPageImg: document.getElementById("reader-page-img"),
  readerPagePrev: document.getElementById("reader-page-prev"),
  readerPageNext: document.getElementById("reader-page-next"),
  readerPageIndicator: document.getElementById("reader-page-indicator"),
  readerPdf: document.getElementById("reader-pdf"),
  readerPdfCanvas: document.getElementById("reader-pdf-canvas"),
  readerPdfIndicator: document.getElementById("reader-pdf-indicator"),
  readerPdfPrev: document.getElementById("reader-pdf-prev"),
  readerPdfNext: document.getElementById("reader-pdf-next"),
  readerPdfStrip: document.getElementById("reader-pdf-strip"),
  readerText: document.getElementById("reader-text"),
  readerEpub: document.getElementById("reader-epub"),
  readerEpubPrev: document.getElementById("reader-epub-prev"),
  readerEpubNext: document.getElementById("reader-epub-next"),
  readerEmpty: document.getElementById("reader-empty"),
  readerZoomOut: document.getElementById("reader-zoom-out"),
  readerZoomLabel: document.getElementById("reader-zoom-label"),
  readerZoomIn: document.getElementById("reader-zoom-in"),
  readerZoomReset: document.getElementById("reader-zoom-reset"),
  readerThemePage: document.getElementById("reader-theme-page"),
  readerTextMode: document.getElementById("reader-text-mode"),
  readerModePages: document.getElementById("reader-mode-pages"),
  readerModeContinuous: document.getElementById("reader-mode-continuous"),
  readerTurnTap: document.getElementById("reader-turn-tap"),
  readerTurnSwipe: document.getElementById("reader-turn-swipe"),
  formatModal: document.getElementById("format-modal"),
  formatClose: document.getElementById("format-close"),
  formatBook: document.getElementById("format-book"),
  formatOptions: document.getElementById("format-options"),
  formatTotal: document.getElementById("format-total"),
  formatCancel: document.getElementById("format-cancel"),
  formatConfirm: document.getElementById("format-confirm"),
  chapterModal: document.getElementById("chapter-modal"),
  chapterClose: document.getElementById("chapter-close"),
  chapterBook: document.getElementById("chapter-book"),
  chapterSelectMissing: document.getElementById("chapter-select-missing"),
  chapterSelectAll: document.getElementById("chapter-select-all"),
  chapterClear: document.getElementById("chapter-clear"),
  chapterOptions: document.getElementById("chapter-options"),
  chapterTotal: document.getElementById("chapter-total"),
  chapterCancel: document.getElementById("chapter-cancel"),
  chapterConfirm: document.getElementById("chapter-confirm"),
};

let currentView = "library";
let viewBeforeReader = "library";
let searchCategory = localStorage.getItem(SEARCH_CATEGORY_KEY) || "manga";
let libraryPage = 1;
let libraryTotalPages = 1;
let discoverSource = null; // {id, name, domain, category} — set while browsing one source's catalog
let discoverPage = 1;
let discoverTotalPages = 1;
let jobPollTimer = null;
let mangaReaderState = null; // { mode, mangaId/bookId, chapterFile, pages, index }
let epubBook = null;
let epubRendition = null;
let currentBookFileUrl = "";
let pdfDoc = null;
let pdfPageNum = 1;
let pdfNumPages = 0;
let pdfRenderTask = null;
let pdfContinuousObserver = null;
let currentReaderItem = null;
let currentPdfText = "";
let readerZoom = 100;
let readerPaperMode = false;
let readerLayoutMode = localStorage.getItem(READER_LAYOUT_KEY) || "pages";
let detailItem = null;
let viewBeforeDetail = "library";
let readingStateSaveTimer = null;

// ---- reading position (resume where you left off, even after quitting) ----
async function fetchReadingState(itemId) {
  try {
    const data = await fetchJSON(`/api/reading-state?id=${encodeURIComponent(itemId)}`);
    return data.state || null;
  } catch (err) {
    console.error("failed to load reading state", err);
    return null;
  }
}

function saveReadingState(itemId, kind, patch) {
  clearTimeout(readingStateSaveTimer);
  readingStateSaveTimer = setTimeout(() => {
    fetchJSON("/api/reading-state", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id: itemId, kind, ...patch }),
    }).catch((err) => console.error("failed to save reading state", err));
  }, 500);
}

// ---- theme ----
function applyTheme(theme) {
  document.documentElement.dataset.theme = theme;
  el.themeIcon.innerHTML = theme === "light" ? ICON_SUN : ICON_MOON;
  el.themeSegmented.querySelectorAll("button").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.themeValue === theme);
  });
}

function getTheme() {
  return localStorage.getItem(THEME_KEY) || "dark";
}

function setTheme(theme) {
  localStorage.setItem(THEME_KEY, theme);
  applyTheme(theme);
}

applyTheme(getTheme());

// ---- update check ----
// build-info.json is a plain static file (not an /api/ route), regenerated
// fresh at build time by release.yml with this specific build's own commit
// — desktop/Android/web dev builds all keep their own copy in assets/web/.
// There's no meaningfully incrementing version number in this project's
// release flow (the same v1.0.0 tag's assets just get replaced on every
// rebuild), so "is there an update" is answered by comparing commits, not
// timestamps: a build-time timestamp and the release asset's "replaced at"
// time are always minutes apart just from how long the CI pipeline takes
// to build+upload, so that comparison flags every single build as
// "outdated" the moment it's done — including compared to itself.
let pendingUpdateApkUrl = null;
const hasAndroidAutoUpdate = () =>
  Boolean(window.SapphireBoxAndroid && typeof window.SapphireBoxAndroid.hasAutoUpdate === "function" && window.SapphireBoxAndroid.hasAutoUpdate());

async function checkForUpdates() {
  el.updateDownloadLink.hidden = true;
  el.updateInstallBtn.hidden = true;
  el.updateInstallBtn.disabled = false;
  el.updateInstallBtn.textContent = "Atualizar agora";
  el.updateCancelBtn.hidden = true;
  el.updateProgress.hidden = true;
  el.updateProgressBar.style.width = "0%";
  el.updateStatus.textContent = "Verificando…";
  pendingUpdateApkUrl = null;
  try {
    const infoRes = await fetch("build-info.json", { cache: "no-store" });
    const info = infoRes.ok ? await infoRes.json() : {};
    const localCommit = info.commit || null;

    const [commitRes, releaseRes] = await Promise.all([
      fetch("https://api.github.com/repos/juankalleo/sapphire-box/commits/main", { cache: "no-store" }),
      fetch("https://api.github.com/repos/juankalleo/sapphire-box/releases/latest", { cache: "no-store" }),
    ]);
    if (!commitRes.ok) throw new Error(`GitHub respondeu ${commitRes.status}`);
    const latestCommit = (await commitRes.json()).sha || null;
    const release = releaseRes.ok ? await releaseRes.json() : { assets: [] };
    const apkAsset = (release.assets || []).find((a) => /\.apk$/i.test(a.name));

    if (!localCommit || localCommit === "dev") {
      el.updateStatus.textContent = `Essa build não tem um commit gravado pra comparar (build de desenvolvimento). Commit mais recente no GitHub: ${latestCommit ? latestCommit.slice(0, 7) : "?"}.`;
      el.updateDownloadLink.hidden = false;
      return;
    }

    if (localCommit === latestCommit) {
      el.updateStatus.textContent = `Você já está na versão mais recente (commit ${localCommit.slice(0, 7)}).`;
      return;
    }

    el.updateStatus.textContent = `Tem atualização disponível. Sua build: ${localCommit.slice(0, 7)} · mais recente: ${latestCommit ? latestCommit.slice(0, 7) : "?"}.`;
    if (hasAndroidAutoUpdate() && apkAsset) {
      pendingUpdateApkUrl = apkAsset.browser_download_url;
      el.updateInstallBtn.hidden = false;
    } else {
      el.updateDownloadLink.hidden = false;
    }
  } catch (err) {
    el.updateStatus.textContent = `Não deu pra checar agora — confira sua internet e tenta de novo. (${err.message})`;
  }
}

function openUpdateModal() {
  el.updateModal.hidden = false;
  checkForUpdates();
}

function closeUpdateModal() {
  if (updateDownloadInProgress) cancelUpdateDownload();
  el.updateModal.hidden = true;
}

el.updateCheckBtn.addEventListener("click", openUpdateModal);
el.updateClose.addEventListener("click", closeUpdateModal);
el.updateCloseBtn.addEventListener("click", closeUpdateModal);

let updateDownloadInProgress = false;

function resetUpdateDownloadUi() {
  updateDownloadInProgress = false;
  el.updateInstallBtn.hidden = !pendingUpdateApkUrl;
  el.updateInstallBtn.disabled = false;
  el.updateInstallBtn.textContent = "Atualizar agora";
  el.updateCancelBtn.hidden = true;
  el.updateProgress.hidden = true;
  el.updateProgressBar.style.width = "0%";
}

function cancelUpdateDownload() {
  if (window.SapphireBoxAndroid && typeof window.SapphireBoxAndroid.cancelUpdateDownload === "function") {
    window.SapphireBoxAndroid.cancelUpdateDownload();
  }
  resetUpdateDownloadUi();
  el.updateStatus.textContent = "Download cancelado.";
}

el.updateInstallBtn.addEventListener("click", () => {
  if (!pendingUpdateApkUrl || !window.SapphireBoxAndroid) return;
  updateDownloadInProgress = true;
  el.updateInstallBtn.hidden = true;
  el.updateCancelBtn.hidden = false;
  el.updateProgress.hidden = false;
  el.updateProgressBar.style.width = "0%";
  el.updateStatus.textContent = "Baixando atualização…";
  window.SapphireBoxAndroid.downloadAndInstallUpdate(pendingUpdateApkUrl);
});

el.updateCancelBtn.addEventListener("click", cancelUpdateDownload);

// Called by MainActivity.kt while the update APK downloads, and if the
// download or the handoff to the system installer fails.
window.onSapphireBoxUpdateProgress = (pct) => {
  if (!updateDownloadInProgress) return;
  el.updateProgressBar.style.width = `${Math.max(0, Math.min(100, pct))}%`;
  el.updateStatus.textContent = pct >= 100 ? "Abrindo o instalador…" : `Baixando atualização… ${pct}%`;
};

window.onSapphireBoxUpdateError = (message) => {
  resetUpdateDownloadUi();
  el.updateStatus.textContent = `Não deu pra atualizar: ${message}`;
};

el.themeToggle.addEventListener("click", () => {
  setTheme(getTheme() === "dark" ? "light" : "dark");
});

el.themeSegmented.addEventListener("click", (evt) => {
  const btn = evt.target.closest("button[data-theme-value]");
  if (btn) setTheme(btn.dataset.themeValue);
});

// ---- helpers ----
function isAndroidApiRequest(url) {
  if (!window.SapphireBoxAndroid) return false;
  try {
    return new URL(url, window.location.href).pathname.startsWith("/api/");
  } catch (err) {
    return false;
  }
}

// A cover is either a remote http(s) URL (search/discover, straight from
// the source's site) or a local disk path (once the item's been
// downloaded) — the latter needs proxying through /api/cover since a bare
// filesystem path isn't something an <img> can fetch on its own.
function resolveCoverSrc(coverPath) {
  if (!coverPath) return null;
  if (/^https?:\/\//.test(coverPath)) return coverPath;
  return `/api/cover?path=${encodeURIComponent(coverPath)}`;
}

// PDFs downloaded with no cover from their source can't get one the same
// way cbz/epub/zip do server-side (extracting the first image from a
// plain zip) — rendering a PDF page needs a real PDF engine, and adding
// one on the Python side is a heavy, Android-risky new dependency this
// app can't safely take on. pdf.js is already loaded for the reader
// itself, so it renders page 1 here instead, once per book, and hands
// the image back to /api/library/books/cover to save — so this only
// costs a full PDF fetch+render the first time a library card for that
// book is shown, not on every subsequent library load.
const pdfCoverAttempts = new Set();

async function tryGeneratePdfCover(item, imgEl) {
  if (item.format !== "pdf" || !item.id || !window.pdfjsLib || pdfCoverAttempts.has(item.id)) return;
  pdfCoverAttempts.add(item.id);
  let doc = null;
  try {
    doc = await window.pdfjsLib.getDocument(`/api/library/books/file?id=${encodeURIComponent(item.id)}`).promise;
    const page = await doc.getPage(1);
    const viewport = page.getViewport({ scale: 0.5 });
    const canvas = document.createElement("canvas");
    canvas.width = viewport.width;
    canvas.height = viewport.height;
    await page.render({ canvasContext: canvas.getContext("2d"), viewport }).promise;
    const dataUrl = canvas.toDataURL("image/jpeg", 0.72);

    const saved = await fetchJSON("/api/library/books/cover", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id: item.id, dataUrl }),
    });
    item.coverPath = saved.coverPath;
    if (imgEl && imgEl.isConnected) {
      imgEl.src = resolveCoverSrc(saved.coverPath);
      imgEl.style.display = "";
    }
  } catch (err) {
    console.error("pdf cover generation failed", err);
  } finally {
    if (doc) doc.destroy();
  }
}

function bytesFromBase64(value) {
  const raw = atob(value || "");
  const bytes = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i += 1) {
    bytes[i] = raw.charCodeAt(i);
  }
  return bytes;
}

async function apiFetch(url, options = {}) {
  if (!isAndroidApiRequest(url)) return fetch(url, options);
  const payload = {
    method: (options.method || "GET").toUpperCase(),
    url: new URL(url, window.location.href).pathname + new URL(url, window.location.href).search,
    body: options.body || null,
  };
  const raw = window.SapphireBoxAndroid.request(JSON.stringify(payload));
  const response = JSON.parse(raw);
  const body = response.bodyBase64 ? bytesFromBase64(response.bodyBase64) : (response.body || "");
  return new Response(body, {
    status: response.status || 200,
    statusText: response.statusText || "OK",
    headers: response.headers || {},
  });
}

async function fetchJSON(url, options) {
  const res = await apiFetch(url, options);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `${res.status} ${res.statusText}`);
  }
  return res.json();
}

function formatBytes(bytes) {
  if (!bytes) return "0 MB";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let value = bytes;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit += 1;
  }
  return `${value.toFixed(unit === 0 ? 0 : 1)} ${units[unit]}`;
}

function compactText(value) {
  return (value || "").toString().replace(/\s+/g, " ").trim();
}

function fileOptionsFor(item) {
  const options = Array.isArray(item.fileOptions) ? item.fileOptions.filter((o) => o && o.format) : [];
  if (options.length > 0) {
    return options.map((option) => ({
      format: option.format.toLowerCase(),
      label: option.label || option.format.toUpperCase(),
      sizeBytes: option.sizeBytes || 0,
      sizeLabel: option.sizeLabel || (option.sizeBytes ? formatBytes(option.sizeBytes) : ""),
    }));
  }
  if (item.format) {
    return [{
      format: item.format.toLowerCase(),
      label: item.format.toUpperCase(),
      sizeBytes: item.fileSizeBytes || 0,
      sizeLabel: item.fileSizeBytes ? formatBytes(item.fileSizeBytes) : "",
    }];
  }
  return [];
}

function lightestFormat(options) {
  const known = options.filter((option) => option.sizeBytes > 0);
  if (known.length === 0) return null;
  return known.reduce((best, option) => (option.sizeBytes < best.sizeBytes ? option : best), known[0]);
}

function setState(kind, message) {
  el.stateEmpty.hidden = kind !== "empty";
  el.stateLoading.hidden = kind !== "loading";
  el.stateError.hidden = kind !== "error";
  el.grid.hidden = kind === "loading" || kind === "error" || kind === "empty";
  if (kind === "empty") el.stateEmpty.querySelector(".desc").textContent = message;
  if (kind === "error") el.stateError.querySelector(".desc").textContent = message;
}

function domainFor(item) {
  return item.kind === "book" ? "books" : "manga";
}

function cardPillText(item) {
  // Language matters most for a multi-language source like Library
  // Genesis, where one search mixes Portuguese/English/Spanish/etc. — so
  // it always shows here, not just on the details screen, right where
  // someone decides whether to open a result at all.
  const bits = [item.sourceName || item.sourceId || ""];
  if (item.author) bits.push(item.author);
  if (item.language) bits.push(item.language);
  return bits.filter(Boolean).join(" · ");
}

function formatForItem(item) {
  const fmt = (item.format || "").toLowerCase();
  if (fmt) return fmt;
  const match = (item.localPath || "").match(/\.([^.\\/]+)$/);
  return match ? match[1].toLowerCase() : "";
}

function isComicItem(item) {
  return domainFor(item) === "books" && (
    item.sourceCategory === "quadrinho" ||
    item.category === "quadrinho" ||
    (currentView === "search" && searchCategory === "quadrinho") ||
    discoverSource?.category === "quadrinho" ||
    ["cbz", "cbr"].includes(formatForItem(item))
  );
}

// ---- cards: "search" mode shows a Baixar button, "library" mode makes
// the whole card open the reader instead. `container` defaults to the
// flat search/discover #grid; library mode renders into a per-group
// container instead (cards grid or horizontally-scrolling shelf). ----
function renderCards(items, mode, container = el.grid) {
  container.innerHTML = "";
  for (const item of items) {
    const domain = domainFor(item);
    const node = el.template.content.cloneNode(true);
    const card = node.querySelector(".card");
    const img = node.querySelector("img");
    const badgeIcon = node.querySelector(".domain-badge svg");
    const title = node.querySelector(".card-title");
    const pill = node.querySelector(".card-pill");
    const actionBtn = node.querySelector(".card-open");
    const actions = node.querySelector(".card-actions");
    const menuBtn = node.querySelector(".card-menu");

    title.textContent = item.title || "Sem título";
    pill.textContent = cardPillText(item);
    badgeIcon.innerHTML = domain === "manga" ? ICON_MANGA : ICON_BOOKS;

    const coverSrc = resolveCoverSrc(item.coverPath);
    if (coverSrc) {
      img.src = coverSrc;
      img.alt = title.textContent;
      img.onerror = () => { img.remove(); };
    } else if (mode === "library" && item.format === "pdf") {
      img.style.display = "none";
      tryGeneratePdfCover(item, img);
    } else {
      img.remove();
    }

    card.classList.add("card-clickable");

    if (mode === "library") {
      card.addEventListener("click", () => openReader(item));
      menuBtn.hidden = false;
      menuBtn.addEventListener("click", (evt) => {
        evt.stopPropagation();
        deleteLibraryItem(item);
      });
      actions.classList.add("card-actions-dual");
      actionBtn.textContent = "Ler";
      actionBtn.addEventListener("click", (evt) => {
        evt.stopPropagation();
        openReader(item);
      });

      const detailsBtn = document.createElement("button");
      detailsBtn.type = "button";
      detailsBtn.className = "card-open card-details";
      detailsBtn.textContent = "Detalhes";
      detailsBtn.addEventListener("click", (evt) => {
        evt.stopPropagation();
        openDetails(item);
      });
      actions.appendChild(detailsBtn);
    } else {
      card.addEventListener("click", () => openDetails(item));
      actionBtn.textContent = "Baixar";
      actionBtn.addEventListener("click", (evt) => {
        evt.stopPropagation();
        downloadWithChoice(item);
      });
    }

    container.appendChild(node);
  }
}

async function deleteLibraryItem(item) {
  const kind = domainFor(item) === "manga" ? "manga" : "book";
  const title = item.title || "este item";
  if (!confirm(`Apagar "${title}" da biblioteca e remover os arquivos baixados do disco?`)) return;
  try {
    const params = new URLSearchParams({ kind, id: item.id });
    const data = await fetchJSON(`/api/library/item?${params.toString()}`, { method: "DELETE" });
    el.statFiles.textContent = String(data.stats.fileCount);
    el.statSize.textContent = formatBytes(data.stats.totalBytes);
    await loadLibraryPage();
  } catch (err) {
    alert(`Não deu pra apagar: ${err.message}`);
  }
}

async function populateSources(view) {
  el.sourceSelect.innerHTML = "";
  const allOpt = document.createElement("option");
  allOpt.value = "";
  allOpt.textContent = "Todas as fontes";
  el.sourceSelect.appendChild(allOpt);

  try {
    const sources = await fetchJSON(view.sourcesUrl);
    for (const s of sources) {
      if (s.implemented === false) continue;
      const opt = document.createElement("option");
      opt.value = s.id;
      opt.textContent = s.name;
      el.sourceSelect.appendChild(opt);
    }
  } catch (err) {
    console.error("failed to load sources", err);
  }
}

async function runSearch(view) {
  const q = el.query.value.trim();
  if (!q) {
    setState("empty", view.emptyText);
    return;
  }
  setState("loading");
  try {
    const data = await fetchJSON(view.searchUrl(q, el.sourceSelect.value));
    const items = data[view.resultsKey] || [];
    if (items.length === 0) {
      setState("empty", "Nenhum resultado.");
      return;
    }
    setState(null);
    renderCards(items, "search");
  } catch (err) {
    setState("error", err.message);
  }
}

async function setSearchCategory(category) {
  searchCategory = category;
  localStorage.setItem(SEARCH_CATEGORY_KEY, category);
  el.searchCategoryToggle.querySelectorAll("button").forEach((b) => {
    b.classList.toggle("active", b.dataset.searchCategory === category);
  });
  el.query.value = "";
  const meta = SEARCH_CATEGORIES[category];
  await populateSources(meta);
  setState("empty", meta.emptyText);
}

el.searchCategoryToggle.addEventListener("click", (evt) => {
  const btn = evt.target.closest("button[data-search-category]");
  if (btn) setSearchCategory(btn.dataset.searchCategory);
});

// ---- details: every card opens a richer item page before reading/downloading ----
function detailsUrlFor(item) {
  const params = new URLSearchParams({
    source: item.sourceId || "",
    id: item.id || "",
  });
  if (item.title) params.set("title", item.title);
  if (item.sourceName) params.set("sourceName", item.sourceName);
  if (item.author) params.set("author", item.author);
  if (item.coverPath) params.set("coverPath", item.coverPath);
  if (item.format) params.set("format", item.format);
  return domainFor(item) === "manga" ? `/api/manga/details?${params.toString()}` : `/api/books/details?${params.toString()}`;
}

async function fetchDetails(item) {
  if (!item.sourceId || item.sourceId === "local") return item;
  return fetchJSON(detailsUrlFor(item));
}

function setDetailLoading() {
  el.detailLayout.hidden = true;
  el.detailLoading.hidden = false;
  el.detailError.hidden = true;
}

function setDetailReady() {
  el.detailLayout.hidden = false;
  el.detailLoading.hidden = true;
  el.detailError.hidden = true;
}

function setDetailError(message) {
  el.detailLoading.hidden = true;
  el.detailError.hidden = false;
  el.detailError.querySelector(".desc").textContent = message;
}

function addDetailMeta(label, value) {
  const clean = compactText(value);
  if (!clean) return;
  const item = document.createElement("div");
  item.className = "detail-meta-item";
  item.innerHTML = `<span class="detail-meta-label"></span><span class="detail-meta-value"></span>`;
  item.querySelector(".detail-meta-label").textContent = label;
  item.querySelector(".detail-meta-value").textContent = clean;
  el.detailMeta.appendChild(item);
}

function renderDetails(item) {
  detailItem = item;
  const domain = domainFor(item);
  const options = fileOptionsFor(item);
  const optionText = options.map((option) => {
    const size = option.sizeLabel || (option.sizeBytes ? formatBytes(option.sizeBytes) : "");
    return size ? `${option.label} ${size}` : option.label;
  }).join(" / ");

  const coverBox = el.detailCover.closest(".detail-cover");
  const detailCoverSrc = resolveCoverSrc(item.coverPath);
  if (detailCoverSrc) {
    coverBox.hidden = false;
    el.detailCover.src = detailCoverSrc;
    el.detailCover.alt = item.title || "";
    el.detailCover.onerror = () => { coverBox.hidden = true; };
  } else {
    coverBox.hidden = true;
    el.detailCover.removeAttribute("src");
  }

  el.detailSource.textContent = item.sourceName || item.sourceId || (domain === "manga" ? "Mangá" : "Livro");
  el.detailTitle.textContent = item.title || "Sem título";
  el.detailAuthor.textContent = item.author ? `por ${item.author}` : "";
  el.detailAuthor.hidden = !item.author;
  el.detailSynopsis.textContent = compactText(item.synopsis);
  el.detailMeta.innerHTML = "";

  addDetailMeta("Tipo", domain === "manga" ? "Mangá" : "Livro");
  addDetailMeta("Fonte", item.sourceName || item.sourceId);
  if (domain === "manga") {
    addDetailMeta("Capítulos", item.totalChapters || item.downloadedChapters);
    addDetailMeta("Status", item.status && item.status !== "unknown" ? item.status : "");
  } else {
    addDetailMeta("Formatos", optionText || (item.format || "").toUpperCase());
    addDetailMeta("Páginas", item.pages);
    addDetailMeta("Tamanho", item.fileSizeBytes ? formatBytes(item.fileSizeBytes) : "");
    addDetailMeta("Idioma", item.language);
    addDetailMeta("Ano", item.year);
    addDetailMeta("Categoria", item.category);
  }

  const isDownloaded = Boolean(item.localPath);
  el.detailRead.hidden = !isDownloaded;
  el.detailDownload.hidden = isDownloaded;
  el.detailDownload.onclick = () => downloadWithChoice(detailItem);
  el.detailRead.onclick = () => openReader(detailItem);
}

async function openDetails(item) {
  viewBeforeDetail = currentView;
  detailItem = item;
  el.content.hidden = true;
  el.readerView.hidden = true;
  el.detailView.hidden = false;
  setDetailLoading();
  try {
    const detailed = await fetchDetails(item);
    renderDetails({ ...item, ...detailed, localPath: item.localPath || detailed.localPath });
    setDetailReady();
  } catch (err) {
    renderDetails(item);
    setDetailReady();
    setDetailError(err.message);
  }
}

function closeDetails() {
  detailItem = null;
  el.detailView.hidden = true;
  el.content.hidden = false;
  switchView(viewBeforeDetail);
}

el.detailBack.addEventListener("click", closeDetails);

// ---- downloads: start a job from a search result, then jump to the
// Downloads view so the progress bar is the very next thing you see. ----
async function startDownload(item, selectedFormat = null, selectedChapters = null) {
  try {
    if (domainFor(item) === "manga") {
      await fetchJSON("/api/manga/download", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          sourceId: item.sourceId,
          sourceName: item.sourceName,
          mangaId: item.id,
          title: item.title,
          coverPath: item.coverPath,
          chapters: selectedChapters || "all",
          format: "cbz",
        }),
      });
    } else {
      await fetchJSON("/api/books/download", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          sourceId: item.sourceId,
          sourceName: item.sourceName,
          bookId: item.id,
          title: item.title,
          author: item.author,
          coverPath: item.coverPath,
          format: selectedFormat || item.format,
        }),
      });
    }
    if (!el.detailView.hidden) {
      el.detailView.hidden = true;
      el.content.hidden = false;
    }
    switchView("downloads");
  } catch (err) {
    alert(`Não deu pra iniciar o download: ${err.message}`);
  }
}

function openFormatModal(item, options) {
  return new Promise((resolve) => {
    const lightest = lightestFormat(options);
    let selected = lightest?.format || options[0]?.format || item.format;

    function renderOptions() {
      el.formatOptions.innerHTML = "";
      for (const option of options) {
        const row = document.createElement("label");
        row.className = "format-option";
        row.classList.toggle("selected", option.format === selected);
        const size = option.sizeLabel || (option.sizeBytes ? formatBytes(option.sizeBytes) : "tamanho desconhecido");
        const badge = lightest && lightest.format === option.format ? `<span class="format-option-badge">mais leve</span>` : "";
        row.innerHTML = `
          <input type="radio" name="download-format" value="">
          <span class="format-option-title"><span class="format-option-name"></span>${badge}</span>
          <span class="format-option-size"></span>
        `;
        const input = row.querySelector("input");
        input.value = option.format;
        input.checked = option.format === selected;
        row.querySelector(".format-option-name").textContent = option.label || option.format.toUpperCase();
        row.querySelector(".format-option-size").textContent = size;
        row.addEventListener("click", () => {
          selected = option.format;
          renderOptions();
        });
        el.formatOptions.appendChild(row);
      }
    }

    function cleanup(value) {
      el.formatModal.hidden = true;
      el.formatConfirm.onclick = null;
      el.formatCancel.onclick = null;
      el.formatClose.onclick = null;
      resolve(value);
    }

    el.formatBook.textContent = item.title || "Sem título";
    el.formatTotal.textContent = lightest ? `Menor arquivo: ${(lightest.label || lightest.format.toUpperCase())} · ${lightest.sizeLabel || formatBytes(lightest.sizeBytes)}` : "";
    renderOptions();
    el.formatModal.hidden = false;
    el.formatConfirm.onclick = () => cleanup(selected);
    el.formatCancel.onclick = () => cleanup(null);
    el.formatClose.onclick = () => cleanup(null);
  });
}

async function downloadWithFormatChoice(item) {
  try {
    const detailed = domainFor(item) === "books" ? { ...item, ...(await fetchDetails(item)) } : item;
    if (isComicItem(detailed)) {
      const ok = confirm("Esse quadrinho vem como arquivo único nessa fonte. O app só consegue baixar tudo, sem escolher capítulos. Continuar?");
      if (!ok) return;
    }
    const options = fileOptionsFor(detailed);
    let selectedFormat = options[0]?.format || detailed.format;
    if (options.length > 1) {
      selectedFormat = await openFormatModal(detailed, options);
      if (!selectedFormat) return;
    }
    await startDownload({ ...item, ...detailed, format: selectedFormat }, selectedFormat);
  } catch (err) {
    alert(`Não deu pra preparar o download: ${err.message}`);
  }
}

function normalizeChapterOptions(chapters) {
  return (Array.isArray(chapters) ? chapters : [])
    .map((chapter, idx) => ({
      index: Number(chapter.index) || idx + 1,
      label: compactText(chapter.label) || String(Number(chapter.index) || idx + 1),
      downloaded: Boolean(chapter.downloaded),
    }))
    .filter((chapter) => chapter.index > 0);
}

async function chapterOptionsFor(item) {
  let detailed = item;
  let detailsError = null;
  if (item.chapterOptions?.length) {
    detailed = item;
  } else {
    try {
      detailed = { ...item, ...(await fetchDetails(item)) };
    } catch (err) {
      detailsError = err;
    }
  }
  let chapters = normalizeChapterOptions(detailed.chapterOptions);
  if (chapters.length === 0 && item.sourceId && item.id) {
    const params = new URLSearchParams({ source: item.sourceId, id: item.id });
    try {
      const data = await fetchJSON(`/api/manga/chapter-options?${params.toString()}`);
      chapters = normalizeChapterOptions(data.chapters);
    } catch (err) {
      if (detailsError) {
        throw new Error(`${detailsError.message}; capítulos: ${err.message}`);
      }
      throw err;
    }
  }
  return { detailed, chapters };
}

function openChapterModal(item, chapters) {
  return new Promise((resolve) => {
    const normalized = normalizeChapterOptions(chapters);
    const selected = new Set(normalized.filter((chapter) => !chapter.downloaded).map((chapter) => chapter.index));

    function setSelection(values) {
      selected.clear();
      for (const value of values) selected.add(value);
      renderOptions();
    }

    function renderOptions() {
      const downloadedCount = normalized.filter((chapter) => chapter.downloaded).length;
      el.chapterOptions.innerHTML = "";

      for (const chapter of normalized) {
        const row = document.createElement("label");
        row.className = "chapter-option";
        row.classList.toggle("selected", selected.has(chapter.index));
        row.classList.toggle("downloaded", chapter.downloaded);

        const input = document.createElement("input");
        input.type = "checkbox";
        input.checked = selected.has(chapter.index);
        input.addEventListener("change", () => {
          if (input.checked) selected.add(chapter.index);
          else selected.delete(chapter.index);
          renderOptions();
        });

        const title = document.createElement("span");
        title.className = "chapter-option-title";
        title.textContent = `Capítulo ${chapter.label}`;

        const badge = document.createElement("span");
        badge.className = "chapter-option-badge";
        badge.textContent = chapter.downloaded ? "baixado" : "novo";

        row.append(input, title, badge);
        el.chapterOptions.appendChild(row);
      }

      const selectedCount = selected.size;
      const missingCount = normalized.length - downloadedCount;
      el.chapterTotal.textContent =
        `${selectedCount} selecionado${selectedCount === 1 ? "" : "s"} · ` +
        `${downloadedCount} já baixado${downloadedCount === 1 ? "" : "s"} · ` +
        `${missingCount} novo${missingCount === 1 ? "" : "s"}`;
    }

    function cleanup(value) {
      el.chapterModal.hidden = true;
      el.chapterConfirm.onclick = null;
      el.chapterCancel.onclick = null;
      el.chapterClose.onclick = null;
      el.chapterSelectMissing.onclick = null;
      el.chapterSelectAll.onclick = null;
      el.chapterClear.onclick = null;
      resolve(value);
    }

    el.chapterBook.textContent = item.title || "Sem título";
    renderOptions();
    el.chapterModal.hidden = false;
    el.chapterSelectMissing.onclick = () => setSelection(normalized.filter((chapter) => !chapter.downloaded).map((chapter) => chapter.index));
    el.chapterSelectAll.onclick = () => setSelection(normalized.map((chapter) => chapter.index));
    el.chapterClear.onclick = () => setSelection([]);
    el.chapterConfirm.onclick = () => {
      if (selected.size === 0) {
        el.chapterTotal.textContent = "Escolha pelo menos um capítulo.";
        return;
      }
      cleanup([...selected].sort((a, b) => a - b).join(","));
    };
    el.chapterCancel.onclick = () => cleanup(null);
    el.chapterClose.onclick = () => cleanup(null);
  });
}

async function downloadWithChapterChoice(item) {
  try {
    const { detailed, chapters } = await chapterOptionsFor(item);
    if (chapters.length === 0) {
      await startDownload({ ...item, ...detailed }, null, "all");
      return;
    }
    const selectedChapters = await openChapterModal({ ...item, ...detailed }, chapters);
    if (!selectedChapters) return;
    await startDownload({ ...item, ...detailed }, null, selectedChapters);
  } catch (err) {
    alert(`Não deu pra preparar os capítulos: ${err.message}`);
  }
}

function downloadWithChoice(item) {
  if (domainFor(item) === "manga") {
    return downloadWithChapterChoice(item);
  }
  return downloadWithFormatChoice(item);
}

const JOB_STATUS_LABEL = {
  pending: "na fila",
  running: "baixando",
  manual_required: "ação manual",
  completed: "concluído",
  cancelled: "cancelado",
  error: "falhou",
};
const JOB_ACTIVE_STATUSES = ["pending", "running"];

function renderJobs(jobs) {
  el.downloadsEmpty.hidden = jobs.length > 0;
  el.jobList.hidden = jobs.length === 0;
  el.jobList.innerHTML = "";

  for (const job of jobs.slice().reverse()) {
    const node = el.jobRowTemplate.content.cloneNode(true);
    const row = node.querySelector(".job-row");
    const img = node.querySelector(".job-cover img");
    const title = node.querySelector(".job-title");
    const status = node.querySelector(".job-status");
    const bar = node.querySelector(".job-bar-fill");
    const meta = node.querySelector(".job-meta");
    const readBtn = node.querySelector(".job-read");
    const manualBtn = node.querySelector(".job-manual");
    const importBtn = node.querySelector(".job-import");
    const cancelBtn = node.querySelector(".job-cancel");
    const retryBtn = node.querySelector(".job-retry");
    const deleteBtn = node.querySelector(".job-delete");

    const active = JOB_ACTIVE_STATUSES.includes(job.status);

    title.textContent = job.title || "Sem título";
    status.textContent = JOB_STATUS_LABEL[job.status] || job.status;
    status.classList.toggle("completed", job.status === "completed");
    status.classList.toggle("error", job.status === "error");
    status.classList.toggle("cancelled", job.status === "cancelled");
    status.classList.toggle("manual", job.status === "manual_required");
    row.classList.toggle("error", job.status === "error");
    row.classList.toggle("cancelled", job.status === "cancelled");
    row.classList.toggle("manual", job.status === "manual_required");
    bar.style.width = `${job.status === "completed" ? 100 : job.progress || 0}%`;
    meta.textContent = job.status === "error" ? job.error : (job.lastStdout || "");

    const jobCoverSrc = resolveCoverSrc(job.coverPath);
    if (jobCoverSrc) {
      img.src = jobCoverSrc;
      img.onerror = () => { img.remove(); };
    } else {
      img.remove();
    }

    cancelBtn.hidden = !active;
    readBtn.hidden = job.status !== "completed" || !job.dest || !job.itemId;
    manualBtn.hidden = job.status !== "manual_required" || !job.manualUrl;
    importBtn.hidden = job.status !== "manual_required";
    retryBtn.hidden = active || job.status === "completed" || job.status === "manual_required";
    readBtn.addEventListener("click", () => openReader(jobToLibraryItem(job)));
    manualBtn.addEventListener("click", () => openManualJob(job.id));
    importBtn.addEventListener("click", () => importManualJob(job.id));
    cancelBtn.addEventListener("click", () => cancelJob(job.id));
    retryBtn.addEventListener("click", () => retryJob(job.id));
    deleteBtn.addEventListener("click", () => deleteJob(job.id));

    el.jobList.appendChild(node);
  }
}

async function openManualJob(jobId) {
  try {
    await fetchJSON(`/api/jobs/${jobId}/open-manual`, { method: "POST" });
  } catch (err) {
    alert(`Não deu pra abrir no navegador: ${err.message}`);
  }
}

async function importManualJob(jobId) {
  try {
    await fetchJSON(`/api/jobs/${jobId}/import-manual`, { method: "POST" });
    refreshJobs();
    loadLibrary();
  } catch (err) {
    alert(`Não encontrei o arquivo baixado ainda: ${err.message}`);
  }
}

function jobToLibraryItem(job) {
  const isBook = job.domain === "book";
  return {
    kind: isBook ? "book" : "manga",
    id: job.itemId,
    title: job.title || "Sem título",
    author: job.author || "",
    sourceId: job.sourceId || "local",
    sourceName: job.sourceName || job.sourceId || "Local",
    coverPath: job.coverPath || "",
    format: isBook ? (job.format || "") : "cbz",
    localPath: job.dest || "",
  };
}

async function cancelJob(jobId) {
  try {
    await fetchJSON(`/api/jobs/${jobId}/cancel`, { method: "POST" });
    refreshJobs();
  } catch (err) {
    console.error("failed to cancel job", err);
  }
}

async function retryJob(jobId) {
  try {
    await fetchJSON(`/api/jobs/${jobId}/retry`, { method: "POST" });
    refreshJobs();
  } catch (err) {
    alert(`Não deu pra tentar de novo: ${err.message}`);
  }
}

async function deleteJob(jobId) {
  try {
    await fetchJSON(`/api/jobs/${jobId}`, { method: "DELETE" });
    refreshJobs();
  } catch (err) {
    console.error("failed to delete job", err);
  }
}

async function refreshJobs() {
  try {
    const data = await fetchJSON("/api/jobs");
    const jobs = data.jobs || [];
    renderJobs(jobs);
    const hasActive = jobs.some((job) => JOB_ACTIVE_STATUSES.includes(job.status));
    if (hasActive && currentView === "downloads" && !jobPollTimer) {
      jobPollTimer = setInterval(refreshJobs, JOB_POLL_MS);
    } else if (!hasActive) {
      stopJobPolling();
    }
  } catch (err) {
    console.error("failed to refresh jobs", err);
  }
}

function startJobPolling() {
  stopJobPolling();
  refreshJobs();
}

function stopJobPolling() {
  if (jobPollTimer) {
    clearInterval(jobPollTimer);
    jobPollTimer = null;
  }
}

// ---- unified library ----
function updatePagination(page, totalPages) {
  el.pagination.hidden = totalPages <= 1;
  el.pageIndicator.textContent = `página ${page} de ${totalPages}`;
  el.pagePrev.disabled = page <= 1;
  el.pageNext.disabled = page >= totalPages;
}

// ---- library: grouped by kind (Mangás & Manhwas / Quadrinhos / Livros),
// each group shown as cards, a horizontal shelf, or a compact list —
// whichever the user picked last (remembered in localStorage). ----
const LIBRARY_VIEW_KEY = "sapphirebox-library-view";
const LIBRARY_GROUPS = [
  { key: "manga", label: "Mangás & Manhwas" },
  { key: "quadrinho", label: "Quadrinhos" },
  { key: "livro", label: "Livros" },
];
let libraryViewMode = localStorage.getItem(LIBRARY_VIEW_KEY) || "cards";
let lastLibraryItems = [];

function libraryGroupFor(item) {
  if (domainFor(item) === "manga") return "manga";
  return isComicItem(item) ? "quadrinho" : "livro";
}

function renderListRow(item, container) {
  const node = el.listRowTemplate.content.cloneNode(true);
  const img = node.querySelector("img");
  const title = node.querySelector(".list-row-title");
  const pill = node.querySelector(".list-row-pill");
  const openBtn = node.querySelector(".list-row-open");
  const menuBtn = node.querySelector(".list-row-menu");
  const row = node.querySelector(".list-row");

  title.textContent = item.title || "Sem título";
  pill.textContent = cardPillText(item);

  const listCoverSrc = resolveCoverSrc(item.coverPath);
  if (listCoverSrc) {
    img.src = listCoverSrc;
    img.alt = title.textContent;
    img.onerror = () => { img.remove(); };
  } else if (item.format === "pdf") {
    img.style.display = "none";
    tryGeneratePdfCover(item, img);
  } else {
    img.remove();
  }

  openBtn.textContent = "Ler";
  openBtn.addEventListener("click", (evt) => {
    evt.stopPropagation();
    openReader(item);
  });
  menuBtn.hidden = false;
  menuBtn.addEventListener("click", (evt) => {
    evt.stopPropagation();
    deleteLibraryItem(item);
  });
  row.classList.add("card-clickable");
  row.addEventListener("click", () => openReader(item));

  container.appendChild(node);
}

function renderLibraryGroups(items) {
  el.librarySections.innerHTML = "";
  const byGroup = new Map();
  for (const item of items) {
    const key = libraryGroupFor(item);
    if (!byGroup.has(key)) byGroup.set(key, []);
    byGroup.get(key).push(item);
  }

  for (const { key, label } of LIBRARY_GROUPS) {
    const groupItems = byGroup.get(key);
    if (!groupItems || groupItems.length === 0) continue;

    const section = document.createElement("section");
    section.className = "library-section";
    const heading = document.createElement("h2");
    heading.className = "library-section-title";
    heading.textContent = `${label} · ${groupItems.length}`;
    section.appendChild(heading);

    if (libraryViewMode === "list") {
      const list = document.createElement("div");
      list.className = "list";
      for (const item of groupItems) renderListRow(item, list);
      section.appendChild(list);
    } else {
      const wrap = document.createElement("div");
      wrap.className = libraryViewMode === "shelf" ? "shelf" : "grid";
      renderCards(groupItems, "library", wrap);
      section.appendChild(wrap);
    }

    el.librarySections.appendChild(section);
  }
}

function setLibraryViewMode(mode) {
  libraryViewMode = mode;
  localStorage.setItem(LIBRARY_VIEW_KEY, mode);
  el.libraryViewToggle.querySelectorAll("button").forEach((b) => {
    b.classList.toggle("active", b.dataset.libraryView === mode);
  });
  if (currentView === "library" && lastLibraryItems.length > 0) renderLibraryGroups(lastLibraryItems);
}

el.libraryViewToggle.addEventListener("click", (evt) => {
  const btn = evt.target.closest("button[data-library-view]");
  if (btn) setLibraryViewMode(btn.dataset.libraryView);
});
setLibraryViewMode(libraryViewMode);

async function loadLibraryPage() {
  el.librarySections.hidden = true;
  setState("loading");
  el.pagination.hidden = true;
  try {
    const q = el.libraryQuery.value.trim();
    const kind = el.libraryKind.value;
    const params = new URLSearchParams({ q, kind, page: String(libraryPage), pageSize: "1000" });
    const data = await fetchJSON(`/api/library?${params.toString()}`);
    libraryTotalPages = data.totalPages || 1;
    if (!data.items || data.items.length === 0) {
      setState("empty", "Baixe alguma coisa numa das buscas — aparece aqui na hora.");
      return;
    }
    setState(null);
    el.grid.hidden = true;
    el.librarySections.hidden = false;
    lastLibraryItems = data.items;
    renderLibraryGroups(data.items);
    updatePagination(libraryPage, libraryTotalPages);
  } catch (err) {
    setState("error", err.message);
  }
}

el.libraryFilterbar.addEventListener("submit", (evt) => {
  evt.preventDefault();
  libraryPage = 1;
  loadLibraryPage();
});
el.pagePrev.addEventListener("click", () => {
  if (discoverSource) {
    if (discoverPage > 1) { discoverPage -= 1; loadDiscoverPage(); }
  } else if (libraryPage > 1) {
    libraryPage -= 1;
    loadLibraryPage();
  }
});
el.pageNext.addEventListener("click", () => {
  if (discoverSource) {
    if (discoverPage < discoverTotalPages) { discoverPage += 1; loadDiscoverPage(); }
  } else if (libraryPage < libraryTotalPages) {
    libraryPage += 1;
    loadLibraryPage();
  }
});

// ---- discover: a grid of every live source, click one to browse its
// catalog straight away (no query needed) with real search + pagination ----
async function loadDiscoverSources() {
  el.sourceGrid.innerHTML = "";
  try {
    const sources = await fetchJSON("/api/sources");
    for (const s of sources) {
      const node = el.sourceTileTemplate.content.cloneNode(true);
      const icon = node.querySelector(".source-tile-icon");
      const iconSvg = icon.querySelector("svg");
      const iconImg = icon.querySelector("img");
      iconSvg.innerHTML = s.domain === "manga" ? ICON_MANGA : ICON_BOOKS;
      if (s.faviconPath) {
        iconImg.src = s.faviconPath;
        iconImg.hidden = false;
        iconSvg.hidden = true;
        iconImg.onerror = () => {
          iconImg.hidden = true;
          iconSvg.hidden = false;
        };
      }
      node.querySelector(".source-tile-name").textContent = s.name;
      node.querySelector(".source-tile-meta").textContent =
        s.category === "quadrinho" ? "Quadrinhos" : s.category === "livro" ? "Livros" : "Mangás";
      node.querySelector(".source-tile").addEventListener("click", () => openDiscoverSource(s));
      el.sourceGrid.appendChild(node);
    }
  } catch (err) {
    el.sourceGrid.innerHTML = `<p class="muted">Falha ao carregar fontes: ${err.message}</p>`;
  }
}

function discoverSearchUrl(source, q, page) {
  if (source.domain === "manga") {
    return `/api/manga/search?source=${encodeURIComponent(source.id)}&q=${encodeURIComponent(q)}&page=${page}`;
  }
  return `/api/books/search?source=${encodeURIComponent(source.id)}&q=${encodeURIComponent(q)}&category=${encodeURIComponent(source.category)}&page=${page}`;
}

function openDiscoverSource(source) {
  discoverSource = source;
  discoverPage = 1;
  el.discoverSources.hidden = true;
  el.discoverBack.hidden = false;
  el.searchbar.hidden = false;
  el.sourceSelect.hidden = true;
  el.query.value = "";
  el.viewTitle.textContent = source.name;
  el.viewSub.hidden = false;
  el.viewSub.textContent = "Catálogo ao vivo dessa fonte — já mostra capas mesmo sem pesquisar. Digite algo pra filtrar.";
  loadDiscoverPage();
}

function closeDiscoverSource() {
  discoverSource = null;
  el.discoverBack.hidden = true;
  el.searchbar.hidden = true;
  el.sourceSelect.hidden = false;
  el.pagination.hidden = true;
  el.viewTitle.textContent = views.discover.title;
  el.viewSub.textContent = views.discover.sub;
  el.grid.innerHTML = "";
  el.discoverSources.hidden = false;
  setState(null);
}

async function loadDiscoverPage() {
  if (!discoverSource) return;
  setState("loading");
  el.pagination.hidden = true;
  try {
    const q = el.query.value.trim();
    const data = await fetchJSON(discoverSearchUrl(discoverSource, q, discoverPage));
    const items = data.results || [];
    discoverTotalPages = data.totalPages || 1;
    if (items.length === 0) {
      setState("empty", q ? "Nenhum resultado pra essa busca nessa fonte." : "Essa fonte não devolveu nada agora — tenta de novo em instantes.");
      return;
    }
    setState(null);
    renderCards(items, "search");
    updatePagination(discoverPage, discoverTotalPages);
  } catch (err) {
    setState("error", err.message);
  }
}

el.discoverBack.addEventListener("click", closeDiscoverSource);

// ---- settings ----
async function loadSettings() {
  try {
    const data = await fetchJSON("/api/settings");
    el.libraryPathInput.value = data.libraryPath;
    el.statFiles.textContent = String(data.stats.fileCount);
    el.statSize.textContent = formatBytes(data.stats.totalBytes);
    el.libraryPathHint.textContent = "";
  } catch (err) {
    el.libraryPathHint.textContent = `Falha ao carregar: ${err.message}`;
  }
}

async function saveLibraryPath(path) {
  if (!path) return;
  el.libraryPathInput.value = path;
  el.libraryPathHint.textContent = "Salvando…";
  try {
    const data = await fetchJSON("/api/settings/library-path", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path }),
    });
    el.libraryPathInput.value = data.libraryPath;
    el.statFiles.textContent = String(data.stats.fileCount);
    el.statSize.textContent = formatBytes(data.stats.totalBytes);
    el.libraryPathHint.textContent = "Pasta atualizada.";
  } catch (err) {
    el.libraryPathHint.textContent = `Falhou: ${err.message}`;
  }
}

el.libraryPathSave.addEventListener("click", () => {
  saveLibraryPath(el.libraryPathInput.value.trim());
});

// ---- Android native folder picker (Storage Access Framework) ----
// Only shown when the WebView bridge exposes it — desktop/browser preview
// keeps the plain text field as the only way to set the path.
if (window.SapphireBoxAndroid && typeof window.SapphireBoxAndroid.hasFolderPicker === "function" && window.SapphireBoxAndroid.hasFolderPicker()) {
  el.libraryPathBrowse.hidden = false;
  el.libraryPathBrowse.addEventListener("click", () => {
    el.libraryPathHint.textContent = "Escolhendo pasta…";
    window.SapphireBoxAndroid.pickFolder();
  });
}

// Called by MainActivity.kt once the user finishes the native folder
// picker (and, if needed, grants "acesso a todos os arquivos" first).
window.onSapphireBoxFolderPicked = (path) => {
  saveLibraryPath(path);
};

const FOLDER_PICK_FAILURE_MESSAGES = {
  WRONG_PROVIDER:
    "Essa pasta veio de um atalho (tipo \"Downloads\" ou \"Recentes\") que o app não consegue usar. Abre o seletor de novo e navega até \"Armazenamento interno\" no menu lateral pra escolher a pasta lá dentro.",
  UNSUPPORTED_VOLUME:
    "Cartão SD ou armazenamento externo ainda não é suportado pra essa escolha — escolha uma pasta dentro do armazenamento interno principal, ou digite o caminho manualmente.",
  OTHER:
    "Não deu pra usar essa pasta. Se apareceu a tela de permissão, aceite \"Acesso a todos os arquivos\" e tente de novo — ou digite o caminho manualmente.",
};

window.onSapphireBoxFolderPickFailed = (reason) => {
  el.libraryPathHint.textContent = FOLDER_PICK_FAILURE_MESSAGES[reason] || FOLDER_PICK_FAILURE_MESSAGES.OTHER;
};

el.settingsClearLibrary.addEventListener("click", async () => {
  const ok = confirm("Apagar todos os mangás, quadrinhos e livros baixados do disco? Essa ação remove os arquivos da biblioteca local.");
  if (!ok) return;
  el.settingsClearHint.textContent = "Limpando…";
  try {
    const data = await fetchJSON("/api/library/all", { method: "DELETE" });
    el.statFiles.textContent = String(data.stats.fileCount);
    el.statSize.textContent = formatBytes(data.stats.totalBytes);
    el.settingsClearHint.textContent = "Biblioteca limpa.";
    libraryPage = 1;
  } catch (err) {
    el.settingsClearHint.textContent = `Falhou: ${err.message}`;
  }
});

// ---- reader ----
function resetReaderPanels() {
  el.readerManga.hidden = true;
  el.readerStrip.hidden = true;
  el.readerStrip.innerHTML = "";
  el.readerPdf.hidden = true;
  el.readerPdfStrip.hidden = true;
  el.readerPdfStrip.innerHTML = "";
  if (pdfContinuousObserver) {
    pdfContinuousObserver.disconnect();
    pdfContinuousObserver = null;
  }
  if (pdfRenderTask) {
    pdfRenderTask.cancel();
    pdfRenderTask = null;
  }
  if (pdfDoc) {
    pdfDoc.destroy();
    pdfDoc = null;
  }
  pdfPageNum = 1;
  pdfNumPages = 0;
  el.readerText.hidden = true;
  el.readerText.textContent = "";
  el.readerEpub.hidden = true;
  el.readerEpub.innerHTML = "";
  el.readerEmpty.hidden = true;
  el.readerTextMode.hidden = true;
  el.readerTextMode.disabled = false;
  el.readerTextMode.textContent = "Texto";
  el.readerTextMode.onclick = null;
  el.readerModePages.hidden = true;
  el.readerModeContinuous.hidden = true;
  el.readerTurnTap.hidden = true;
  el.readerTurnSwipe.hidden = true;
  el.readerToc.innerHTML = "";
  el.readerView.classList.remove("reader-continuous-mode");
  if (epubBook) {
    epubBook.destroy();
    epubBook = null;
  }
  epubRendition = null;
  currentBookFileUrl = "";
  currentReaderItem = null;
  currentPdfText = "";
  mangaReaderState = null;
  setReaderNavEnabled(false, false);
}

function openReader(item) {
  viewBeforeReader = el.detailView.hidden ? currentView : "details";
  resetReaderPanels();
  currentReaderItem = item;
  readerZoom = 100;
  applyReaderZoom();
  applyReaderPaperMode();
  el.readerTitle.textContent = item.title || "";
  el.content.hidden = true;
  el.detailView.hidden = true;
  el.main.classList.add("reader-open");
  el.readerView.hidden = false;

  if (domainFor(item) === "manga") {
    openMangaReader(item);
  } else {
    openBookReader(item);
  }
}

function closeReader() {
  if (isFullscreenActive()) {
    const exit = document.exitFullscreen || document.webkitExitFullscreen;
    if (exit) exit.call(document).catch(() => {});
  }
  resetReaderPanels();
  el.readerView.hidden = true;
  el.main.classList.remove("reader-open");
  if (viewBeforeReader === "details") {
    el.detailView.hidden = false;
    return;
  }
  el.content.hidden = false;
  switchView(viewBeforeReader);
}

el.readerBack.addEventListener("click", closeReader);

function setReaderNavEnabled(prev, next) {
  el.readerPrev.disabled = !prev;
  el.readerNext.disabled = !next;
  el.readerPagePrev.disabled = !prev;
  el.readerPageNext.disabled = !next;
}

function scrollReader(delta) {
  el.readerViewer.scrollBy({ top: delta * el.readerViewer.clientHeight * 0.82, behavior: "smooth" });
}

function readerGoPrev() {
  if (mangaReaderState) {
    if (readerLayoutMode === "continuous") scrollToContinuousPage(mangaReaderState.index - 1);
    else showMangaPage(mangaReaderState.index - 1);
  } else if (pdfDoc) {
    if (readerLayoutMode === "continuous") scrollToPdfStripPage(pdfPageNum - 1);
    else goToPdfPage(pdfPageNum - 1);
  } else if (epubRendition) {
    epubRendition.prev();
  } else {
    scrollReader(-1);
  }
}

function readerGoNext() {
  if (mangaReaderState) {
    if (readerLayoutMode === "continuous") scrollToContinuousPage(mangaReaderState.index + 1);
    else showMangaPage(mangaReaderState.index + 1);
  } else if (pdfDoc) {
    if (readerLayoutMode === "continuous") scrollToPdfStripPage(pdfPageNum + 1);
    else goToPdfPage(pdfPageNum + 1);
  } else if (epubRendition) {
    epubRendition.next();
  } else {
    scrollReader(1);
  }
}

el.readerPrev.addEventListener("click", readerGoPrev);
el.readerNext.addEventListener("click", readerGoNext);
el.readerPdfPrev.addEventListener("click", readerGoPrev);
el.readerPdfNext.addEventListener("click", readerGoNext);
el.readerEpubPrev.addEventListener("click", readerGoPrev);
el.readerEpubNext.addEventListener("click", readerGoNext);

function isFullscreenActive() {
  return Boolean(document.fullscreenElement || document.webkitFullscreenElement);
}

// The header's own fullscreen button is outside #reader-viewer, so once
// that element goes fullscreen the button (and the rest of the header/
// toolbar) simply isn't rendered any more — fullscreen only paints the
// fullscreened element's own subtree. The floating exit button lives
// inside #reader-viewer specifically so there's still a way out.
function updateFullscreenIcon() {
  el.readerFullscreenExit.hidden = !isFullscreenActive();
}

async function toggleFullscreen() {
  try {
    if (!isFullscreenActive()) {
      const target = el.readerViewer;
      const request = target.requestFullscreen || target.webkitRequestFullscreen;
      if (request) await request.call(target);
    } else {
      const exit = document.exitFullscreen || document.webkitExitFullscreen;
      if (exit) await exit.call(document);
    }
  } catch (err) {
    console.error("fullscreen toggle failed", err);
  }
}

el.readerFullscreen.addEventListener("click", toggleFullscreen);
el.readerFullscreenExit.addEventListener("click", toggleFullscreen);
document.addEventListener("fullscreenchange", updateFullscreenIcon);
document.addEventListener("webkitfullscreenchange", updateFullscreenIcon);

function applyEpubReaderTheme() {
  if (!epubRendition) return;
  epubRendition.themes.default({
    body: {
      "font-family": "Arial, sans-serif",
      "font-size": `${readerZoom}%`,
      "line-height": "1.65",
      "background": readerPaperMode ? "#f6f1e8" : "#151516",
      "color": readerPaperMode ? "#201915" : "#ededf0",
    },
    p: {
      "line-height": "1.65",
    },
  });
}

function applyReaderZoom() {
  readerZoom = Math.max(60, Math.min(190, readerZoom));
  el.readerZoomLabel.textContent = `${readerZoom}%`;
  el.readerPageImg.style.width = `${readerZoom}%`;
  el.readerStrip.querySelectorAll("img").forEach((img) => {
    img.style.width = `${readerZoom}%`;
  });
  el.readerText.style.fontSize = `${14.5 * (readerZoom / 100)}px`;
  applyEpubReaderTheme();
  if (!el.readerPdf.hidden && pdfDoc) {
    renderPdfPage(pdfPageNum);
  }
  if (!el.readerPdfStrip.hidden && pdfDoc) {
    reRenderPdfStripAtCurrentZoom();
  }
}

function applyReaderPaperMode() {
  el.readerView.classList.toggle("reader-paper", readerPaperMode);
  el.readerThemePage.textContent = readerPaperMode ? "Noite" : "Papel";
  el.readerThemePage.classList.toggle("active", readerPaperMode);
  applyEpubReaderTheme();
}

function changeReaderZoom(delta) {
  readerZoom += delta;
  applyReaderZoom();
}

el.readerZoomOut.addEventListener("click", () => changeReaderZoom(-10));
el.readerZoomIn.addEventListener("click", () => changeReaderZoom(10));
el.readerZoomReset.addEventListener("click", () => {
  readerZoom = 100;
  applyReaderZoom();
});
el.readerThemePage.addEventListener("click", () => {
  readerPaperMode = !readerPaperMode;
  applyReaderPaperMode();
});

// ---- page-turn method: tap zones vs swipe ----
// Some formats/readers feel more natural flipped by dragging a finger
// across the page (like a real book) instead of tapping an edge — this
// mirrors the choice most e-reader apps offer, persisted the same way as
// the pages/continuous layout choice. Swiping only makes sense in paged
// mode (continuous already navigates by scrolling).
const READER_TURN_KEY = "sapphirebox-reader-turn-mode";
let readerTurnMode = localStorage.getItem(READER_TURN_KEY) || "tap";

function updateReaderTurnButtons() {
  el.readerTurnTap.classList.toggle("active", readerTurnMode === "tap");
  el.readerTurnSwipe.classList.toggle("active", readerTurnMode === "swipe");
}

function applyReaderTurnMode() {
  const tapEnabled = readerTurnMode === "tap";
  [el.readerPagePrev, el.readerPageNext, el.readerPdfPrev, el.readerPdfNext, el.readerEpubPrev, el.readerEpubNext].forEach((btn) => {
    if (btn) btn.style.display = tapEnabled ? "" : "none";
  });
}

function setReaderTurnMode(mode) {
  readerTurnMode = mode === "swipe" ? "swipe" : "tap";
  localStorage.setItem(READER_TURN_KEY, readerTurnMode);
  updateReaderTurnButtons();
  applyReaderTurnMode();
}

el.readerTurnTap.addEventListener("click", () => setReaderTurnMode("tap"));
el.readerTurnSwipe.addEventListener("click", () => setReaderTurnMode("swipe"));
updateReaderTurnButtons();
applyReaderTurnMode();

// ---- pinch-to-zoom (two fingers) + swipe-to-turn (one finger) ----
// The WebView's own native page-zoom would scale the whole app UI
// (sidebar included, not just the page), doesn't know about this app's
// own zoom percentage, and — inside the Fullscreen API's custom view
// specifically — didn't seem to respond to the gesture at all. Handled
// as a plain two-finger touch gesture instead, driving the exact same
// readerZoom state as the +/- buttons. A cheap CSS transform previews
// the gesture live; the real content (a full canvas re-render for PDF,
// image width for manga) is only recomputed once the fingers lift —
// re-rendering a PDF page on every touchmove tick would never keep up
// with a finger. The same listeners also track a one-finger horizontal
// drag for swipe-to-turn, since both need to watch the same touch
// sequence to tell "two fingers pinching" from "one finger swiping"
// apart from the start.
let pinchStartDistance = 0;
let pinchStartZoom = 100;
let pinchLiveZoom = 100;
let swipeStartX = 0;
let swipeStartY = 0;
let swipeTracking = false;

function touchDistance(touches) {
  return Math.hypot(touches[0].clientX - touches[1].clientX, touches[0].clientY - touches[1].clientY);
}

function handleReaderTouchStart(evt) {
  if (evt.touches.length === 2) {
    swipeTracking = false;
    pinchStartDistance = touchDistance(evt.touches);
    pinchStartZoom = readerZoom;
    pinchLiveZoom = readerZoom;
  } else if (evt.touches.length === 1 && readerTurnMode === "swipe" && readerLayoutMode !== "continuous") {
    swipeTracking = true;
    swipeStartX = evt.touches[0].clientX;
    swipeStartY = evt.touches[0].clientY;
  }
}

function handleReaderTouchMove(evt) {
  if (evt.touches.length === 2 && pinchStartDistance > 0) {
    evt.preventDefault();
    swipeTracking = false;
    const scale = touchDistance(evt.touches) / pinchStartDistance;
    pinchLiveZoom = Math.max(60, Math.min(190, pinchStartZoom * scale));
    el.readerViewer.style.transformOrigin = "center center";
    el.readerViewer.style.transform = `scale(${pinchLiveZoom / pinchStartZoom})`;
  }
}

function endPinch() {
  if (pinchStartDistance === 0) return;
  pinchStartDistance = 0;
  el.readerViewer.style.transform = "";
  readerZoom = pinchLiveZoom;
  applyReaderZoom();
}

function handleReaderTouchEnd(evt) {
  endPinch();
  if (!swipeTracking) return;
  swipeTracking = false;
  const touch = evt.changedTouches && evt.changedTouches[0];
  if (!touch) return;
  const dx = touch.clientX - swipeStartX;
  const dy = touch.clientY - swipeStartY;
  if (Math.abs(dx) > 60 && Math.abs(dx) > Math.abs(dy) * 1.5) {
    if (dx < 0) readerGoNext();
    else readerGoPrev();
  }
}

function handleReaderTouchCancel() {
  endPinch();
  swipeTracking = false;
}

function attachReaderTouchHandlers(target) {
  target.addEventListener("touchstart", handleReaderTouchStart, { passive: true });
  target.addEventListener("touchmove", handleReaderTouchMove, { passive: false });
  target.addEventListener("touchend", handleReaderTouchEnd);
  target.addEventListener("touchcancel", handleReaderTouchCancel);
}

attachReaderTouchHandlers(el.readerViewer);

// EPUB pages render inside an <iframe> that epub.js manages — touches
// landing on that content fire in the iframe's OWN document and never
// bubble out to the parent page (a normal cross-document boundary, not a
// bug in epub.js), so the listeners above alone never see a finger that
// lands on the actual text. Re-attaching the same handlers straight onto
// each rendered iframe's document — done from the "rendered" hook set up
// where the EPUB is opened — is what makes pinch-zoom and edge taps work
// there too. The pinch preview transform still targets el.readerViewer
// (a normal element in the parent document), so that part needs no
// special handling once the gesture's numbers are computed.
const epubTouchDocuments = new WeakSet();

// epub.js's rendition "rendered" event hands back a View instance, not a
// plain object — the iframe's document lives at .document on some
// versions/managers and at .contents.document on others, so both are
// checked rather than betting on one internal shape.
function attachEpubTouchHandlers(view) {
  const doc = (view && (view.document || (view.contents && view.contents.document))) || null;
  if (!doc || epubTouchDocuments.has(doc)) return;
  epubTouchDocuments.add(doc);
  attachReaderTouchHandlers(doc);
}

function updateReaderModeButtons() {
  el.readerModePages.classList.toggle("active", readerLayoutMode === "pages");
  el.readerModeContinuous.classList.toggle("active", readerLayoutMode === "continuous");
}

function setImageReaderControlsVisible(visible) {
  el.readerModePages.hidden = !visible;
  el.readerModeContinuous.hidden = !visible;
  el.readerTurnTap.hidden = !visible;
  el.readerTurnSwipe.hidden = !visible;
  updateReaderModeButtons();
}

function imageUrlForReaderPage(index) {
  if (!mangaReaderState) return "";
  const page = mangaReaderState.pages[index];
  if (mangaReaderState.mode === "bookArchive") {
    return `/api/library/books/archive/page?id=${encodeURIComponent(mangaReaderState.bookId)}&page=${encodeURIComponent(page)}`;
  }
  return `/api/library/manga/page?id=${encodeURIComponent(mangaReaderState.mangaId)}&chapter=${encodeURIComponent(mangaReaderState.chapterFile)}&page=${encodeURIComponent(page)}`;
}

function setReaderPageIndex(index) {
  if (!mangaReaderState) return;
  const clamped = Math.max(0, Math.min(index, mangaReaderState.pages.length - 1));
  mangaReaderState.index = clamped;
  el.readerPageIndicator.textContent = `Página ${clamped + 1}`;
  setReaderNavEnabled(clamped > 0, clamped < mangaReaderState.pages.length - 1);
  el.readerToc.querySelectorAll("button[data-page-index]").forEach((b) => {
    b.classList.toggle("active", Number(b.dataset.pageIndex) === clamped);
  });

  if (currentReaderItem) {
    if (mangaReaderState.mode === "manga") {
      saveReadingState(currentReaderItem.id, "manga", { chapterFile: mangaReaderState.chapterFile, pageIndex: clamped });
    } else if (mangaReaderState.mode === "bookArchive") {
      saveReadingState(currentReaderItem.id, "bookArchive", { pageIndex: clamped });
    }
  }
}

function renderPagedImageReader(index = 0) {
  if (!mangaReaderState) return;
  el.readerView.classList.remove("reader-continuous-mode");
  el.readerStrip.hidden = true;
  el.readerStrip.innerHTML = "";
  el.readerManga.hidden = false;
  const clamped = Math.max(0, Math.min(index, mangaReaderState.pages.length - 1));
  el.readerPageImg.src = imageUrlForReaderPage(clamped);
  el.readerPageImg.alt = `Página ${clamped + 1}`;
  setReaderPageIndex(clamped);
  applyReaderZoom();
}

function renderContinuousImageReader(index = 0) {
  if (!mangaReaderState) return;
  el.readerView.classList.add("reader-continuous-mode");
  el.readerManga.hidden = true;
  el.readerStrip.hidden = false;
  el.readerStrip.innerHTML = "";
  mangaReaderState.pages.forEach((page, idx) => {
    const img = document.createElement("img");
    img.loading = idx < 3 ? "eager" : "lazy";
    img.alt = `Página ${idx + 1}`;
    img.dataset.pageIndex = String(idx);
    img.src = imageUrlForReaderPage(idx);
    img.style.width = `${readerZoom}%`;
    el.readerStrip.appendChild(img);
  });
  setReaderPageIndex(index);
  requestAnimationFrame(() => scrollToContinuousPage(index, "auto"));
}

function renderImageReader(index = 0) {
  setImageReaderControlsVisible(true);
  updateReaderModeButtons();
  if (readerLayoutMode === "continuous") renderContinuousImageReader(index);
  else renderPagedImageReader(index);
}

function setReaderLayoutMode(mode) {
  readerLayoutMode = mode === "continuous" ? "continuous" : "pages";
  localStorage.setItem(READER_LAYOUT_KEY, readerLayoutMode);
  updateReaderModeButtons();
  if (mangaReaderState) {
    renderImageReader(mangaReaderState.index || 0);
  } else if (pdfDoc && el.readerText.hidden) {
    if (readerLayoutMode === "continuous") renderContinuousPdfReader(pdfPageNum);
    else renderPagedPdfReader(pdfPageNum);
  } else if (epubRendition) {
    epubRendition.flow(readerLayoutMode === "continuous" ? "scrolled-doc" : "paginated");
  }
}

function scrollToContinuousPage(index, behavior = "smooth") {
  if (!mangaReaderState) return;
  const clamped = Math.max(0, Math.min(index, mangaReaderState.pages.length - 1));
  const img = el.readerStrip.querySelector(`img[data-page-index="${clamped}"]`);
  if (img) {
    const top = Math.max(0, img.offsetTop - el.readerStrip.offsetTop);
    el.readerViewer.scrollTo({ top, behavior });
  }
  setReaderPageIndex(clamped);
}

function updateContinuousPosition() {
  if (!mangaReaderState || readerLayoutMode !== "continuous" || el.readerStrip.hidden) return;
  const images = [...el.readerStrip.querySelectorAll("img")];
  if (images.length === 0) return;
  const center = el.readerViewer.scrollTop + el.readerViewer.clientHeight / 2;
  let bestIdx = mangaReaderState.index || 0;
  let bestDistance = Number.POSITIVE_INFINITY;
  for (const img of images) {
    const pageCenter = img.offsetTop - el.readerStrip.offsetTop + img.clientHeight / 2;
    const distance = Math.abs(pageCenter - center);
    if (distance < bestDistance) {
      bestDistance = distance;
      bestIdx = Number(img.dataset.pageIndex);
    }
  }
  setReaderPageIndex(bestIdx);
}

let textScrollSaveTimer = null;

function saveTextScrollPosition() {
  if (el.readerText.hidden || !currentReaderItem) return;
  const itemId = currentReaderItem.id;
  clearTimeout(textScrollSaveTimer);
  textScrollSaveTimer = setTimeout(() => {
    const max = el.readerViewer.scrollHeight - el.readerViewer.clientHeight;
    const fraction = max > 0 ? el.readerViewer.scrollTop / max : 0;
    saveReadingState(itemId, "text", { location: String(fraction) });
  }, 600);
}

el.readerModePages.addEventListener("click", () => setReaderLayoutMode("pages"));
el.readerModeContinuous.addEventListener("click", () => setReaderLayoutMode("continuous"));
el.readerViewer.addEventListener("scroll", updateContinuousPosition);
el.readerViewer.addEventListener("scroll", saveTextScrollPosition);

// -- manga: chapters on the left, page image + prev/next in the middle --
async function openMangaReader(item) {
  let chapters = [];
  try {
    const data = await fetchJSON(`/api/library/manga/chapters?id=${encodeURIComponent(item.id)}`);
    chapters = data.chapters || [];
  } catch (err) {
    console.error(err);
  }

  if (chapters.length === 0) {
    el.readerEmpty.hidden = false;
    el.readerEmpty.querySelector(".desc").textContent = "Nenhum capítulo encontrado nessa pasta.";
    return;
  }

  for (const chapter of chapters) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.textContent = `Capítulo ${chapter.label}`;
    btn.dataset.file = chapter.file;
    btn.addEventListener("click", () => loadMangaChapter(item.id, chapter.file));
    el.readerToc.appendChild(btn);
  }

  let startChapter = chapters[0].file;
  let startIndex = 0;
  const saved = await fetchReadingState(item.id);
  if (saved && saved.chapterFile && chapters.some((c) => c.file === saved.chapterFile)) {
    startChapter = saved.chapterFile;
    startIndex = saved.pageIndex || 0;
  }

  await loadMangaChapter(item.id, startChapter, startIndex);
}

async function loadMangaChapter(mangaId, chapterFile, startIndex = 0) {
  el.readerToc.querySelectorAll("button").forEach((b) => b.classList.toggle("active", b.dataset.file === chapterFile));
  try {
    const data = await fetchJSON(`/api/library/manga/pages?id=${encodeURIComponent(mangaId)}&chapter=${encodeURIComponent(chapterFile)}`);
    const pages = data.pages || [];
    if (pages.length === 0) {
      el.readerEmpty.hidden = false;
      el.readerEmpty.querySelector(".desc").textContent = "Esse capítulo não tem páginas legíveis.";
      return;
    }
    const clampedStart = Math.max(0, Math.min(startIndex, pages.length - 1));
    mangaReaderState = { mode: "manga", mangaId, chapterFile, pages, index: clampedStart };
    el.readerEmpty.hidden = true;
    renderImageReader(clampedStart);
  } catch (err) {
    el.readerEmpty.hidden = false;
    el.readerEmpty.querySelector(".desc").textContent = err.message;
  }
}

function showMangaPage(index) {
  if (!mangaReaderState) return;
  if (readerLayoutMode === "continuous") {
    scrollToContinuousPage(index);
    return;
  }
  renderPagedImageReader(index);
}

el.readerPagePrev.addEventListener("click", readerGoPrev);
el.readerPageNext.addEventListener("click", readerGoNext);

document.addEventListener("keydown", (evt) => {
  if (el.readerView.hidden) return;
  if (evt.key === "ArrowLeft") readerGoPrev();
  if (evt.key === "ArrowRight") readerGoNext();
});

function restoreTextScrollPosition(itemId) {
  fetchReadingState(itemId).then((saved) => {
    const fraction = saved && saved.location ? parseFloat(saved.location) : NaN;
    if (Number.isNaN(fraction)) return;
    requestAnimationFrame(() => {
      const max = el.readerViewer.scrollHeight - el.readerViewer.clientHeight;
      el.readerViewer.scrollTop = fraction * Math.max(max, 0);
    });
  });
}

async function openBookTextReader(item) {
  try {
    const data = await fetchJSON(`/api/library/books/text?id=${encodeURIComponent(item.id)}`);
    el.readerPdf.hidden = true;
    el.readerText.hidden = false;
    el.readerText.textContent = data.text || "";
    el.readerViewer.scrollTop = 0;
    applyReaderZoom();
    setReaderNavEnabled(true, true);
    restoreTextScrollPosition(item.id);
  } catch (err) {
    el.readerEmpty.hidden = false;
    el.readerEmpty.querySelector(".desc").textContent = err.message;
  }
}

async function togglePdfTextMode() {
  if (!currentReaderItem || !currentBookFileUrl) return;
  if (!el.readerText.hidden) {
    el.readerText.hidden = true;
    el.readerTextMode.textContent = "Texto";
    if (pdfDoc) {
      if (readerLayoutMode === "continuous") renderContinuousPdfReader(pdfPageNum);
      else renderPagedPdfReader(pdfPageNum);
    } else {
      setReaderNavEnabled(false, false);
    }
    return;
  }
  if (currentPdfText) {
    el.readerPdf.hidden = true;
    el.readerPdfStrip.hidden = true;
    teardownPdfContinuous();
    el.readerText.hidden = false;
    el.readerText.textContent = currentPdfText;
    el.readerTextMode.textContent = "PDF";
    setReaderNavEnabled(true, true);
    restoreTextScrollPosition(currentReaderItem.id);
    return;
  }
  el.readerTextMode.disabled = true;
  el.readerTextMode.textContent = "Extraindo";
  try {
    const data = await fetchJSON(`/api/library/books/text?id=${encodeURIComponent(currentReaderItem.id)}`);
    currentPdfText = data.text || "";
    el.readerPdf.hidden = true;
    el.readerPdfStrip.hidden = true;
    teardownPdfContinuous();
    el.readerText.hidden = false;
    el.readerText.textContent = currentPdfText;
    el.readerViewer.scrollTop = 0;
    el.readerTextMode.textContent = "PDF";
    setReaderNavEnabled(true, true);
    applyReaderZoom();
    restoreTextScrollPosition(currentReaderItem.id);
  } catch (err) {
    alert(`Não deu pra extrair texto: ${err.message}`);
    el.readerTextMode.textContent = "Texto";
  } finally {
    el.readerTextMode.disabled = false;
  }
}

async function openBookArchiveReader(item) {
  try {
    const data = await fetchJSON(`/api/library/books/archive/pages?id=${encodeURIComponent(item.id)}`);
    const pages = data.pages || [];
    if (pages.length === 0) {
      el.readerEmpty.hidden = false;
      el.readerEmpty.querySelector(".desc").textContent = "Esse arquivo não tem páginas de imagem legíveis.";
      return;
    }
    el.readerToc.innerHTML = "";
    pages.forEach((page, idx) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.textContent = `Página ${idx + 1}`;
      btn.dataset.pageIndex = String(idx);
      btn.addEventListener("click", () => {
        if (readerLayoutMode === "continuous") scrollToContinuousPage(idx);
        else showMangaPage(idx);
      });
      el.readerToc.appendChild(btn);
    });
    let startIndex = 0;
    const saved = await fetchReadingState(item.id);
    if (saved && typeof saved.pageIndex === "number") {
      startIndex = Math.max(0, Math.min(saved.pageIndex, pages.length - 1));
    }
    mangaReaderState = { mode: "bookArchive", bookId: item.id, pages, index: startIndex };
    el.readerEmpty.hidden = true;
    renderImageReader(startIndex);
  } catch (err) {
    el.readerEmpty.hidden = false;
    el.readerEmpty.querySelector(".desc").textContent = err.message;
  }
}

// -- pdf: rendered page-by-page onto a <canvas> via pdf.js — never an
// <iframe> onto the browser's own PDF plugin, since that's exactly what
// a future e-reader port (Kindle etc.) can't be relied on to have. ----
function renderPdfPage(num) {
  if (!pdfDoc) return;
  if (pdfRenderTask) {
    pdfRenderTask.cancel();
    pdfRenderTask = null;
  }
  pdfDoc.getPage(num).then((page) => {
    const canvas = el.readerPdfCanvas;
    const ctx = canvas.getContext("2d");
    const dpr = window.devicePixelRatio || 1;
    const scale = (readerZoom / 100) * dpr;
    const viewport = page.getViewport({ scale });
    canvas.width = viewport.width;
    canvas.height = viewport.height;
    canvas.style.width = `${viewport.width / dpr}px`;
    canvas.style.height = `${viewport.height / dpr}px`;
    const task = page.render({ canvasContext: ctx, viewport });
    pdfRenderTask = task;
    task.promise
      .then(() => { pdfRenderTask = null; })
      .catch((err) => {
        pdfRenderTask = null;
        if (err?.name !== "RenderingCancelledException") console.error(err);
      });
  });
  el.readerPdfIndicator.textContent = `Página ${num} de ${pdfNumPages}`;
  setReaderNavEnabled(num > 1, num < pdfNumPages);
  if (currentReaderItem) {
    saveReadingState(currentReaderItem.id, "pdf", { pageIndex: num - 1 });
  }
}

function goToPdfPage(num) {
  if (!pdfDoc) return;
  pdfPageNum = Math.max(1, Math.min(num, pdfNumPages));
  renderPdfPage(pdfPageNum);
}

function teardownPdfContinuous() {
  if (pdfContinuousObserver) {
    pdfContinuousObserver.disconnect();
    pdfContinuousObserver = null;
  }
}

function renderPagedPdfReader(num) {
  el.readerView.classList.remove("reader-continuous-mode");
  teardownPdfContinuous();
  el.readerPdfStrip.hidden = true;
  el.readerPdfStrip.innerHTML = "";
  el.readerPdf.hidden = false;
  renderPdfPage(num);
}

// Continuous PDF reading: one canvas per page stacked in a scrollable
// strip (same idea as the manga strip), rendered lazily as each page
// scrolls into view instead of all at once up front — a 300-page PDF
// rendered eagerly at full res would stall the page and burn memory.
function renderPdfStripPage(pageNum) {
  if (!pdfDoc) return;
  const wrap = el.readerPdfStrip.querySelector(`.pdf-strip-page[data-page-index="${pageNum}"]`);
  if (!wrap || wrap.dataset.rendered === "1") return;
  wrap.dataset.rendered = "1";
  pdfDoc.getPage(pageNum).then((page) => {
    const canvas = wrap.querySelector("canvas");
    const ctx = canvas.getContext("2d");
    const dpr = window.devicePixelRatio || 1;
    const scale = (readerZoom / 100) * dpr;
    const viewport = page.getViewport({ scale });
    canvas.width = viewport.width;
    canvas.height = viewport.height;
    canvas.style.width = `${viewport.width / dpr}px`;
    canvas.style.height = `${viewport.height / dpr}px`;
    page.render({ canvasContext: ctx, viewport });
  });
}

function reRenderPdfStripAtCurrentZoom() {
  el.readerPdfStrip.querySelectorAll('.pdf-strip-page[data-rendered="1"]').forEach((wrap) => {
    wrap.dataset.rendered = "";
    renderPdfStripPage(Number(wrap.dataset.pageIndex));
  });
}

function scrollToPdfStripPage(num, behavior = "smooth") {
  if (!pdfDoc) return;
  const clamped = Math.max(1, Math.min(num, pdfNumPages));
  const wrap = el.readerPdfStrip.querySelector(`.pdf-strip-page[data-page-index="${clamped}"]`);
  if (wrap) {
    const top = Math.max(0, wrap.offsetTop - el.readerPdfStrip.offsetTop);
    el.readerViewer.scrollTo({ top, behavior });
  }
  pdfPageNum = clamped;
  setReaderNavEnabled(clamped > 1, clamped < pdfNumPages);
  if (currentReaderItem) {
    saveReadingState(currentReaderItem.id, "pdf", { pageIndex: clamped - 1 });
  }
}

function renderContinuousPdfReader(startPage) {
  if (!pdfDoc) return;
  el.readerView.classList.add("reader-continuous-mode");
  el.readerPdf.hidden = true;
  el.readerPdfStrip.hidden = false;
  el.readerPdfStrip.innerHTML = "";
  teardownPdfContinuous();

  for (let i = 1; i <= pdfNumPages; i += 1) {
    const wrap = document.createElement("div");
    wrap.className = "pdf-strip-page";
    wrap.dataset.pageIndex = String(i);
    wrap.appendChild(document.createElement("canvas"));
    el.readerPdfStrip.appendChild(wrap);
  }

  pdfContinuousObserver = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) renderPdfStripPage(Number(entry.target.dataset.pageIndex));
      });
    },
    { root: el.readerViewer, rootMargin: "800px 0px" }
  );
  el.readerPdfStrip.querySelectorAll(".pdf-strip-page").forEach((wrap) => pdfContinuousObserver.observe(wrap));

  pdfPageNum = startPage;
  setReaderNavEnabled(startPage > 1, startPage < pdfNumPages);
  requestAnimationFrame(() => scrollToPdfStripPage(startPage, "auto"));
}

function updatePdfContinuousPosition() {
  if (!pdfDoc || readerLayoutMode !== "continuous" || el.readerPdfStrip.hidden) return;
  const wraps = [...el.readerPdfStrip.querySelectorAll(".pdf-strip-page")];
  if (wraps.length === 0) return;
  const center = el.readerViewer.scrollTop + el.readerViewer.clientHeight / 2;
  let bestNum = pdfPageNum;
  let bestDistance = Number.POSITIVE_INFINITY;
  for (const wrap of wraps) {
    const pageCenter = wrap.offsetTop - el.readerPdfStrip.offsetTop + wrap.clientHeight / 2;
    const distance = Math.abs(pageCenter - center);
    if (distance < bestDistance) {
      bestDistance = distance;
      bestNum = Number(wrap.dataset.pageIndex);
    }
  }
  pdfPageNum = bestNum;
  setReaderNavEnabled(bestNum > 1, bestNum < pdfNumPages);
}

el.readerViewer.addEventListener("scroll", updatePdfContinuousPosition);

async function openPdfReader(item, fileUrl) {
  el.readerTextMode.hidden = false;
  el.readerTextMode.onclick = togglePdfTextMode;
  setImageReaderControlsVisible(true);
  try {
    pdfDoc = await window.pdfjsLib.getDocument(fileUrl).promise;
    pdfNumPages = pdfDoc.numPages;
    let startPage = 1;
    const saved = await fetchReadingState(item.id);
    if (saved && typeof saved.pageIndex === "number") {
      startPage = Math.max(1, Math.min(saved.pageIndex + 1, pdfNumPages));
    }
    pdfPageNum = startPage;
    if (readerLayoutMode === "continuous") renderContinuousPdfReader(startPage);
    else renderPagedPdfReader(startPage);
  } catch (err) {
    el.readerEmpty.hidden = false;
    el.readerEmpty.querySelector(".desc").textContent = `Não deu pra abrir esse PDF: ${err.message}`;
  }
}

// -- books: pdf via pdf.js canvas/text, txt/html/md as text, epub via epub.js, cbz/cbr as pages --
function openBookReader(item) {
  const fileUrl = `/api/library/books/file?id=${encodeURIComponent(item.id)}`;
  const format = formatForItem(item);

  if (format === "pdf") {
    currentBookFileUrl = fileUrl;
    openPdfReader(item, fileUrl);
    return;
  }

  if (["txt", "md", "markdown", "html", "htm", "xhtml", "csv", "log"].includes(format)) {
    openBookTextReader(item);
    return;
  }

  if (["cbz", "cbr"].includes(format)) {
    openBookArchiveReader(item);
    return;
  }

  if (format === "epub" && window.ePub) {
    el.readerEpub.hidden = false;
    // epub.js decides packed-vs-unpacked by sniffing the URL for a
    // ".epub" extension when handed a URL directly — our file endpoint is
    // "/api/.../file?id=..." with none, so it guessed wrong (tried
    // fetching internal paths like META-INF/container.xml as separate
    // HTTP requests) and, even forcing openAs, the fetch just hung.
    // Fetching the bytes ourselves and handing epub.js the ArrayBuffer
    // sidesteps its URL heuristics entirely — it accepts binary data
    // directly just as well as a URL.
    setImageReaderControlsVisible(true);
    apiFetch(fileUrl)
      .then((resp) => {
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        return resp.arrayBuffer();
      })
      .then((buffer) => {
        epubBook = window.ePub(buffer);
        const rendition = epubBook.renderTo(el.readerEpub, {
          width: "100%",
          height: "100%",
          flow: readerLayoutMode === "continuous" ? "scrolled-doc" : "paginated",
        });
        epubRendition = rendition;
        applyEpubReaderTheme();
        rendition.on("rendered", (section, view) => attachEpubTouchHandlers(view));
        rendition.on("relocated", (loc) => {
          if (loc && loc.start && loc.start.cfi) {
            saveReadingState(item.id, "epub", { location: loc.start.cfi });
          }
        });
        fetchReadingState(item.id).then((saved) => rendition.display(saved && saved.location ? saved.location : undefined));
        setReaderNavEnabled(true, true);
        epubBook.loaded.navigation.then((nav) => {
          for (const navItem of nav.toc) {
            const btn = document.createElement("button");
            btn.type = "button";
            btn.textContent = navItem.label.trim();
            btn.addEventListener("click", () => rendition.display(navItem.href));
            el.readerToc.appendChild(btn);
          }
        });
      })
      .catch((err) => {
        el.readerEmpty.hidden = false;
        el.readerEmpty.querySelector(".desc").textContent = `Não deu pra abrir o EPUB: ${err.message}`;
      });
    return;
  }

  el.readerEmpty.hidden = false;
  const unsupported =
    ["mobi", "azw3"].includes(format)
      ? "MOBI/AZW3 precisam de um leitor externo ou de uma versão EPUB/PDF para leitura interna."
      : `O leitor interno ainda não renderiza "${format || "formato desconhecido"}".`;
  el.readerEmpty.querySelector(".desc").innerHTML =
    `${unsupported} <a href="${fileUrl}" target="_blank" rel="noopener">Abrir arquivo direto</a>.`;
}

// ---- routing ----
async function switchView(name) {
  if (currentView === "downloads" && name !== "downloads") stopJobPolling();

  currentView = name;
  const view = views[name];
  discoverSource = null;
  el.discoverBack.hidden = true;
  el.sourceSelect.hidden = false;
  el.navItems.forEach((btn) => btn.classList.toggle("active", btn.dataset.view === name));
  el.viewTitle.textContent = view.title;
  el.viewSub.textContent = view.sub;
  el.viewSub.hidden = !view.sub;
  el.grid.innerHTML = "";
  el.grid.hidden = false;
  el.librarySections.innerHTML = "";
  el.librarySections.hidden = true;
  el.pagination.hidden = true;
  el.searchbar.hidden = view.mode !== "search";
  el.searchCategoryToggle.hidden = view.mode !== "search";
  el.libraryToolbar.hidden = view.mode !== "library";
  el.panels.forEach((panel) => { panel.hidden = panel.id !== view.panelId; });

  if (view.mode === "discover") {
    setState(null);
    await loadDiscoverSources();
    return;
  }
  if (view.mode === "downloads") {
    setState(null);
    startJobPolling();
    return;
  }
  if (view.mode === "panel") {
    setState(null);
    return;
  }
  if (view.mode === "settings") {
    setState(null);
    await loadSettings();
    return;
  }
  if (view.mode === "library") {
    el.libraryQuery.value = "";
    el.libraryKind.value = "";
    libraryPage = 1;
    await loadLibraryPage();
    return;
  }
  if (view.mode === "search") {
    await setSearchCategory(searchCategory);
  }
}

el.navItems.forEach((btn) => {
  btn.addEventListener("click", () => {
    if (!el.readerView.hidden) closeReader();
    if (!el.detailView.hidden) {
      detailItem = null;
      el.detailView.hidden = true;
      el.content.hidden = false;
    }
    switchView(btn.dataset.view);
    el.mobileFab.classList.remove("open");
  });
});

el.searchbar.addEventListener("submit", (evt) => {
  evt.preventDefault();
  if (discoverSource) {
    discoverPage = 1;
    loadDiscoverPage();
  } else {
    runSearch(SEARCH_CATEGORIES[searchCategory]);
  }
});

el.brandHome.addEventListener("click", () => {
  if (!el.readerView.hidden) closeReader();
  if (!el.detailView.hidden) {
    detailItem = null;
    el.detailView.hidden = true;
    el.content.hidden = false;
  }
  switchView("library");
});

el.fabMain.addEventListener("click", () => {
  const open = el.mobileFab.classList.toggle("open");
  el.fabMain.setAttribute("aria-expanded", String(open));
});

document.addEventListener("click", (evt) => {
  if (el.mobileFab.classList.contains("open") && !el.mobileFab.contains(evt.target)) {
    el.mobileFab.classList.remove("open");
    el.fabMain.setAttribute("aria-expanded", "false");
  }
});

switchView(currentView);
