// Constants
const POLL_INTERVAL_MS   = 500;
const SEARCH_DEBOUNCE_MS = 300;
const TOAST_DURATION_MS  = 4000;
// Consecutive scan-status poll failures tolerated before giving up. At 500ms
// that is ~5s of silence, long enough to ride out a transient error.
const MAX_POLL_FAILURES  = 10;

// State Management
let allVoices = [];      // Current page of grouped results from server (up to LIMIT)
let filteredVoices = []; // Sorted view for rendering
let totalVoices = 0;     // Total matching unique patch names in the database
let isScanning = false;
let statusInterval = null;
let pollFailures = 0;
let searchDebounceTimer = null;
let voicesAbortController = null;
let currentSort = { key: 'name', asc: true };

// Folder tree state
let selectedFolder = null;  // null = all folders
let selectedType = '';       // '' = all types
let treeOpen = true;
let expandedNodes = new Set();

// Patch-type display config, shared by the voice list and the detail view header
const TYPE_CFG = {
    'Voice':          { label: 'VOICE',  cls: 'type-badge-voice', icon: 'fa-wave-square' },
    'Performance':    { label: 'PERF',   cls: 'type-badge-perf',  icon: 'fa-layer-group' },
    'Gen 2 Extended': { label: 'GEN 2',  cls: 'type-badge-gen2',  icon: 'fa-sliders' },
};

// DOM Elements
const dirInput = document.getElementById('dir-input');
const browseBtn = document.getElementById('browse-btn');
const scanBtn = document.getElementById('scan-btn');
const scanBtnText = document.getElementById('scan-btn-text');
const scanSpinner = document.getElementById('scan-spinner');
const clearBtn = document.getElementById('clear-btn');
const progressContainer = document.getElementById('progress-container');
const progressFilename = document.getElementById('progress-filename');
const progressRatio = document.getElementById('progress-ratio');
const progressBarFill = document.getElementById('progress-bar-fill');

const lcdStatus = document.getElementById('lcd-status');
const lcdTotalVoices = document.getElementById('lcd-total-voices');

const searchInput = document.getElementById('search-input');
const clearSearchBtn = document.getElementById('clear-search-btn');
const voicesTable = document.getElementById('voices-table');
const voicesTbody = document.getElementById('voices-tbody');
const loadingState = document.getElementById('loading-state');
const emptyState = document.getElementById('empty-state');
const tableHeaders = document.querySelectorAll('.voices-table th[data-sort]');

const toast = document.getElementById('toast');
const toastIcon = document.getElementById('toast-icon');
const toastMessage = document.getElementById('toast-message');
const resultCounter = document.getElementById('result-counter');

// Folder Tree Elements
const treeToggleBtn = document.getElementById('tree-toggle-btn');
const folderTreePanel = document.getElementById('folder-tree-panel');
const folderTreeRoot = document.getElementById('folder-tree-root');
const typeTabs = document.querySelectorAll('.type-tab');

// Cleanup Tab Elements
const tabExplorer = document.getElementById('tab-explorer');
const tabCleanup = document.getElementById('tab-cleanup');
const sectionExplorer = document.getElementById('section-explorer');
const sectionCleanup = document.getElementById('section-cleanup');
const findDuplicatesBtn = document.getElementById('find-duplicates-btn');
const findDupBtnText = document.getElementById('find-dup-btn-text');
const findDupSpinner = document.getElementById('find-dup-spinner');
const dupLoading = document.getElementById('dup-loading');
const dupEmpty = document.getElementById('dup-empty');
const dupInitial = document.getElementById('dup-initial');
const dupGroupsContainer = document.getElementById('dup-groups-container');

// Voice Detail View Elements
const tabBar = document.querySelector('.tab-bar');
const sectionDetail = document.getElementById('section-detail');
const detailBackBtn = document.getElementById('detail-back-btn');
const detailHeader = document.getElementById('detail-header');
const detailOperators = document.getElementById('detail-operators');
const detailModulation = document.getElementById('detail-modulation');
const detailKeymode = document.getElementById('detail-keymode');
const detailControllers = document.getElementById('detail-controllers');
let previousTab = 'explorer'; // which tab to restore when leaving the detail view

// Modal Elements
const filesModalOverlay = document.getElementById('files-modal-overlay');
const modalVoiceName = document.getElementById('modal-voice-name');
const modalLoading = document.getElementById('modal-loading');
const modalList = document.getElementById('modal-list');
const modalCloseBtn = document.getElementById('modal-close-btn');

// Initialize Application
document.addEventListener('DOMContentLoaded', () => {
    loadVoices();
    loadFolders();
    checkScanStatusOnLoad();
    setupEventListeners();
    syncSortIndicators();
    prefillDemoPath();
});

// Prefill the scan field with the bundled demo patches, so a first-run user can
// see where the sample patches came from and re-scan them. Never overwrites a
// path the user has already typed.
async function prefillDemoPath() {
    try {
        const res = await fetch('/api/app-info');
        if (!res.ok) return;
        const info = await res.json();
        if (!dirInput.value && info.demo_path) {
            dirInput.value = info.demo_path;
        }
    } catch (e) {
        /* non-fatal: the field just stays empty */
    }
}

// Event Listeners Setup
function setupEventListeners() {
    // Scan Button
    scanBtn.addEventListener('click', handleScanTrigger);
    browseBtn.addEventListener('click', handleBrowseFolder);
    
    // Clear Database Button
    clearBtn.addEventListener('click', handleClearDatabase);
    
    // Search Input
    searchInput.addEventListener('input', handleSearchInput);
    clearSearchBtn.addEventListener('click', clearSearch);
    
    // Table Header Sorting (mouse + keyboard)
    tableHeaders.forEach(th => {
        const doSort = () => handleSort(th.getAttribute('data-sort'));
        th.addEventListener('click', doSort);
        th.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); doSort(); }
        });
    });

    // Folder tree toggle
    treeToggleBtn.addEventListener('click', toggleFolderTree);

    // Type filter tabs
    typeTabs.forEach(tab => tab.addEventListener('click', () => setTypeFilter(tab.dataset.type)));

    // Tab switching
    tabExplorer.addEventListener('click', () => switchTab('explorer'));
    tabCleanup.addEventListener('click', () => switchTab('cleanup'));

    // Cleanup actions
    findDuplicatesBtn.addEventListener('click', loadDuplicates);

    // Voice Parameters detail view
    detailBackBtn.addEventListener('click', backFromDetail);

    // Modal close
    modalCloseBtn.addEventListener('click', closeFilesModal);
    filesModalOverlay.addEventListener('click', (e) => {
        if (e.target === filesModalOverlay) closeFilesModal();
    });
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && !filesModalOverlay.classList.contains('hidden')) closeFilesModal();
    });

    // Modal focus trap (keep Tab within the dialog while open)
    filesModalOverlay.addEventListener('keydown', (e) => {
        if (e.key !== 'Tab') return;
        const focusable = [...filesModalOverlay.querySelectorAll('button, a[href], input, [tabindex]:not([tabindex="-1"])')]
            .filter(el => !el.disabled && el.offsetParent !== null);
        if (!focusable.length) return;
        const first = focusable[0], last = focusable[focusable.length - 1];
        if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
        else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
    });

    // Cleanup polling interval when page is unloaded
    window.addEventListener('pagehide', () => {
        if (statusInterval) clearInterval(statusInterval);
    });
}

// Check if scanning is running (e.g. if page reloaded during scan)
async function checkScanStatusOnLoad() {
    try {
        const response = await fetch('/api/scan-status');
        if (!response.ok) throw new Error(`Status ${response.status}`);
        const state = await response.json();
        if (state.status === 'scanning') {
            startPollingStatus();
        } else {
            updateLcd(state);
        }
    } catch (e) {
        console.error("Error checking initial status:", e);
    }
}

