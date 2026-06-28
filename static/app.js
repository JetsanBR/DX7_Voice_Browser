// State Management
let allVoices = [];      // Current page of grouped results from server (up to LIMIT)
let filteredVoices = []; // Sorted view for rendering
let totalVoices = 0;     // Total matching unique voice names in the database
let isScanning = false;
let statusInterval = null;
let searchDebounceTimer = null;
let currentSort = { key: 'name', asc: true };

// DOM Elements
const dirInput = document.getElementById('dir-input');
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
    checkScanStatusOnLoad();
    setupEventListeners();
});

// Event Listeners Setup
function setupEventListeners() {
    // Scan Button
    scanBtn.addEventListener('click', handleScanTrigger);
    
    // Clear Database Button
    clearBtn.addEventListener('click', handleClearDatabase);
    
    // Search Input
    searchInput.addEventListener('input', handleSearchInput);
    clearSearchBtn.addEventListener('click', clearSearch);
    
    // Table Header Sorting
    tableHeaders.forEach(th => {
        th.addEventListener('click', () => {
            const sortKey = th.getAttribute('data-sort');
            handleSort(sortKey);
        });
    });

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
        if (e.key === 'Escape') closeFilesModal();
    });
}

// Check if scanning is running (e.g. if page reloaded during scan)
async function checkScanStatusOnLoad() {
    try {
        const response = await fetch('/api/scan-status');
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

// Fetch grouped voices from backend — one row per unique name, capped at LIMIT
async function loadVoices(query = '') {
    showLoading(true);
    try {
        const url = query
            ? `/api/voices?q=${encodeURIComponent(query)}`
            : '/api/voices';
        const response = await fetch(url);
        if (!response.ok) throw new Error("Failed to load voices.");
        const result = await response.json();
        allVoices = result.voices;
        totalVoices = result.total;
        sortAndRender();
        updateLcdVoicesCount(totalVoices);
    } catch (e) {
        showToast(e.message, 'error');
    } finally {
        showLoading(false);
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
                    showToast(`Scan complete! Cataloged ${state.voices_found} voices.`, 'success');
                }
                loadVoices();
            }
        } catch (e) {
            console.error("Error polling scan status:", e);
        }
    }, 500);
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

async function showFilesModal(voiceName) {
    // Show modal immediately with loading state
    modalVoiceName.textContent = voiceName;
    modalList.innerHTML = '';
    modalLoading.classList.remove('hidden');
    filesModalOverlay.classList.remove('hidden');
    document.body.style.overflow = 'hidden';

    try {
        const response = await fetch(`/api/voices/files?name=${encodeURIComponent(voiceName)}`);
        if (!response.ok) throw new Error("Failed to fetch file list.");
        const files = await response.json();

        modalLoading.classList.add('hidden');
        renderModalList(files);
    } catch (e) {
        modalLoading.classList.add('hidden');
        modalList.innerHTML = `<div class="modal-error"><i class="fa-solid fa-triangle-exclamation"></i> ${e.message}</div>`;
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
        item.innerHTML = `
            <div class="modal-file-index">${String(idx + 1).padStart(2, '0')}</div>
            <div class="modal-file-info">
                <div class="modal-file-name">
                    <i class="fa-solid fa-file-audio"></i>
                    <span>${f.file_name}</span>
                    <span class="modal-pos-pill">${f.position}</span>
                </div>
                <div class="modal-file-path" title="${f.folder_path}">${f.folder_path}</div>
            </div>
            <button class="btn-reveal modal-reveal-btn" title="Reveal in Explorer" data-path="${f.file_path}">
                <i class="fa-regular fa-folder-open"></i>
            </button>
        `;
        item.querySelector('.modal-reveal-btn').addEventListener('click', () => {
            revealInExplorer(f.file_path);
        });
        modalList.appendChild(item);
    });
}

