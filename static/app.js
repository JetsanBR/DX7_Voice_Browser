// Constants
const POLL_INTERVAL_MS   = 500;
const SEARCH_DEBOUNCE_MS = 300;
const TOAST_DURATION_MS  = 4000;

// State Management
let allVoices = [];      // Current page of grouped results from server (up to LIMIT)
let filteredVoices = []; // Sorted view for rendering
let totalVoices = 0;     // Total matching unique patch names in the database
let isScanning = false;
let statusInterval = null;
let searchDebounceTimer = null;
let voicesAbortController = null;
let currentSort = { key: 'name', asc: true };

// Folder tree state
let selectedFolder = null;  // null = all folders
let selectedType = '';       // '' = all types
let treeOpen = true;
let expandedNodes = new Set();

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
const lcdActiveFile = document.getElementById('lcd-active-file');
const lcdProgress = document.getElementById('lcd-progress');

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
});

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
        if (e.name === 'AbortError') return;
        showToast(e.message, 'error');
    } finally {
        showLoading(false);
    }
}

// Open native OS folder picker and populate the directory input
async function handleBrowseFolder() {
    try {
        const response = await fetch('/api/browse-folder');
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
        const response = await fetch('/api/scan', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ directory })
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.detail || "Scan request failed.");
        }
        
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
        } catch (e) {
            showToast('Connection error while polling scan status.', 'error');
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
        const response = await fetch('/api/clear', { method: 'POST' });
        const data = await response.json();
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
        const response = await fetch('/api/reveal', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ file_path: filePath })
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || "Failed to reveal file.");
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
        const response = await fetch(`/api/voices/files?${params}`);
        if (!response.ok) throw new Error("Failed to fetch file list.");
        const files = await response.json();

        modalLoading.classList.add('hidden');
        renderModalList(files);
    } catch (e) {
        modalLoading.classList.add('hidden');
        const errEl = document.createElement('div');
        errEl.className = 'modal-error';
        errEl.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i> ';
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
        nameEl.innerHTML = '<i class="fa-solid fa-file-audio"></i>';
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

        const revealBtn = document.createElement('button');
        revealBtn.className = 'btn-reveal modal-reveal-btn';
        revealBtn.title = 'Reveal in Explorer';
        revealBtn.innerHTML = '<i class="fa-regular fa-folder-open"></i>';
        revealBtn.addEventListener('click', () => revealInExplorer(f.file_path));

        item.appendChild(indexEl);
        item.appendChild(infoEl);
        item.appendChild(revealBtn);
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
function handleSort(key) {
    if (currentSort.key === key) {
        currentSort.asc = !currentSort.asc;
    } else {
        currentSort.key = key;
        currentSort.asc = true;
    }
    
    // Update visual header indicator arrows
    tableHeaders.forEach(th => {
        const icon = th.querySelector('i');
        if (th.getAttribute('data-sort') === key) {
            icon.className = currentSort.asc ? 'fa-solid fa-sort-up' : 'fa-solid fa-sort-down';
            th.classList.add('active-sort');
            th.setAttribute('aria-sort', currentSort.asc ? 'ascending' : 'descending');
        } else {
            icon.className = 'fa-solid fa-sort';
            th.classList.remove('active-sort');
            th.removeAttribute('aria-sort');
        }
    });
    
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
    
    const TYPE_CFG = {
        'Voice':          { label: 'VOICE',  cls: 'type-badge-voice', icon: 'fa-wave-square' },
        'Performance':    { label: 'PERF',   cls: 'type-badge-perf',  icon: 'fa-layer-group' },
        'Gen 2 Extended': { label: 'GEN 2',  cls: 'type-badge-gen2',  icon: 'fa-sliders' },
    };

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
        typeBadge.innerHTML = `<i class="fa-solid ${typeCfg.icon}"></i> ${typeCfg.label}`;
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
        fileWrapper.innerHTML = `<i class="fa-solid fa-file-audio"></i> <span>${voice.file_name}</span>`;
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
            badge.innerHTML = `<i class="fa-solid fa-layer-group"></i> ${fileCount}`;
            badge.addEventListener('click', () => showFilesModal(voice.voice_name, voice.patch_type));
            tdFiles.appendChild(badge);
        } else {
            const badge = document.createElement('span');
            badge.className = 'file-count-badge file-count-single';
            badge.title = '1 file contains this patch';
            badge.innerHTML = `<i class="fa-solid fa-file"></i> 1`;
            tdFiles.appendChild(badge);
        }

        // Action Column
        const tdAction = document.createElement('td');
        tdAction.className = 'col-actions';
        const revealBtn = document.createElement('button');
        revealBtn.className = 'btn-reveal';
        revealBtn.innerHTML = '<i class="fa-regular fa-folder-open"></i>';
        revealBtn.title = "Reveal file in Windows Explorer";
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
        const response = await fetch('/api/folders');
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const paths = await response.json();
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
    loadVoices(searchInput.value);
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
    loadVoices(searchInput.value);
}

// -----------------------------------------------------------------------
// Tab Switching
// -----------------------------------------------------------------------

function switchTab(tab) {
    const toExplorer = tab === 'explorer';
    tabExplorer.classList.toggle('active', toExplorer);
    tabCleanup.classList.toggle('active', !toExplorer);
    tabExplorer.setAttribute('aria-selected', String(toExplorer));
    tabCleanup.setAttribute('aria-selected', String(!toExplorer));
    sectionExplorer.classList.toggle('hidden', !toExplorer);
    sectionCleanup.classList.toggle('hidden', toExplorer);
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
        const res = await fetch('/api/duplicates');
        if (!res.ok) throw new Error((await res.json()).detail || 'Failed to load duplicates.');
        const groups = await res.json();
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
                    <i class="fa-solid fa-copy"></i>
                    ${group.folders.length} folders &mdash; identical content
                </span>
                <span class="dup-file-count-label">
                    <i class="fa-solid fa-file-audio"></i>
                    ${fileCount} file${fileCount !== 1 ? 's' : ''} each
                </span>
            </div>
            <div class="dup-folder-list"></div>
            <div class="dup-group-footer">
                <button class="btn btn-danger dup-delete-btn">
                    <i class="fa-solid fa-trash-can"></i> DELETE UNSELECTED
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
                    <span class="dup-radio-indicator"><i class="fa-solid fa-check"></i></span>
                    <span class="dup-keep-label">${idx === 0 ? 'KEEP' : 'DEL'}</span>
                </label>
                <div class="dup-folder-info">
                    <span class="dup-folder-path"></span>
                    <span class="dup-folder-meta">${folder.file_count} file${folder.file_count !== 1 ? 's' : ''}</span>
                </div>
                <button class="btn-reveal dup-reveal-btn" title="Reveal in Explorer">
                    <i class="fa-regular fa-folder-open"></i>
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

    let errors = 0;
    for (const folder_path of toDelete) {
        try {
            const res = await fetch('/api/delete-folder', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ folder_path })
            });
            const result = await res.json();
            if (result.error) {
                errors++;
                showToast(`Error: ${result.error}`, 'error');
            }
        } catch (e) {
            errors++;
            showToast(`Network error deleting ${folder_path}`, 'error');
        }
    }

    if (errors === 0) {
        showToast(`Deleted ${toDelete.length} folder(s) successfully.`, 'success');
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