// Fetch grouped patches from backend — one row per unique (name, type), capped at LIMIT
async function loadVoices(query = '') {
    if (voicesAbortController) voicesAbortController.abort();
    voicesAbortController = new AbortController();
    showLoading(true);
    try {
        const params = new URLSearchParams();
        if (query) params.set('q', query);
        if (selectedFolder) params.set('folder', selectedFolder);
        if (selectedType) params.set('patch_type', selectedType);
        const qs = params.toString();
        const url = qs ? `/api/voices?${qs}` : '/api/voices';
        const response = await fetch(url, { signal: voicesAbortController.signal });
        if (!response.ok) throw new Error("Failed to load patches.");
        const result = await response.json();
        allVoices = result.voices;
        totalVoices = result.total;
        sortAndRender();
        updateLcdVoicesCount(totalVoices);
    } catch (e) {
        // A superseded request must not touch the spinner: the newer request is
        // already in flight and owns it. `return` inside catch does not skip
        // `finally`, so the reset lives here rather than in a finally block.
        if (e.name === 'AbortError') return;
        showToast(e.message, 'error');
    }
    showLoading(false);
}

// Fetches JSON, turning a non-OK response into a useful Error.
//
// The server reports failures as {"detail": "..."} (HTTPException) or
// {"error": "..."} (the delete endpoint). A crashing server may return neither,
// so the body is parsed defensively -- calling res.json() before checking
// res.ok surfaces "Unexpected token '<'" instead of the real problem.
async function fetchJson(url, options) {
    const res = await fetch(url, options);
    let body = null;
    try {
        body = await res.json();
    } catch (e) {
        body = null;
    }
    if (!res.ok) {
        const detail = body && (body.detail || body.error);
        throw new Error(detail || `Request failed (status ${res.status}).`);
    }
    if (body === null) throw new Error('Server returned an invalid response.');
    return body;
}

// Open native OS folder picker and populate the directory input
async function handleBrowseFolder() {
    try {
        const response = await fetch('/api/browse-folder', { method: 'POST' });
        if (!response.ok) throw new Error('Browse dialog failed.');
        const data = await response.json();
        if (data.path) {
            dirInput.value = data.path;
        }
    } catch (e) {
        showToast('Could not open folder browser.', 'error');
    }
}

// Trigger Directory Scan
async function handleScanTrigger() {
    const directory = dirInput.value.trim();
    if (!directory) {
        showToast("Please enter a directory path.", "error");
        return;
    }
    
    try {
        setScanButtonState(true);
        await fetchJson('/api/scan', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ directory })
        });
        
        showToast("Scan started in background.", "success");
        startPollingStatus();
    } catch (e) {
        showToast(e.message, 'error');
        setScanButtonState(false);
    }
}

// Status Polling Manager
function startPollingStatus() {
    if (statusInterval) clearInterval(statusInterval);
    isScanning = true;
    setScanButtonState(true);
    progressContainer.classList.remove('hidden');
    
    pollFailures = 0;
    statusInterval = setInterval(async () => {
        try {
            const response = await fetch('/api/scan-status');
            if (!response.ok) throw new Error(`Poll failed: ${response.status}`);
            const state = await response.json();
            
            updateLcd(state);
            updateProgressBar(state);
            
            if (state.status === 'idle') {
                // Scan completed
                clearInterval(statusInterval);
                statusInterval = null;
                isScanning = false;
                setScanButtonState(false);
                progressContainer.classList.add('hidden');
                
                if (state.error) {
                    showToast(`Scan interrupted: ${state.error}`, 'error');
                } else {
                    showToast(`Scan complete! Cataloged ${state.voices_found} patches.`, 'success');
                }
                loadVoices();
                loadFolders();
            }
            pollFailures = 0;
        } catch (e) {
            // Without a cap this retries forever: an error toast every 500ms
            // with SCAN and the directory input disabled until a page reload.
            pollFailures++;
            if (pollFailures >= MAX_POLL_FAILURES) {
                clearInterval(statusInterval);
                statusInterval = null;
                isScanning = false;
                setScanButtonState(false);
                progressContainer.classList.add('hidden');
                showToast('Lost contact with the scanner. Please try again.', 'error');
            }
        }
    }, POLL_INTERVAL_MS);
}

// Clear Database Handler
async function handleClearDatabase() {
    if (isScanning) {
        showToast("Cannot clear database while scanning.", "error");
        return;
    }
    
    if (!confirm("Are you sure you want to clear the entire voice database?")) {
        return;
    }
    
    try {
        const data = await fetchJson('/api/clear', { method: 'POST' });
        if (!response.ok) throw new Error(data.detail || "Failed to clear database.");
        
        allVoices = [];
        totalVoices = 0;
        selectedFolder = null;
        expandedNodes.clear();
        folderTreeRoot.innerHTML = '';
        sortAndRender();
        updateLcdVoicesCount(0);
        showToast("Database cleared successfully.", "success");
    } catch (e) {
        showToast(e.message, 'error');
    }
}

// Reveal file in Explorer
async function revealInExplorer(filePath) {
    try {
        await fetchJson('/api/reveal', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ file_path: filePath })
        });
        showToast("File selected in Explorer.", "success");
    } catch (e) {
        showToast(e.message, 'error');
    }
}

// -----------------------------------------------------------------------
// Duplicate-Files Modal
// -----------------------------------------------------------------------

async function showFilesModal(voiceName, patchType) {
    // Show modal immediately with loading state
    modalVoiceName.textContent = voiceName;
    modalList.innerHTML = '';
    modalLoading.classList.remove('hidden');
    filesModalOverlay._lastFocus = document.activeElement;
    filesModalOverlay.classList.remove('hidden');
    document.body.style.overflow = 'hidden';
    setTimeout(() => modalCloseBtn.focus(), 0);

    try {
        const params = new URLSearchParams({ name: voiceName });
        if (patchType) params.set('patch_type', patchType);
        const files = await fetchJson(`/api/voices/files?${params}`);

        modalLoading.classList.add('hidden');
        renderModalList(files);
    } catch (e) {
        modalLoading.classList.add('hidden');
        const errEl = document.createElement('div');
        errEl.className = 'modal-error';
        errEl.innerHTML = '<i class="fa-solid fa-triangle-exclamation" aria-hidden="true"></i> ';
        errEl.append(e.message);
        modalList.appendChild(errEl);
    }
}

function renderModalList(files) {
    if (files.length === 0) {
        modalList.innerHTML = '<div class="modal-empty">No files found.</div>';
        return;
    }

    files.forEach((f, idx) => {
        const item = document.createElement('div');
        item.className = 'modal-file-item';

        const indexEl = document.createElement('div');
        indexEl.className = 'modal-file-index';
        indexEl.textContent = String(idx + 1).padStart(2, '0');

        const infoEl = document.createElement('div');
        infoEl.className = 'modal-file-info';

        const nameEl = document.createElement('div');
        nameEl.className = 'modal-file-name';
        nameEl.innerHTML = '<i class="fa-solid fa-file-audio" aria-hidden="true"></i>';
        const nameSpan = document.createElement('span');
        nameSpan.textContent = f.file_name;
        const posPill = document.createElement('span');
        posPill.className = 'modal-pos-pill';
        posPill.textContent = f.position;
        nameEl.appendChild(nameSpan);
        nameEl.appendChild(posPill);

        const pathEl = document.createElement('div');
        pathEl.className = 'modal-file-path';
        pathEl.textContent = f.folder_path;
        pathEl.title = f.folder_path;

        infoEl.appendChild(nameEl);
        infoEl.appendChild(pathEl);

        const actionsEl = document.createElement('div');
        actionsEl.className = 'modal-file-actions';

        if (f.patch_type !== 'Performance') {
            const detailsBtn = document.createElement('button');
            detailsBtn.className = 'btn-reveal modal-reveal-btn';
            detailsBtn.title = 'View voice parameters';
        detailsBtn.setAttribute('aria-label', 'View voice parameters');
            detailsBtn.innerHTML = '<i class="fa-solid fa-circle-info" aria-hidden="true"></i>';
            detailsBtn.addEventListener('click', () => {
                closeFilesModal();
                showVoiceDetail(f.id);
            });
            actionsEl.appendChild(detailsBtn);
        }

        const revealBtn = document.createElement('button');
        revealBtn.className = 'btn-reveal modal-reveal-btn';
        revealBtn.title = 'Reveal in Explorer';
        revealBtn.setAttribute('aria-label', 'Reveal in Explorer');
        revealBtn.innerHTML = '<i class="fa-regular fa-folder-open" aria-hidden="true"></i>';
        revealBtn.addEventListener('click', () => revealInExplorer(f.file_path));
        actionsEl.appendChild(revealBtn);

        item.appendChild(indexEl);
        item.appendChild(infoEl);
        item.appendChild(actionsEl);
        modalList.appendChild(item);
    });
}