function closeFilesModal() {
    filesModalOverlay.classList.add('hidden');
    document.body.style.overflow = '';
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
    }, 300);
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
        } else {
            icon.className = 'fa-solid fa-sort';
            th.classList.remove('active-sort');
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
            resultCounter.innerHTML = `Showing <strong>${allVoices.length.toLocaleString()}</strong> of <strong>${totalVoices.toLocaleString()}</strong> unique voices &mdash; refine your search to see more`;
        } else {
            resultCounter.innerHTML = `<strong>${totalVoices.toLocaleString()}</strong> unique voice${totalVoices !== 1 ? 's' : ''} found`;
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
        
        // Voice Name Column
        const tdName = document.createElement('td');
        tdName.className = 'td-name';
        tdName.textContent = voice.voice_name;
        
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
            // Clickable badge for duplicates
            const badge = document.createElement('button');
            badge.className = 'file-count-badge file-count-dup';
            badge.title = `${fileCount} files contain this voice — click to view all`;
            badge.innerHTML = `<i class="fa-solid fa-layer-group"></i> ${fileCount}`;
            badge.addEventListener('click', () => showFilesModal(voice.voice_name));
            tdFiles.appendChild(badge);
        } else {
            // Single file — non-interactive pill
            const badge = document.createElement('span');
            badge.className = 'file-count-badge file-count-single';
            badge.title = '1 file contains this voice';
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
    lcdTotalVoices.textContent = String(count).padStart(6, '0');
}

function updateLcd(state) {
    // 1. Status
    if (state.status === 'scanning') {
        lcdStatus.textContent = "SCANNING";
        lcdStatus.className = "lcd-value status-scanning";
    } else {
        lcdStatus.textContent = "READY";
        lcdStatus.className = "lcd-value status-idle";
    }
    
    // 2. Voices Count
    updateLcdVoicesCount(state.voices_found);
    
    // 3. Active File
    if (state.status === 'scanning' && state.current_file) {
        lcdActiveFile.textContent = state.current_file;
    } else {
        lcdActiveFile.textContent = "NONE";
    }
    
    // 4. Progress Text
    if (state.status === 'scanning' && state.total_files > 0) {
        const pct = Math.round((state.files_scanned / state.total_files) * 100);
        const barLen = 6;
        const filledLen = Math.round((state.files_scanned / state.total_files) * barLen);
        const barStr = "#".repeat(filledLen) + "-".repeat(barLen - filledLen);
        lcdProgress.textContent = `${pct}% [${barStr}]`;
    } else {
        lcdProgress.textContent = "0% [------]";
    }
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
                           value="${folder.folder_path}" ${idx === 0 ? 'checked' : ''}>
                    <span class="dup-radio-indicator"><i class="fa-solid fa-check"></i></span>
                    <span class="dup-keep-label">${idx === 0 ? 'KEEP' : 'DEL'}</span>
                </label>
                <div class="dup-folder-info">
                    <span class="dup-folder-path" title="${folder.folder_path}">${folder.folder_path}</span>
                    <span class="dup-folder-meta">${folder.file_count} file${folder.file_count !== 1 ? 's' : ''}</span>
                </div>
                <button class="btn-reveal dup-reveal-btn" title="Reveal in Explorer">
                    <i class="fa-regular fa-folder-open"></i>
                </button>
            `;

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
        toast.style.borderColor = 'hsl(150, 100%, 40%)';
        toastIcon.style.color = 'hsl(150, 100%, 45%)';
    } else if (type === 'error') {
        toastIcon.className = 'fa-solid fa-circle-exclamation';
        toast.style.borderColor = 'var(--accent-red)';
        toastIcon.style.color = 'var(--accent-red)';
    } else {
        toastIcon.className = 'fa-solid fa-circle-info';
        toast.style.borderColor = 'var(--accent-teal)';
        toastIcon.style.color = 'var(--accent-teal)';
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
    }, 4000);
}
