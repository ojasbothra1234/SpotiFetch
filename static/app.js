let activeTaskId = null;
let pollInterval = null;
let currentPreviewSongs = [];

// Auth DOM Elements
const authOverlay = document.getElementById('authOverlay');
const authForm = document.getElementById('authForm');
const authPasswordInput = document.getElementById('authPasswordInput');
const toggleAuthPasswordBtn = document.getElementById('toggleAuthPasswordBtn');
const eyeIcon = document.getElementById('eyeIcon');
const authErrorBox = document.getElementById('authErrorBox');
const authErrorMessage = document.getElementById('authErrorMessage');
const authSubmitBtn = document.getElementById('authSubmitBtn');
const logoutBtn = document.getElementById('logoutBtn');

// DOM Elements
const spotifyUrlInput = document.getElementById('spotifyUrlInput');
const pasteBtn = document.getElementById('pasteBtn');
const startDownloadBtn = document.getElementById('startDownloadBtn');
const previewTracksBtn = document.getElementById('previewTracksBtn');
const formatSelect = document.getElementById('formatSelect');
const downloadBtnFormatText = document.getElementById('downloadBtnFormatText');

const typeIndicator = document.getElementById('typeIndicator');
const typeIndicatorPlaceholder = document.getElementById('typeIndicatorPlaceholder');
const detectedTypeText = document.getElementById('detectedTypeText');

// Track Selection Section
const trackSelectionSection = document.getElementById('trackSelectionSection');
const previewTypeBadge = document.getElementById('previewTypeBadge');
const trackSelectionSubtitle = document.getElementById('trackSelectionSubtitle');
const selectAllBtn = document.getElementById('selectAllBtn');
const deselectAllBtn = document.getElementById('deselectAllBtn');
const trackSearchInput = document.getElementById('trackSearchInput');
const selectionCounterText = document.getElementById('selectionCounterText');
const trackListContainer = document.getElementById('trackListContainer');
const closeTrackSelectionBtn = document.getElementById('closeTrackSelectionBtn');
const downloadSelectedBtn = document.getElementById('downloadSelectedBtn');
const downloadSelectedBtnText = document.getElementById('downloadSelectedBtnText');

// Progress & Status Elements
const taskSection = document.getElementById('taskSection');
const taskStatusTitle = document.getElementById('taskStatusTitle');
const taskStatusSubtitle = document.getElementById('taskStatusSubtitle');
const taskTypeBadge = document.getElementById('taskTypeBadge');
const statusIcon = document.getElementById('statusIcon');
const statusIconContainer = document.getElementById('statusIconContainer');
const progressBar = document.getElementById('progressBar');

const toggleLogsBtn = document.getElementById('toggleLogsBtn');
const logChevron = document.getElementById('logChevron');
const logContainer = document.getElementById('logContainer');

const readyBox = document.getElementById('readyBox');
const readyFileName = document.getElementById('readyFileName');
const readyFileSize = document.getElementById('readyFileSize');
const readyItemCount = document.getElementById('readyItemCount');
const finalDownloadLink = document.getElementById('finalDownloadLink');

const errorBox = document.getElementById('errorBox');
const errorMessage = document.getElementById('errorMessage');
const historyList = document.getElementById('historyList');