function closeFilesModal() {
    filesModalOverlay.classList.add('hidden');
    document.body.style.overflow = '';
    if (filesModalOverlay._lastFocus) {
        filesModalOverlay._lastFocus.focus();
        filesModalOverlay._lastFocus = null;
    }
}

// -----------------------------------------------------------------------
// Search and Filtering (server-side with debounce)
// -----------------------------------------------------------------------

function handleSearchInput() {
    const query = searchInput.value;
    clearSearchBtn.style.display = query.length > 0 ? 'block' : 'none';

    clearTimeout(searchDebounceTimer);
    searchDebounceTimer = setTimeout(() => {
        loadVoices(query.trim());
    }, SEARCH_DEBOUNCE_MS);
}

function clearSearch() {
    searchInput.value = '';
    clearSearchBtn.style.display = 'none';
    clearTimeout(searchDebounceTimer);
    loadVoices('');
    searchInput.focus();
}

// Sort cached server results and render (no client-side filtering needed)
function sortAndRender() {
    filteredVoices = [...allVoices];
    sortData();
    renderVoicesTable();
}

// Sorting logic
// Reflects currentSort in the header arrows and aria-sort. Also called on load:
// the server returns name-ascending, so shipping "unsorted" arrows would state
// the opposite of what the user is looking at.
function syncSortIndicators() {
    tableHeaders.forEach(th => {
        const icon = th.querySelector('i');
        if (th.getAttribute('data-sort') === currentSort.key) {
            icon.className = currentSort.asc ? 'fa-solid fa-sort-up' : 'fa-solid fa-sort-down';
            th.classList.add('active-sort');
            th.setAttribute('aria-sort', currentSort.asc ? 'ascending' : 'descending');
        } else {
            icon.className = 'fa-solid fa-sort';
            th.classList.remove('active-sort');
            th.removeAttribute('aria-sort');
        }
    });
}

function handleSort(key) {
    if (currentSort.key === key) {
        currentSort.asc = !currentSort.asc;
    } else {
        currentSort.key = key;
        currentSort.asc = true;
    }
    
    syncSortIndicators();
    sortData();
    renderVoicesTable();
}

function sortData() {
    filteredVoices.sort((a, b) => {
        let valA, valB;
        if (currentSort.key === 'name') {
            valA = a.voice_name.toLowerCase();
            valB = b.voice_name.toLowerCase();
        } else if (currentSort.key === 'pos') {
            valA = a.position;
            valB = b.position;
        } else if (currentSort.key === 'file') {
            valA = a.file_name.toLowerCase();
            valB = b.file_name.toLowerCase();
        } else if (currentSort.key === 'files') {
            valA = a.file_count;
            valB = b.file_count;
        } else {
            return 0;
        }
        
        if (valA < valB) return currentSort.asc ? -1 : 1;
        if (valA > valB) return currentSort.asc ? 1 : -1;
        return 0;
    });
}

// Render Table DOM (grouped: one row per unique voice name)
function renderVoicesTable() {
    // Update result counter
    if (totalVoices > 0) {
        resultCounter.classList.remove('hidden');
        if (allVoices.length < totalVoices) {
            resultCounter.innerHTML = `Showing <strong>${allVoices.length.toLocaleString()}</strong> of <strong>${totalVoices.toLocaleString()}</strong> unique patches &mdash; refine your search to see more`;
        } else {
            resultCounter.innerHTML = `<strong>${totalVoices.toLocaleString()}</strong> unique patch${totalVoices !== 1 ? 'es' : ''} found`;
        }
    } else {
        resultCounter.classList.add('hidden');
    }

    voicesTbody.innerHTML = '';
    
    if (filteredVoices.length === 0) {
        voicesTable.classList.add('hidden');
        emptyState.classList.remove('hidden');
        return;
    }
    
    emptyState.classList.add('hidden');
    voicesTable.classList.remove('hidden');

    filteredVoices.forEach(voice => {
        const tr = document.createElement('tr');

        // Patch Name Column
        const tdName = document.createElement('td');
        tdName.className = 'td-name';
        tdName.textContent = voice.voice_name;

        // Type Column
        const tdType = document.createElement('td');
        tdType.className = 'col-type-cell';
        const typeCfg = TYPE_CFG[voice.patch_type] || { label: voice.patch_type || '?', cls: '', icon: 'fa-question' };
        const typeBadge = document.createElement('span');
        typeBadge.className = `type-badge ${typeCfg.cls}`;
        // The `|| { label: voice.patch_type ... }` fallback above puts a raw
        // server value in `label`, so build this from nodes rather than markup.
        const typeIcon = document.createElement('i');
        typeIcon.className = `fa-solid ${typeCfg.icon}`;
        typeIcon.setAttribute('aria-hidden', 'true');
        typeBadge.append(typeIcon, ' ', typeCfg.label);
        tdType.appendChild(typeBadge);

        // Position Column
        const tdPos = document.createElement('td');
        const posSpan = document.createElement('span');
        posSpan.className = 'pos-pill';
        posSpan.textContent = voice.position;
        tdPos.appendChild(posSpan);

        // Sysex File Column
        const tdFile = document.createElement('td');
        const fileWrapper = document.createElement('div');
        fileWrapper.className = 'file-wrapper';
        const fileIcon = document.createElement('i');
        fileIcon.className = 'fa-solid fa-file-audio';
        fileIcon.setAttribute('aria-hidden', 'true');
        // File names come from disk and are rendered verbatim — set them as a
        // text node, never as markup. (A file called "<img onerror=...>.syx"
        // would otherwise execute here, same-origin with the delete APIs.)
        const fileNameSpan = document.createElement('span');
        fileNameSpan.textContent = voice.file_name;
        fileWrapper.append(fileIcon, ' ', fileNameSpan);
        tdFile.appendChild(fileWrapper);

        // Folder Path Column
        const tdPath = document.createElement('td');
        tdPath.className = 'col-path';
        tdPath.textContent = voice.folder_path;
        tdPath.title = voice.folder_path;

        // Files Count Column
        const tdFiles = document.createElement('td');
        tdFiles.className = 'col-files-cell';
        const fileCount = voice.file_count || 1;
        if (fileCount > 1) {
            const badge = document.createElement('button');
            badge.className = 'file-count-badge file-count-dup';
            badge.title = `${fileCount} files contain this patch — click to view all`;
            badge.innerHTML = `<i class="fa-solid fa-layer-group" aria-hidden="true"></i> ${fileCount}`;
            badge.addEventListener('click', () => showFilesModal(voice.voice_name, voice.patch_type));
            tdFiles.appendChild(badge);
        } else {
            const badge = document.createElement('span');
            badge.className = 'file-count-badge file-count-single';
            badge.title = '1 file contains this patch';
            badge.innerHTML = `<i class="fa-solid fa-file" aria-hidden="true"></i> 1`;
            tdFiles.appendChild(badge);
        }

        // Action Column
        const tdAction = document.createElement('td');
        tdAction.className = 'col-actions';
        if (voice.patch_type !== 'Performance') {
            const detailsBtn = document.createElement('button');
            detailsBtn.className = 'btn-reveal';
            detailsBtn.innerHTML = '<i class="fa-solid fa-circle-info" aria-hidden="true"></i>';
            detailsBtn.title = "View voice parameters";
        detailsBtn.setAttribute('aria-label', "View voice parameters");
            detailsBtn.addEventListener('click', () => showVoiceDetail(voice.id));
            tdAction.appendChild(detailsBtn);
        }
        const revealBtn = document.createElement('button');
        revealBtn.className = 'btn-reveal';
        revealBtn.innerHTML = '<i class="fa-regular fa-folder-open" aria-hidden="true"></i>';
        revealBtn.title = "Reveal file in Windows Explorer";
        revealBtn.setAttribute('aria-label', "Reveal file in Windows Explorer");
        revealBtn.addEventListener('click', () => revealInExplorer(voice.file_path));
        tdAction.appendChild(revealBtn);

        tr.appendChild(tdName);
        tr.appendChild(tdType);
        tr.appendChild(tdPos);
        tr.appendChild(tdFile);
        tr.appendChild(tdPath);
        tr.appendChild(tdFiles);
        tr.appendChild(tdAction);

        voicesTbody.appendChild(tr);
    });
}

// UI State Modifiers
function showLoading(show) {
    if (show) {
        loadingState.classList.remove('hidden');
        emptyState.classList.add('hidden');
        voicesTable.classList.add('hidden');
    } else {
        loadingState.classList.add('hidden');
    }
}

function setScanButtonState(disabled) {
    scanBtn.disabled = disabled;
    dirInput.disabled = disabled;
    if (disabled) {
        scanBtnText.classList.add('hidden');
        scanSpinner.classList.remove('hidden');
    } else {
        scanBtnText.classList.remove('hidden');
        scanSpinner.classList.add('hidden');
    }
}

function updateLcdVoicesCount(count) {
    lcdTotalVoices.textContent = (count || 0).toLocaleString();
}

function updateLcd(state) {
    // Status pill (drives the dot color via the status-* class)
    if (state.status === 'scanning') {
        lcdStatus.textContent = "SCANNING";
        lcdStatus.className = "status-scanning";
    } else {
        lcdStatus.textContent = "READY";
        lcdStatus.className = "status-idle";
    }

    // Voice count
    updateLcdVoicesCount(state.voices_found);

    // Active file + progress now surface in the progress bar (see updateProgressBar)
}

function updateProgressBar(state) {
    if (state.status === 'scanning' && state.total_files > 0) {
        const pct = (state.files_scanned / state.total_files) * 100;
        progressBarFill.style.width = `${pct}%`;
        progressFilename.textContent = `Scanning: ${state.current_file || 'indexing...'}`;
        progressRatio.textContent = `${state.files_scanned} / ${state.total_files} files`;
    }
}

// -----------------------------------------------------------------------
// Folder Tree
// -----------------------------------------------------------------------

async function loadFolders() {
    try {
        const paths = await fetchJson('/api/folders');
        folderTreeRoot.innerHTML = '';
        expandedNodes.clear();
        const tree = buildFolderTree(paths);
        renderFolderTree(tree, folderTreeRoot, 0);
    } catch (e) {
        showToast('Failed to load folder tree.', 'error');
    }
}

function buildFolderTree(paths) {
    if (!paths || paths.length === 0) {
        return { name: 'ALL FOLDERS', fullPath: null, children: [] };
    }

    const norm = p => p.replace(/\\/g, '/');

    // Create a node for every path segment, including intermediates that aren't
    // directly in the DB (folders that contain only subfolders, no .syx files).
    const nodeMap = new Map(); // normKey -> { name, fullPath, children }

    function ensureNode(normKey, segs) {
        if (!nodeMap.has(normKey)) {
            // Reconstruct the original OS path from segments
            let fullPath;
            if (/^[A-Za-z]:$/.test(segs[0])) {
                fullPath = segs[0] + (segs.length > 1 ? '/' + segs.slice(1).join('/') : '/');
            } else {
                fullPath = '/' + segs.join('/');
            }
            nodeMap.set(normKey, { name: segs[segs.length - 1], fullPath, children: [] });
        }
        return nodeMap.get(normKey);
    }

    for (const p of paths) {
        const parts = norm(p).split('/').filter(Boolean);
        for (let len = 1; len <= parts.length; len++) {
            ensureNode(parts.slice(0, len).join('/'), parts.slice(0, len));
        }
    }

    // Wire every node to its parent
    for (const [key, node] of nodeMap) {
        const parts = key.split('/');
        if (parts.length > 1) {
            const parent = nodeMap.get(parts.slice(0, -1).join('/'));
            if (parent && !parent.children.includes(node)) {
                parent.children.push(node);
            }
        }
    }

    // Find the deepest common ancestor across all paths
    const allParts = paths.map(p => norm(p).split('/').filter(Boolean));
    let commonLen = 0;
    while (
        commonLen < allParts[0].length &&
        allParts.every(parts => parts[commonLen] === allParts[0][commonLen])
    ) {
        commonLen++;
    }

    // Show the tree starting from the common ancestor (usually the scan root folder)
    let topLevel;
    if (commonLen > 0) {
        const commonKey = allParts[0].slice(0, commonLen).join('/');
        const commonNode = nodeMap.get(commonKey);
        topLevel = commonNode ? [commonNode] : [];
    } else {
        // Paths on different drives — show unique first segments
        const seen = new Set();
        topLevel = [];
        for (const parts of allParts) {
            if (!seen.has(parts[0])) {
                seen.add(parts[0]);
                const n = nodeMap.get(parts[0]);
                if (n) topLevel.push(n);
            }
        }
    }

    return { name: 'ALL FOLDERS', fullPath: null, children: topLevel };
}

function renderFolderTree(node, container, depth) {
    const hasChildren = node.children && node.children.length > 0;
    const nodeKey = node.fullPath ?? '__root__';

    // Expand root and its immediate children by default
    if (depth <= 1) expandedNodes.add(nodeKey);
    const isExpanded = expandedNodes.has(nodeKey);

    // Build the row element
    const row = document.createElement('div');
    row.className = 'tree-node' + (depth === 0 ? ' tree-node-root' : '');
    row.style.paddingLeft = `${depth * 0.9 + 0.4}rem`;
    if (node.fullPath) {
        row.dataset.path = node.fullPath;
        if (node.fullPath === selectedFolder) row.classList.add('selected');
    } else if (selectedFolder === null) {
        row.classList.add('selected');
    }

    // Chevron button (stops click from bubbling to row)
    const chevronBtn = document.createElement('button');
    chevronBtn.className = 'tree-chevron-btn';
    chevronBtn.type = 'button';
    chevronBtn.setAttribute('aria-label', 'Expand or collapse folder');
    if (!hasChildren) chevronBtn.tabIndex = -1;
    chevronBtn.innerHTML = `<i class="fa-solid fa-chevron-right tree-chevron${isExpanded ? ' open' : ''}${!hasChildren ? ' tree-chevron-hidden' : ''}" aria-hidden="true"></i>`;
    if (hasChildren) {
        chevronBtn.addEventListener('click', e => {
            e.stopPropagation();
            const expanded = expandedNodes.has(nodeKey);
            if (expanded) {
                expandedNodes.delete(nodeKey);
                chevronBtn.querySelector('.tree-chevron').classList.remove('open');
                childrenEl.classList.add('hidden');
                row.setAttribute('aria-expanded', 'false');
            } else {
                expandedNodes.add(nodeKey);
                chevronBtn.querySelector('.tree-chevron').classList.add('open');
                childrenEl.classList.remove('hidden');
                row.setAttribute('aria-expanded', 'true');
            }
        });
    }

    // Folder icon
    const icon = document.createElement('i');
    icon.className = node.fullPath ? 'fa-regular fa-folder tree-folder-icon' : 'fa-solid fa-folder-tree tree-folder-icon';

    // Label
    const label = document.createElement('span');
    label.className = 'tree-node-label';
    label.textContent = node.name;

    row.appendChild(chevronBtn);
    row.appendChild(icon);
    row.appendChild(label);

    // Keyboard + ARIA
    row.setAttribute('role', 'button');
    row.tabIndex = 0;
    row.setAttribute('aria-label', node.fullPath ? node.name : 'All folders');
    if (hasChildren) row.setAttribute('aria-expanded', String(isExpanded));

    // Row click / keyboard: select/deselect this folder
    row.addEventListener('click', () => selectTreeFolder(node.fullPath));
    row.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); selectTreeFolder(node.fullPath); }
    });

    container.appendChild(row);

    // Children container
    const childrenEl = document.createElement('div');
    childrenEl.className = 'tree-children' + (isExpanded ? '' : ' hidden');
    if (hasChildren) {
        for (const child of node.children) {
            renderFolderTree(child, childrenEl, depth + 1);
        }
        container.appendChild(childrenEl);
    }
}