// Format file size
function formatBytes(bytes, decimals = 2) {
    if (!+bytes) return '0 Bytes';
    const k = 1024;
    const dm = decimals < 0 ? 0 : decimals;
    const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${parseFloat((bytes / Math.pow(k, i)).toFixed(dm))} ${sizes[i]}`;
}

// --- Authentication Handling ---
async function checkAuthStatus() {
    try {
        const res = await fetch('/api/auth/status');
        if (!res.ok) return;
        const data = await res.json();

        if (data.auth_required && !data.authenticated) {
            showLockScreen();
        } else {
            hideLockScreen();
            if (data.auth_required) {
                logoutBtn.classList.remove('hidden');
            }
            fetchRecentTasks();
        }
    } catch (err) {
        console.error('Failed to check auth status', err);
    }
}

function showLockScreen() {
    authOverlay.classList.remove('hidden');
    logoutBtn.classList.add('hidden');
    authPasswordInput.value = '';
    authErrorBox.classList.add('hidden');
    setTimeout(() => authPasswordInput.focus(), 100);
}

function hideLockScreen() {
    authOverlay.classList.add('hidden');
    logoutBtn.classList.remove('hidden');
}

// Show/Hide password toggle
toggleAuthPasswordBtn.addEventListener('click', () => {
    const isPassword = authPasswordInput.type === 'password';
    authPasswordInput.type = isPassword ? 'text' : 'password';
    eyeIcon.setAttribute('data-lucide', isPassword ? 'eye-off' : 'eye');
    lucide.createIcons();
});

// Submit login form
authForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const password = authPasswordInput.value.trim();
    if (!password) return;

    authSubmitBtn.disabled = true;
    const originalText = authSubmitBtn.innerHTML;
    authSubmitBtn.innerHTML = `
        <i data-lucide="loader" class="w-4 h-4 animate-spin"></i>
        <span>Verifying...</span>
    `;
    lucide.createIcons();
    authErrorBox.classList.add('hidden');

    try {
        const res = await fetch('/api/auth/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ password: password })
        });

        const data = await res.json();
        if (!res.ok) {
            throw new Error(data.detail || 'Incorrect password.');
        }

        hideLockScreen();
        fetchRecentTasks();

    } catch (err) {
        authErrorBox.classList.remove('hidden');
        authErrorMessage.textContent = err.message || 'Incorrect password.';
        authPasswordInput.select();
    } finally {
        authSubmitBtn.disabled = false;
        authSubmitBtn.innerHTML = originalText;
        lucide.createIcons();
    }
});

// Logout / Lock session
logoutBtn.addEventListener('click', async () => {
    try {
        await fetch('/api/auth/logout', { method: 'POST' });
    } catch (e) {
        console.error('Logout error', e);
    }
    showLockScreen();
});

// Update format button labels when format changes
formatSelect.addEventListener('change', () => {
    const fmt = formatSelect.value.toUpperCase();
    downloadBtnFormatText.textContent = fmt;
    updateSelectedDownloadBtnText();
});

// URL detection (debounced)
let urlDebounceTimer = null;
spotifyUrlInput.addEventListener('input', (e) => {
    clearTimeout(urlDebounceTimer);
    urlDebounceTimer = setTimeout(() => {
        const val = e.target.value.toLowerCase().trim();
        if (!val) {
            typeIndicator.classList.add('hidden');
            if (typeIndicatorPlaceholder) typeIndicatorPlaceholder.classList.remove('hidden');
            return;
        }

        if (typeIndicatorPlaceholder) typeIndicatorPlaceholder.classList.add('hidden');
        typeIndicator.classList.remove('hidden');

        if (val.includes('track')) {
            detectedTypeText.textContent = 'Single Track';
        } else if (val.includes('album')) {
            detectedTypeText.textContent = 'Full Album (ZIP Package)';
        } else if (val.includes('playlist')) {
            detectedTypeText.textContent = 'Playlist (ZIP Package)';
        } else if (val.includes('artist')) {
            detectedTypeText.textContent = 'Artist Discography (All Songs in ZIP)';
        } else if (val.includes('episode') || val.includes('show')) {
            detectedTypeText.textContent = 'Podcast / Episode (Audio)';
        } else {
            detectedTypeText.textContent = 'Spotify Link';
        }
    }, 250);
});

// Paste button
pasteBtn.addEventListener('click', async () => {
    try {
        const text = await navigator.clipboard.readText();
        if (text) {
            spotifyUrlInput.value = text;
            spotifyUrlInput.dispatchEvent(new Event('input'));
        }
    } catch (err) {
        console.error('Failed to read clipboard', err);
    }
});

// Toggle Terminal Logs
toggleLogsBtn.addEventListener('click', () => {
    const isHidden = logContainer.classList.contains('hidden');
    if (isHidden) {
        logContainer.classList.remove('hidden');
        logChevron.setAttribute('data-lucide', 'chevron-up');
    } else {
        logContainer.classList.add('hidden');
        logChevron.setAttribute('data-lucide', 'chevron-down');
    }
    lucide.createIcons();
});

// --- Track Preview & Song Selection ---
previewTracksBtn.addEventListener('click', async () => {
    const url = spotifyUrlInput.value.trim();
    if (!url) {
        alert('Please enter a Spotify URL first.');
        return;
    }

    // Set preview loading state
    previewTracksBtn.disabled = true;
    const originalBtnHTML = previewTracksBtn.innerHTML;
    previewTracksBtn.innerHTML = `
        <i data-lucide="loader" class="w-4 h-4 animate-spin text-spotify-green"></i>
        <span>Fetching Tracks...</span>
    `;
    lucide.createIcons();

    trackSelectionSection.classList.remove('hidden');
    trackListContainer.innerHTML = `
        <div class="p-8 text-center text-neutral-400 space-y-3">
            <i data-lucide="loader" class="w-6 h-6 animate-spin text-spotify-green mx-auto"></i>
            <p class="text-xs">Connecting to Spotify & resolving song list...</p>
        </div>
    `;
    lucide.createIcons();

    try {
        const response = await fetch('/api/preview', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url: url })
        });

        if (response.status === 401) {
            showLockScreen();
            throw new Error('Please unlock with password first.');
        }

        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.detail || 'Failed to fetch tracks preview.');
        }

        currentPreviewSongs = data.songs || [];
        previewTypeBadge.textContent = data.item_type || 'MEDIA';
        trackSelectionSubtitle.textContent = `Found ${currentPreviewSongs.length} song(s). Check the tracks you want to download.`;

        renderTrackList(currentPreviewSongs);

    } catch (err) {
        trackListContainer.innerHTML = `
            <div class="p-6 text-center text-red-400 text-xs">
                <i data-lucide="alert-circle" class="w-5 h-5 mx-auto mb-1 text-red-400"></i>
                <p>${escapeHtml(err.message || 'Could not load tracks')}</p>
            </div>
        `;
        lucide.createIcons();
    } finally {
        previewTracksBtn.disabled = false;
        previewTracksBtn.innerHTML = originalBtnHTML;
        lucide.createIcons();
    }
});

function renderTrackList(songs) {
    if (!songs || songs.length === 0) {
        trackListContainer.innerHTML = '<div class="p-6 text-center text-neutral-500 text-xs">No tracks found for this link.</div>';
        updateSelectionCounter();
        return;
    }

    trackListContainer.innerHTML = songs.map((song) => {
        const coverImg = song.cover_url ? 
            `<img src="${escapeHtml(song.cover_url)}" alt="cover" class="w-9 h-9 rounded object-cover shrink-0 bg-neutral-800" loading="lazy" />` :
            `<div class="w-9 h-9 rounded bg-white/5 flex items-center justify-center text-neutral-500 shrink-0"><i data-lucide="music" class="w-4 h-4"></i></div>`;

        return `
            <label class="track-row flex items-center justify-between gap-3 p-2.5 rounded-xl bg-spotify-dark/70 hover:bg-white/5 border border-white/5 cursor-pointer transition-colors text-xs" data-title="${escapeHtml(song.name.toLowerCase())}" data-artist="${escapeHtml(song.artist.toLowerCase())}">
                <div class="flex items-center gap-3 min-w-0 flex-1">
                    <input type="checkbox" value="${escapeHtml(song.url)}" class="track-checkbox w-4 h-4 rounded text-spotify-green accent-spotify-green cursor-pointer shrink-0" checked>
                    <span class="text-neutral-500 font-mono text-[11px] w-5 text-right shrink-0">${song.index}</span>
                    ${coverImg}
                    <div class="min-w-0 flex-1">
                        <div class="font-medium text-white truncate text-xs">${escapeHtml(song.name)}</div>
                        <div class="text-[11px] text-neutral-400 truncate">${escapeHtml(song.artist)}</div>
                    </div>
                </div>
                <div class="text-neutral-400 font-mono text-[11px] shrink-0 pr-1">
                    ${escapeHtml(song.duration || '')}
                </div>
            </label>
        `;
    }).join('');

    lucide.createIcons();

    // Attach checkbox event listeners
    const checkboxes = trackListContainer.querySelectorAll('.track-checkbox');
    checkboxes.forEach(cb => {
        cb.addEventListener('change', updateSelectionCounter);
    });

    updateSelectionCounter();
}

// Search / Filter inside tracklist
trackSearchInput.addEventListener('input', (e) => {
    const q = e.target.value.toLowerCase().trim();
    const rows = trackListContainer.querySelectorAll('.track-row');
    rows.forEach(row => {
        const title = row.getAttribute('data-title') || '';
        const artist = row.getAttribute('data-artist') || '';
        if (!q || title.includes(q) || artist.includes(q)) {
            row.classList.remove('hidden');
        } else {
            row.classList.add('hidden');
        }
    });
});

// Select All / Deselect All
selectAllBtn.addEventListener('click', () => {
    const checkboxes = trackListContainer.querySelectorAll('.track-checkbox');
    checkboxes.forEach(cb => cb.checked = true);
    updateSelectionCounter();
});

deselectAllBtn.addEventListener('click', () => {
    const checkboxes = trackListContainer.querySelectorAll('.track-checkbox');
    checkboxes.forEach(cb => cb.checked = false);
    updateSelectionCounter();
});

function updateSelectionCounter() {
    const checkboxes = trackListContainer.querySelectorAll('.track-checkbox');
    const checked = trackListContainer.querySelectorAll('.track-checkbox:checked');
    const total = checkboxes.length;
    const count = checked.length;

    selectionCounterText.textContent = `${count} of ${total} selected`;
    downloadSelectedBtn.disabled = count === 0;

    updateSelectedDownloadBtnText(count);
}

function updateSelectedDownloadBtnText(count = null) {
    if (count === null) {
        count = trackListContainer.querySelectorAll('.track-checkbox:checked').length;
    }
    const fmt = formatSelect.value.toUpperCase();
    downloadSelectedBtnText.textContent = `Download ${count} Selected Song${count === 1 ? '' : 's'} (${fmt})`;
}

closeTrackSelectionBtn.addEventListener('click', () => {
    trackSelectionSection.classList.add('hidden');
});

// Download Selected Tracks
downloadSelectedBtn.addEventListener('click', () => {
    const checked = Array.from(trackListContainer.querySelectorAll('.track-checkbox:checked')).map(cb => cb.value);
    if (checked.length === 0) {
        alert('Please select at least one song to download.');
        return;
    }

    const url = spotifyUrlInput.value.trim();
    const format = formatSelect.value;

    trackSelectionSection.classList.add('hidden');
    initiateDownload(url, format, checked);
});

// Download All Button
startDownloadBtn.addEventListener('click', () => {
    const url = spotifyUrlInput.value.trim();
    if (!url) {
        alert('Please enter a Spotify URL.');
        return;
    }
    const format = formatSelect.value;
    trackSelectionSection.classList.add('hidden');
    initiateDownload(url, format, null);
});

// --- Core Download Function ---
async function initiateDownload(url, format = 'mp3', selectedUrls = null) {
    // Reset UI
    startDownloadBtn.disabled = true;
    previewTracksBtn.disabled = true;
    taskSection.classList.remove('hidden');
    readyBox.classList.add('hidden');
    errorBox.classList.add('hidden');
    logContainer.innerHTML = '<div class="text-neutral-500">Initiating request...</div>';
    
    taskStatusTitle.textContent = 'Submitting task...';
    taskStatusSubtitle.textContent = 'Connecting to backend...';
    statusIcon.className = 'w-4 h-4 animate-spin';
    statusIcon.setAttribute('data-lucide', 'loader');
    lucide.createIcons();

    try {
        const payload = {
            url: url,
            format: format,
            selected_urls: selectedUrls && selectedUrls.length > 0 ? selectedUrls : null
        };

        const response = await fetch('/api/download', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(payload)
        });

        if (response.status === 401) {
            showLockScreen();
            throw new Error('Please unlock with password first.');
        }

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || 'Failed to start download task.');
        }

        activeTaskId = data.task_id;
        taskTypeBadge.textContent = `${data.item_type} (${(data.audio_format || format).toUpperCase()})`;
        
        if (data.selected_count) {
            taskStatusTitle.textContent = `Downloading ${data.selected_count} Selected Song(s)...`;
        } else {
            taskStatusTitle.textContent = `Downloading ${data.item_type}...`;
        }
        
        // Start polling
        if (pollInterval) clearInterval(pollInterval);
        pollInterval = setInterval(pollTaskStatus, 1500);

    } catch (err) {
        startDownloadBtn.disabled = false;
        previewTracksBtn.disabled = false;
        errorBox.classList.remove('hidden');
        errorMessage.textContent = err.message || 'An error occurred while submitting.';
        taskStatusTitle.textContent = 'Error';
        taskStatusSubtitle.textContent = 'Submission failed';
    }
}

async function pollTaskStatus() {
    if (!activeTaskId) return;

    try {
        const res = await fetch(`/api/status/${activeTaskId}`);
        if (res.status === 401) {
            showLockScreen();
            return;
        }
        if (!res.ok) {
            throw new Error('Task not found');
        }

        const task = await res.json();

        // Update logs
        if (task.logs && task.logs.length > 0) {
            logContainer.innerHTML = task.logs.map(line => `<div>${escapeHtml(line)}</div>`).join('');
            logContainer.scrollTop = logContainer.scrollHeight;
        }

        taskStatusSubtitle.textContent = task.progress_msg || 'Processing...';

        if (task.status === 'downloading') {
            const fmtStr = (task.audio_format || 'MP3').toUpperCase();
            if (task.selected_count) {
                taskStatusTitle.textContent = `Fetching ${task.selected_count} Songs (${fmtStr})...`;
            } else {
                taskStatusTitle.textContent = `Fetching Audio (${task.item_type} • ${fmtStr})...`;
            }
        } else if (task.status === 'zipping') {
            taskStatusTitle.textContent = 'Packaging into Archive...';
        } else if (task.status === 'ready') {
            clearInterval(pollInterval);
            pollInterval = null;
            startDownloadBtn.disabled = false;
            previewTracksBtn.disabled = false;

            taskStatusTitle.textContent = 'Download Complete!';
            taskStatusSubtitle.textContent = task.progress_msg;
            progressBar.classList.remove('animate-pulse');
            progressBar.classList.add('bg-spotify-green');

            // Setup Ready Box
            readyBox.classList.remove('hidden');
            readyFileName.textContent = task.filename;
            readyFileSize.textContent = formatBytes(task.file_size);
            readyItemCount.textContent = task.item_count ? `${task.item_count} song(s)` : '1 item';
            finalDownloadLink.href = `/api/file/${task.task_id}`;
            finalDownloadLink.setAttribute('download', task.filename);

            // Automatically trigger download
            finalDownloadLink.click();

            fetchRecentTasks();
        } else if (task.status === 'failed') {
            clearInterval(pollInterval);
            pollInterval = null;
            startDownloadBtn.disabled = false;
            previewTracksBtn.disabled = false;

            taskStatusTitle.textContent = 'Download Failed';
            errorBox.classList.remove('hidden');
            errorMessage.textContent = task.error || 'Unknown error occurred during processing.';
            fetchRecentTasks();
        }

    } catch (err) {
        console.error('Polling error:', err);
    }
}

async function fetchRecentTasks() {
    try {
        const res = await fetch('/api/tasks');
        if (res.status === 401) {
            showLockScreen();
            return;
        }
        if (!res.ok) return;
        const tasksList = await res.json();
        
        if (tasksList.length === 0) {
            historyList.innerHTML = '<div class="text-xs text-neutral-500 italic">No previous downloads in this session.</div>';
            return;
        }

        historyList.innerHTML = tasksList.map(t => {
            const isReady = t.status === 'ready';
            const statusClass = isReady ? 'text-spotify-green' : (t.status === 'failed' ? 'text-red-400' : 'text-yellow-400');
            const fmtBadge = t.audio_format ? t.audio_format.toUpperCase() : 'MP3';

            return `
                <div class="glass-card rounded-xl p-3 border border-white/5 flex items-center justify-between gap-3 text-xs">
                    <div class="truncate flex-1">
                        <div class="font-medium text-white truncate">${escapeHtml(t.filename || t.url)}</div>
                        <div class="text-neutral-400 text-[11px] flex items-center gap-2">
                            <span class="${statusClass} font-semibold capitalize">${t.status}</span>
                            <span>•</span>
                            <span>${t.item_type} (${fmtBadge})</span>
                            ${t.file_size ? `<span>•</span><span>${formatBytes(t.file_size)}</span>` : ''}
                        </div>
                    </div>
                    ${isReady ? `
                        <a href="/api/file/${t.task_id}" download="${escapeHtml(t.filename)}" class="px-3 py-1.5 rounded-lg bg-white/10 hover:bg-spotify-green hover:text-black font-semibold text-white transition-colors shrink-0">
                            Download
                        </a>
                    ` : ''}
                </div>
            `;
        }).join('');

    } catch (e) {
        console.error('Failed to load history', e);
    }
}

function escapeHtml(text) {
    if (!text) return '';
    return String(text)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

// Initial check on load
checkAuthStatus();