function selectTreeFolder(path) {
    // Toggle: clicking the already-selected folder deselects it (shows all)
    selectedFolder = (selectedFolder === path) ? null : path;
    document.querySelectorAll('.tree-node').forEach(n => {
        const nodePath = n.dataset.path ?? null;
        n.classList.toggle('selected',
            selectedFolder === null ? nodePath === null : nodePath === selectedFolder
        );
    });
    loadVoices(searchInput.value.trim());
}

function toggleFolderTree() {
    treeOpen = !treeOpen;
    folderTreePanel.classList.toggle('collapsed', !treeOpen);
    treeToggleBtn.setAttribute('aria-expanded', String(treeOpen));
    treeToggleBtn.classList.toggle('active', treeOpen);
}

// -----------------------------------------------------------------------
// Type Filter Tabs
// -----------------------------------------------------------------------

function setTypeFilter(type) {
    selectedType = type;
    typeTabs.forEach(t => t.classList.toggle('active', t.dataset.type === type));
    loadVoices(searchInput.value.trim());
}

// -----------------------------------------------------------------------
// Tab Switching
// -----------------------------------------------------------------------

function switchTab(tab) {
    previousTab = tab;
    const toExplorer = tab === 'explorer';
    tabExplorer.classList.toggle('active', toExplorer);
    tabCleanup.classList.toggle('active', !toExplorer);
    tabExplorer.setAttribute('aria-selected', String(toExplorer));
    tabCleanup.setAttribute('aria-selected', String(!toExplorer));
    sectionExplorer.classList.toggle('hidden', !toExplorer);
    sectionCleanup.classList.toggle('hidden', toExplorer);
}

// -----------------------------------------------------------------------
// Voice Parameters Detail View
// -----------------------------------------------------------------------

// Escapes a value for interpolation into an HTML template literal.
//
// Serializing a text node via innerHTML only escapes & < >, which is enough in
// element-content position but NOT inside an attribute — so quotes are escaped
// explicitly here. That makes this helper safe in both positions, including
// title="${escapeHtml(x)}".
function escapeHtml(str) {
    return (str == null ? '' : String(str))
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function signedStr(n) {
    return n > 0 ? `+${n}` : String(n);
}

// DX7-style 4-rate / 4-level envelope drawn as an SVG contour:
// L4 -> R1 -> L1 -> R2 -> L2 -> R3 -> L3 (sustain) -> KEY OFF -> R4 -> L4.
// Ported from design_handoff_voice_parameters/Voice Parameters Page.dc.html's
// envSvg() (React-based reference) to a plain function returning an SVG markup
// string — same geometry/math, no framework.
function envSvg(rates, levels, opts) {
    const o = opts || {};
    const W = o.W || 320, H = o.H || 78, stroke = o.stroke || 'var(--ds-signal)', sw = o.sw || 1.75;
    const padT = o.labels ? 18 : 8, padB = o.keyText ? 18 : 12;
    const padL = o.labels ? 20 : 6, padR = o.labels ? 20 : 6;
    const x0 = padL, x1 = W - padR, yTop = padT, yBot = H - padB;
    const yOf = (lv) => yBot - (lv / 99) * (yBot - yTop);
    const L1 = levels[0], L2 = levels[1], L3 = levels[2], L4 = levels[3];
    const R1 = rates[0], R2 = rates[1], R3 = rates[2];
    const t1 = Math.abs(L1 - L4) / Math.max(R1, 3);
    const t2 = Math.abs(L2 - L1) / Math.max(R2, 3);
    const t3 = Math.abs(L3 - L2) / Math.max(R3, 3);
    const preSum = (t1 + t2 + t3) || 1, innerW = x1 - x0;
    const preW = innerW * 0.54, susW = innerW * 0.16, relW = innerW * 0.30;
    const w1 = preW * t1 / preSum, w2 = preW * t2 / preSum, w3 = preW * t3 / preSum;
    const P = [[x0, yOf(L4)], [x0 + w1, yOf(L1)], [x0 + w1 + w2, yOf(L2)], [x0 + w1 + w2 + w3, yOf(L3)]];
    const keyOffX = P[3][0] + susW;
    P.push([keyOffX, yOf(L3)]);
    P.push([keyOffX + relW, yOf(L4)]);
    const rnd = (n) => Math.round(n * 10) / 10;
    const pts = P.map(p => rnd(p[0]) + ',' + rnd(p[1])).join(' ');

    let extras = '';
    if (o.grid) {
        for (let i = 0; i < 4; i++) {
            const y = yTop + i * ((yBot - yTop) / 3);
            extras += `<line x1="${padL - 2}" y1="${y}" x2="${W - padR + 2}" y2="${y}" stroke="var(--ds-elevated-2)" stroke-width="1" />`;
        }
    }
    if (o.keys) {
        extras += `<line x1="${P[0][0]}" y1="${yTop}" x2="${P[0][0]}" y2="${yBot}" stroke="var(--ds-text-4)" stroke-width="1" stroke-dasharray="2 3" vector-effect="non-scaling-stroke" />`;
        extras += `<line x1="${keyOffX}" y1="${yTop}" x2="${keyOffX}" y2="${yBot}" stroke="var(--ds-text-4)" stroke-width="1" stroke-dasharray="2 3" vector-effect="non-scaling-stroke" />`;
    }
    extras += `<line x1="0" y1="${yBot}" x2="${W}" y2="${yBot}" stroke="var(--ds-border)" stroke-width="1" />`;

    let fillPoly = '';
    if (o.fill) {
        const area = pts + ' ' + rnd(P[5][0]) + ',' + yBot + ' ' + rnd(P[0][0]) + ',' + yBot;
        fillPoly = `<polygon points="${area}" fill="${o.fill}" stroke="none" />`;
    }

    const line = `<polyline points="${pts}" fill="none" stroke="${stroke}" stroke-width="${sw}" stroke-linejoin="round" stroke-linecap="round" vector-effect="non-scaling-stroke" />`;

    const dotR = o.labels ? 2.4 : 1.9;
    const dots = [P[1], P[2], P[3]]
        .map(p => `<circle cx="${rnd(p[0])}" cy="${rnd(p[1])}" r="${dotR}" fill="${stroke}" />`)
        .join('');

    let labels = '';
    if (o.labels) {
        const tf = 'var(--ds-font-mono)', tc = 'var(--ds-text-3)';
        const T = (x, y, s, anchor) =>
            `<text x="${rnd(x)}" y="${rnd(y)}" font-size="var(--ds-fs-micro)" fill="${tc}" font-family="${tf}" text-anchor="${anchor || 'middle'}">${s}</text>`;
        labels += T(P[1][0], P[1][1] - 6, 'L1');
        labels += T(P[2][0], P[2][1] - 6, 'L2');
        labels += T(P[3][0], P[3][1] - 6, 'L3');
        labels += T(P[0][0], P[0][1] - 6, 'L4', 'start');
        labels += T(P[5][0], P[5][1] - 6, 'L4', 'end');
        labels += T((P[0][0] + P[1][0]) / 2 - 5, (P[0][1] + P[1][1]) / 2, 'R1', 'end');
        labels += T((P[1][0] + P[2][0]) / 2 + 5, (P[1][1] + P[2][1]) / 2, 'R2', 'start');
        labels += T((P[2][0] + P[3][0]) / 2, (P[2][1] + P[3][1]) / 2 - 5, 'R3');
        labels += T((P[4][0] + P[5][0]) / 2 + 4, (P[4][1] + P[5][1]) / 2, 'R4', 'start');
    }

    let keyText = '';
    if (o.keyText) {
        const tf = 'var(--ds-font-mono)';
        keyText += `<text x="${P[0][0]}" y="${H - 4}" font-size="var(--ds-fs-micro)" fill="var(--ds-text-4)" font-family="${tf}" text-anchor="start">KEY ON</text>`;
        keyText += `<text x="${keyOffX}" y="${H - 4}" font-size="var(--ds-fs-micro)" fill="var(--ds-text-4)" font-family="${tf}" text-anchor="middle">KEY OFF</text>`;
    }

    return `<svg viewBox="0 0 ${W} ${H}" width="100%" height="${H}" preserveAspectRatio="none" style="display:block;overflow:visible;">${extras}${fillPoly}${line}${dots}${labels}${keyText}</svg>`;
}

// LFO waveform preview. Ported from the same reference file's waveSvg().
function waveSvg(shape, opts) {
    const o = opts || {};
    const W = o.W || 120, H = o.H || 44, stroke = o.stroke || 'var(--ds-signal)', sw = o.sw || 1.75;
    const midY = H / 2, amp = H / 2 - 6, cyc = 2, seg = W / (cyc * 2);
    let pts = [];
    if (/tri/i.test(shape)) {
        for (let i = 0; i <= cyc * 2; i++) pts.push([i * seg, i % 2 === 0 ? midY + amp : midY - amp]);
    } else if (/saw/i.test(shape)) {
        for (let i = 0; i < cyc; i++) {
            pts.push([i * seg * 2, midY + amp]);
            pts.push([(i + 1) * seg * 2 - 0.5, midY - amp]);
            pts.push([(i + 1) * seg * 2, midY + amp]);
        }
    } else if (/squ/i.test(shape)) {
        let up = false;
        for (let i = 0; i <= cyc * 2; i++) {
            const x = i * seg;
            pts.push([x, up ? midY - amp : midY + amp]);
            pts.push([x, up ? midY + amp : midY - amp]);
            up = !up;
        }
    } else {
        for (let i = 0; i <= 48; i++) {
            const x = W * i / 48;
            const y = midY - Math.sin((i / 48) * Math.PI * 2 * cyc) * amp;
            pts.push([x, y]);
        }
    }
    const rnd = (n) => Math.round(n * 10) / 10;
    const s = pts.map(p => rnd(p[0]) + ',' + rnd(p[1])).join(' ');
    return `<svg viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" preserveAspectRatio="none" style="display:block;"><polyline points="${s}" fill="none" stroke="${stroke}" stroke-width="${sw}" stroke-linejoin="round" stroke-linecap="round" vector-effect="non-scaling-stroke" /></svg>`;
}

async function showVoiceDetail(voiceId) {
    // The button that opened this view is about to be hidden, so remember it
    // to restore focus on the way back. Otherwise focus falls to <body> and the
    // next Tab restarts from the top of the document.
    detailReturnFocus = document.activeElement;
    tabBar.classList.add('hidden');
    sectionExplorer.classList.add('hidden');
    sectionCleanup.classList.add('hidden');
    sectionDetail.classList.remove('hidden');
    detailHeader.innerHTML = '<div class="loading-state"><div class="retro-loader"></div><p>Loading voice parameters...</p></div>';
    detailOperators.innerHTML = '';
    detailModulation.innerHTML = '';
    detailKeymode.innerHTML = '';
    detailControllers.innerHTML = '';
    window.scrollTo(0, 0);
    // Move focus into the view so screen readers land on the new content.
    sectionDetail.focus();

    try {
        const data = await fetchJson(`/api/voices/${voiceId}/parameters`);
        renderVoiceDetail(data);
    } catch (e) {
        showToast(e.message, 'error');
        backFromDetail();
    }
}

// Element to restore focus to when the detail view closes.
let detailReturnFocus = null;

function backFromDetail() {
    sectionDetail.classList.add('hidden');
    tabBar.classList.remove('hidden');
    switchTab(previousTab);
    if (detailReturnFocus && document.contains(detailReturnFocus)) {
        detailReturnFocus.focus();
    }
    detailReturnFocus = null;
}

function renderVoiceDetail(data) {
    renderDetailHeader(data);
    renderDetailOperators(data);
    renderDetailModulation(data);
    renderDetailKeyMode(data);
    renderDetailControllers(data);
}

function renderDetailHeader(data) {
    const typeCfg = TYPE_CFG[data.patch_type] || { label: data.patch_type || '?', cls: '', icon: 'fa-question' };
    const carriers = new Set(data.algorithm_carriers || []);

    // Static 2x3 grid position, real carrier/modulator coloring per algorithm.
    const gridOrder = [6, 5, 4, 3, 2, 1];
    const nodesHtml = gridOrder.map((n, i) => {
        const isCarrier = carriers.has(n);
        const top = i < 3 ? '0px' : '38px';
        const left = `${(i % 3) * 33}px`;
        const cls = isCarrier ? 'vd-alg-node vd-alg-node-carrier' : 'vd-alg-node';
        return `<div class="${cls}" style="top:${top};left:${left};">${n}</div>`;
    }).join('');

    const keyStats = [
        { l: 'ALGORITHM', v: data.algorithm },
        { l: 'FEEDBACK', v: data.feedback },
        { l: 'OSC SYNC', v: data.osc_key_sync ? 'On' : 'Off' },
        { l: 'TRANSPOSE', v: data.transpose_name },
        { l: 'KEY MODE', v: data.additional.key_mode_assign },
        { l: 'P.MOD SENS', v: data.lfo.pitch_mod_sensitivity },
    ];
    const statsHtml = keyStats.map(s => `
        <div class="vd-stat">
            <div class="vd-stat-label">${escapeHtml(s.l)}</div>
            <div class="vd-stat-value">${escapeHtml(String(s.v))}</div>
        </div>`).join('');

    detailHeader.innerHTML = `
        <div class="vd-header-left">
            <div class="vd-brand-mark">DX</div>
            <div>
                <div class="vd-name-row">
                    <h1 class="vd-name">${escapeHtml(data.voice_name)}</h1>
                    <span class="type-badge ${escapeHtml(typeCfg.cls)}"><i class="fa-solid ${escapeHtml(typeCfg.icon)}" aria-hidden="true"></i> ${escapeHtml(typeCfg.label)}</span>
                </div>
                <div class="vd-meta">${escapeHtml(data.file_name)} &middot; POS ${data.position} &middot; ALG ${data.algorithm}</div>
            </div>
        </div>
        <div class="vd-alg-diagram">${nodesHtml}</div>
        <div class="vd-key-stats">${statsHtml}</div>
    `;
}

function renderDetailOperators(data) {
    const carriers = new Set(data.algorithm_carriers || []);
    const fbOp = data.algorithm_feedback_op;

    const tiles = data.operators.map(op => {
        const isCarrier = carriers.has(op.op);
        const fbIcon = op.op === fbOp
            ? '<i class="fa-solid fa-rotate-right vd-fb-icon" aria-hidden="true" title="Feedback operator"></i>'
            : '';
        const meterPct = Math.round((op.level / 99) * 100);
        const eg = envSvg(op.eg_rate, op.eg_level, {
            W: 320, H: 74, stroke: 'var(--ds-signal)', sw: 1.75, keys: true, fill: 'var(--ds-signal-fill-strong)'
        });
        return `
        <div class="op-tile">
            <div class="op-tile-head">
                <span class="op-tile-title">
                    <span class="op-dot ${isCarrier ? 'op-dot-carrier' : ''}"></span>
                    OP${op.op} ${fbIcon}
                </span>
                <span class="op-role-tag">${isCarrier ? 'Carrier' : 'Modulator'}</span>
            </div>
            <div class="op-eg-panel">${eg}</div>
            <div class="op-meter">
                <div class="op-meter-row"><span>OUTPUT LEVEL</span><span>${op.level}</span></div>
                <div class="op-meter-track"><div class="op-meter-fill" style="width:${meterPct}%;"></div></div>
            </div>
            <div class="op-eg-numbers">
                <span class="op-eg-label">EG-R</span><span class="op-eg-value">${op.eg_rate.join(' &middot; ')}</span>
                <span class="op-eg-label">EG-L</span><span class="op-eg-value">${op.eg_level.join(' &middot; ')}</span>
            </div>
            <div class="op-summary">
                <div>${escapeHtml(op.osc_mode.toUpperCase())} COARSE ${escapeHtml(op.freq_coarse)} FINE ${escapeHtml(op.freq_fine)} &middot; DET ${escapeHtml(signedStr(op.detune))} &middot; RS ${escapeHtml(op.rate_scaling)}</div>
                <div>${escapeHtml(op.left_curve_name)}/${escapeHtml(op.left_depth)} &middot; BP ${escapeHtml(op.break_point_name)} &middot; ${escapeHtml(op.right_curve_name)}/${escapeHtml(op.right_depth)}</div>
                <div>KEY VEL ${op.vel_sens} &middot; AM SENS ${op.amp_mod_sens}</div>
            </div>
        </div>`;
    }).join('');

    detailOperators.innerHTML = `
        <div class="vd-section-heading"><span class="vd-section-index">01</span><h2>Operators</h2></div>
        <div class="op-grid">${tiles}</div>
    `;
}

function renderDetailModulation(data) {
    const lfo = data.lfo;
    const peg = data.pitch_eg;
    const a = data.additional;

    const lfoWave = waveSvg(lfo.wave_name, { W: 130, H: 46, stroke: 'var(--ds-signal)', sw: 1.9 });
    const pegSvg = envSvg(peg.rate, peg.level, {
        W: 560, H: 150, stroke: 'var(--ds-perf)', sw: 2, keys: true, grid: true, labels: true, keyText: true,
        fill: 'var(--ds-perf-fill-strong)'
    });

    detailModulation.innerHTML = `
        <div class="vd-section-heading"><span class="vd-section-index">02</span><h2>Modulation</h2></div>
        <div class="vd-mod-grid">
            <div class="vd-card-inner">
                <div class="vd-card-title"><i class="fa-solid fa-wave-square" aria-hidden="true" style="color:var(--ds-signal);"></i> LFO <span class="vd-card-tag">${escapeHtml(lfo.wave_name)}</span></div>
                <div class="vd-inset-panel vd-lfo-panel">${lfoWave}</div>
                <div class="vd-kv-grid">
                    <div><span>Wave</span><span>${escapeHtml(lfo.wave_name)}</span></div>
                    <div><span>Speed</span><span>${lfo.speed}</span></div>
                    <div><span>Delay</span><span>${lfo.delay}</span></div>
                    <div><span>Mode</span><span>${escapeHtml(a.lfo_key_trigger)}</span></div>
                    <div><span>PM Depth</span><span>${lfo.pmd}</span></div>
                    <div><span>AM Depth</span><span>${lfo.amd}</span></div>
                    <div><span>Key Sync</span><span>${lfo.sync ? 'On' : 'Off'}</span></div>
                </div>
            </div>
            <div class="vd-card-inner">
                <div class="vd-card-title"><i class="fa-solid fa-chart-line" aria-hidden="true" style="color:var(--ds-perf);"></i> Pitch EG <span class="vd-card-tag">RANGE ${escapeHtml(a.pitch_eg_range)}</span></div>
                <div class="vd-inset-panel">${pegSvg}</div>
                <div class="vd-stat-row">
                    <span>RATES <strong>${peg.rate.join(' &middot; ')}</strong></span>
                    <span>LEVELS <strong>${peg.level.join(' &middot; ')}</strong></span>
                    <span>VELOCITY <strong>${a.pitch_eg_velocity ? 'On' : 'Off'}</strong></span>
                    <span>RATE SCL <strong>${a.pitch_eg_rate_scaling}</strong></span>
                </div>
            </div>
        </div>
    `;
}

function renderDetailControllers(data) {
    const a = data.additional;
    const rowsA = [
        { src: 'BC', pm: a.breath_controller.pitch, am: a.breath_controller.amp, eg: a.breath_controller.eg_bias, extra: signedStr(a.breath_controller.pitch_bias) },
        { src: 'AT', pm: a.aftertouch.pitch, am: a.aftertouch.amp, eg: a.aftertouch.eg_bias, extra: signedStr(a.aftertouch.pitch_bias) },
        { src: 'MW', pm: a.mod_wheel.pitch, am: a.mod_wheel.amp, eg: a.mod_wheel.eg_bias, extra: '&mdash;' },
    ];
    const rowsB = [
        { src: 'FC1', pm: a.foot_controller_1.pitch, am: a.foot_controller_1.amp, eg: a.foot_controller_1.eg_bias, extra: a.foot_controller_1.volume },
        { src: 'FC2', pm: a.foot_controller_2.pitch, am: a.foot_controller_2.amp, eg: a.foot_controller_2.eg_bias, extra: a.foot_controller_2.volume },
        { src: 'MIDI', pm: a.midi_controller.pitch, am: a.midi_controller.amp, eg: a.midi_controller.eg_bias, extra: a.midi_controller.volume },
    ];

    const buildTable = (cols, rows) => `
        <table class="vd-controller-table">
            <thead><tr><th></th>${cols.map(c => `<th>${c}</th>`).join('')}</tr></thead>
            <tbody>${rows.map(r => `<tr><td class="vd-ct-src">${r.src}</td><td>${r.pm}</td><td>${r.am}</td><td>${r.eg}</td><td>${r.extra}</td></tr>`).join('')}</tbody>
        </table>`;

    detailControllers.innerHTML = `
        <div class="vd-section-heading">
            <span class="vd-section-index">04</span><h2>Controllers</h2>
            ${defaultsTag(a.present)}
        </div>
        <div class="vd-two-col ${defaultedClass(a.present)}">
            <div class="vd-card-inner">
                <div class="vd-card-title"><i class="fa-solid fa-lungs" aria-hidden="true" style="color:var(--ds-signal);"></i> BC / AT / MW</div>
                ${buildTable(['PM', 'AM', 'EG BIAS', 'P.BIAS'], rowsA)}
            </div>
            <div class="vd-card-inner">
                <div class="vd-card-title"><i class="fa-solid fa-sliders" aria-hidden="true" style="color:var(--ds-signal);"></i> FC1 / FC2 / MIDI</div>
                ${buildTable(['PM', 'AM', 'EG BIAS', 'VOL'], rowsB)}
                <div class="vd-footnote">FC1 &rarr; CS1: ${a.fc1_as_cs1 ? 'On' : 'Off'}</div>
            </div>
        </div>
    `;
}

function defaultsTag(present) {
    return present
        ? ''
        : '<span class="vd-defaults-tag" title="Not stored in this voice format — showing power-on default values">DEFAULT VALUES</span>';
}

function defaultedClass(present) {
    return present ? '' : 'vd-defaulted';
}

function renderDetailKeyMode(data) {
    const a = data.additional;
    detailKeymode.innerHTML = `
        <div class="vd-section-heading">
            <span class="vd-section-index">03</span><h2>Key Mode, Pitch Bend &amp; Portamento</h2>
            ${defaultsTag(a.present)}
        </div>
        <div class="vd-two-col ${defaultedClass(a.present)}">
            <div class="vd-card-inner">
                <div class="vd-card-title"><i class="fa-solid fa-object-group" aria-hidden="true" style="color:var(--ds-signal);"></i> Key Mode</div>
                <div class="vd-kv-stack">
                    <div><span>Assign</span><span>${escapeHtml(a.key_mode_assign)}</span></div>
                    <div><span>Unison Detune</span><span>${a.unison_detune}</span></div>
                </div>
            </div>
            <div class="vd-card-inner">
                <div class="vd-card-title"><i class="fa-solid fa-arrows-left-right" aria-hidden="true" style="color:var(--ds-signal);"></i> Pitch Bend &amp; Portamento</div>
                <div class="vd-kv-grid">
                    <div><span>Bend Mode</span><span>${escapeHtml(a.pitch_bend_mode)}</span></div>
                    <div><span>Bend Range</span><span>${a.pitch_bend_range} semi</span></div>
                    <div><span>Bend Step</span><span>${a.pitch_bend_step}</span></div>
                    <div><span>Porta Mode</span><span>${escapeHtml(a.portamento_mode)}</span></div>
                    <div><span>Porta Time</span><span>${a.portamento_time}</span></div>
                    <div><span>Porta Step</span><span>${a.portamento_step}</span></div>
                    <div><span>Random Pitch</span><span>${a.random_pitch}</span></div>
                </div>
            </div>
        </div>
    `;
}

// -----------------------------------------------------------------------
// Cleanup: Duplicate Folder Detection & Deletion
// -----------------------------------------------------------------------

async function loadDuplicates() {
    dupGroupsContainer.innerHTML = '';
    dupEmpty.classList.add('hidden');
    dupInitial.classList.add('hidden');
    dupLoading.classList.remove('hidden');
    findDuplicatesBtn.disabled = true;
    findDupBtnText.classList.add('hidden');
    findDupSpinner.classList.remove('hidden');

    try {
        const groups = await fetchJson('/api/duplicates');
        dupLoading.classList.add('hidden');

        if (groups.length === 0) {
            dupEmpty.classList.remove('hidden');
        } else {
            renderDuplicateGroups(groups);
        }
    } catch (e) {
        dupLoading.classList.add('hidden');
        dupInitial.classList.remove('hidden');
        showToast(e.message, 'error');
    } finally {
        findDuplicatesBtn.disabled = false;
        findDupBtnText.classList.remove('hidden');
        findDupSpinner.classList.add('hidden');
    }
}

function renderDuplicateGroups(groups) {
    dupGroupsContainer.innerHTML = '';
    groups.forEach(group => {
        const groupEl = document.createElement('div');
        groupEl.className = 'dup-group';
        groupEl.dataset.fingerprint = group.fingerprint;

        const fileCount = group.folders[0].file_count;
        groupEl.innerHTML = `
            <div class="dup-group-header">
                <span class="dup-group-badge">
                    <i class="fa-solid fa-copy" aria-hidden="true"></i>
                    ${group.folders.length} folders &mdash; identical content
                </span>
                <span class="dup-file-count-label">
                    <i class="fa-solid fa-file-audio" aria-hidden="true"></i>
                    ${fileCount} file${fileCount !== 1 ? 's' : ''} each
                </span>
            </div>
            <div class="dup-folder-list"></div>
            <div class="dup-group-footer">
                <button class="btn btn-danger dup-delete-btn">
                    <i class="fa-solid fa-trash-can" aria-hidden="true"></i> DELETE UNSELECTED
                </button>
            </div>
        `;

        const folderList = groupEl.querySelector('.dup-folder-list');
        group.folders.forEach((folder, idx) => {
            const row = document.createElement('div');
            row.className = 'dup-folder-row ' + (idx === 0 ? 'dup-row-keep' : 'dup-row-will-delete');
            row.dataset.folderPath = folder.folder_path;

            const radioName = `keep-${group.fingerprint}`;
            const radioId = `radio-${group.fingerprint}-${idx}`;

            row.innerHTML = `
                <label class="dup-radio-label" for="${radioId}">
                    <input type="radio" id="${radioId}" name="${radioName}"
                           ${idx === 0 ? 'checked' : ''}>
                    <span class="dup-radio-indicator"><i class="fa-solid fa-check" aria-hidden="true"></i></span>
                    <span class="dup-keep-label">${idx === 0 ? 'KEEP' : 'DEL'}</span>
                </label>
                <div class="dup-folder-info">
                    <span class="dup-folder-path"></span>
                    <span class="dup-folder-meta">${folder.file_count} file${folder.file_count !== 1 ? 's' : ''}</span>
                </div>
                <button class="btn-reveal dup-reveal-btn" title="Reveal in Explorer">
                    <i class="fa-regular fa-folder-open" aria-hidden="true"></i>
                </button>
            `;
            // Set user-derived data via DOM properties to avoid XSS
            const radioInput = row.querySelector('input[type="radio"]');
            radioInput.value = folder.folder_path;
            const pathSpan = row.querySelector('.dup-folder-path');
            pathSpan.textContent = folder.folder_path;
            pathSpan.title = folder.folder_path;

            row.querySelector('input[type="radio"]').addEventListener('change', () =>
                updateGroupRowStates(folderList)
            );
            row.querySelector('.dup-reveal-btn').addEventListener('click', () =>
                revealInExplorer(folder.example_file_path)
            );
            folderList.appendChild(row);
        });

        groupEl.querySelector('.dup-delete-btn').addEventListener('click', () =>
            handleDeleteGroup(groupEl)
        );
        dupGroupsContainer.appendChild(groupEl);
    });
}

function updateGroupRowStates(folderList) {
    const checked = folderList.querySelector('input[type="radio"]:checked');
    folderList.querySelectorAll('.dup-folder-row').forEach(row => {
        const isKeep = row.querySelector('input[type="radio"]') === checked;
        row.classList.toggle('dup-row-keep', isKeep);
        row.classList.toggle('dup-row-will-delete', !isKeep);
        row.querySelector('.dup-keep-label').textContent = isKeep ? 'KEEP' : 'DEL';
    });
}

async function handleDeleteGroup(groupEl) {
    const toDelete = [...groupEl.querySelectorAll('.dup-row-will-delete')]
        .map(row => row.dataset.folderPath);

    if (toDelete.length === 0) {
        showToast('All folders in this group are marked KEEP — nothing to delete.', 'info');
        return;
    }

    const pathList = toDelete.map(p => `  • ${p}`).join('\n');
    if (!confirm(
        `This will PERMANENTLY DELETE the following folder(s) and ALL their contents:\n\n` +
        pathList +
        `\n\nThis cannot be undone. Continue?`
    )) return;

    const deleteBtn = groupEl.querySelector('.dup-delete-btn');
    deleteBtn.disabled = true;
    deleteBtn.innerHTML = '<span class="spinner"></span> DELETING...';

    let deleted = 0;
    let errors = 0;
    for (const folder_path of toDelete) {
        try {
            // fetchJson throws on a non-OK status, including the {error: ...}
            // body returned when rmtree fails. Deciding success purely on the
            // absence of an `error` key previously turned a failed delete into
            // a green "Deleted N folder(s) successfully."
            const result = await fetchJson('/api/delete-folder', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ folder_path })
            });
            if (result.error) {
                errors++;
                showToast(`Error: ${result.error}`, 'error');
            } else {
                deleted++;
            }
        } catch (e) {
            errors++;
            showToast(`Could not delete ${folder_path}: ${e.message}`, 'error');
        }
    }

    if (errors === 0) {
        showToast(`Deleted ${deleted} folder(s) successfully.`, 'success');
    } else if (deleted > 0) {
        showToast(`Deleted ${deleted} of ${toDelete.length}; ${errors} failed.`, 'error');
    }

    // Refresh the duplicate list to reflect the new state
    await loadDuplicates();
}

// Toast Notification Manager
let toastTimeout = null;
function showToast(message, type = 'info') {
    if (toastTimeout) clearTimeout(toastTimeout);
    
    toastMessage.textContent = message;
    
    // Set Icon and style based on type
    if (type === 'success') {
        toastIcon.className = 'fa-solid fa-circle-check';
        toast.style.borderColor = 'var(--ds-success)';
        toastIcon.style.color = 'var(--ds-success)';
    } else if (type === 'error') {
        toastIcon.className = 'fa-solid fa-circle-exclamation';
        toast.style.borderColor = 'var(--ds-danger)';
        toastIcon.style.color = 'var(--ds-danger)';
    } else {
        toastIcon.className = 'fa-solid fa-circle-info';
        toast.style.borderColor = 'var(--ds-signal)';
        toastIcon.style.color = 'var(--ds-signal)';
    }
    
    toast.classList.remove('hidden');
    toast.style.opacity = '1';
    toast.style.transform = 'translateY(0)';
    
    toastTimeout = setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateY(20px)';
        toastTimeout = setTimeout(() => {
            toast.classList.add('hidden');
        }, 300);
    }, TOAST_DURATION_MS);
}
