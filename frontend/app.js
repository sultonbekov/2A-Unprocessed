/**
 * Viloyat Archiver - Frontend Application
 * Professional ZIP Archive Tool
 */

const API_BASE = 'http://localhost:5000/api';

// State
let currentBrowserTarget = null;
let currentPath = '';
let parentPath = null;
let selectedFolder = null;
let selectedFormat = '7z';
let availableFormats = [];

// DOM Elements
const inputPath = document.getElementById('inputPath');
const outputPath = document.getElementById('outputPath');
const archiveBtn = document.getElementById('archiveBtn');
const inputValidation = document.getElementById('inputValidation');
const resultSection = document.getElementById('resultSection');
const browserModal = document.getElementById('browserModal');
const folderList = document.getElementById('folderList');
const currentPathInput = document.getElementById('currentPath');
const backBtn = document.getElementById('backBtn');

// Initialize
document.addEventListener('DOMContentLoaded', async () => {
    updateArchiveButton();
    await loadFormats();
});

// Load available formats
async function loadFormats() {
    try {
        const res = await fetch(`${API_BASE}/formats`);
        const data = await res.json();
        availableFormats = data.formats || [];
        // Default to first available format
        const firstAvailable = availableFormats.find(f => f.available);
        if (firstAvailable) selectedFormat = firstAvailable.id;
        renderFormatSelector();
    } catch (err) {
        console.error('Failed to load formats:', err);
    }
}

function renderFormatSelector() {
    const grid = document.getElementById('formatGrid');
    if (!grid) return;
    grid.innerHTML = '';
    availableFormats.forEach(f => {
        const btn = document.createElement('button');
        btn.className = 'option-btn' + (f.id === selectedFormat ? ' selected' : '') + (f.available ? '' : ' disabled');
        btn.disabled = !f.available;
        btn.innerHTML = `
            <span class="option-name">${f.ext.toUpperCase()}</span>
            <span class="option-desc">${f.name}</span>
            ${!f.available ? '<span class="option-badge">недоступно</span>' : ''}
        `;
        btn.addEventListener('click', () => {
            if (!f.available) return;
            selectedFormat = f.id;
            renderFormatSelector();
        });
        grid.appendChild(btn);
    });
}

// Open file browser
async function openBrowser(target) {
    currentBrowserTarget = target;
    selectedFolder = null;
    browserModal.classList.add('show');
    // For input path, show only Unprocessed folders
    const showOnlyUnprocessed = target === 'input';
    await browsePath('', showOnlyUnprocessed);
}

// Close file browser
function closeBrowser() {
    browserModal.classList.remove('show');
    currentBrowserTarget = null;
    selectedFolder = null;
}

// Browse directory
async function browsePath(path, showOnlyUnprocessed = false) {
    try {
        const response = await fetch(`${API_BASE}/browse`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path, show_only_unprocessed: showOnlyUnprocessed })
        });
        
        const data = await response.json();
        
        if (data.error) {
            showNotification(data.error, 'error');
            return;
        }
        
        currentPath = data.current_path;
        parentPath = data.parent_path;
        currentPathInput.value = currentPath || 'Мой компьютер';
        backBtn.disabled = !parentPath && !currentPath;
        
        renderFolderList(data.items);
    } catch (error) {
        showNotification('Ошибка просмотра папки', 'error');
    }
}

// Render folder list
function renderFolderList(items) {
    folderList.innerHTML = '';
    
    const folders = items.filter(item => item.type === 'folder' || item.type === 'drive' || item.type === 'network');
    
    if (folders.length === 0) {
        folderList.innerHTML = `
            <div style="text-align: center; padding: 40px; color: var(--text-muted);">
                <p>Папки не найдены</p>
            </div>
        `;
        return;
    }
    
    folders.forEach(item => {
        const button = document.createElement('button');
        button.className = `folder-item ${item.type === 'drive' ? 'drive' : item.type === 'network' ? 'network' : ''}`;
        button.innerHTML = `
            ${item.type === 'drive' ? `
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <rect x="2" y="4" width="20" height="16" rx="2"/>
                    <path d="M6 8h.01M6 12h.01M6 16h.01"/>
                </svg>
            ` : item.type === 'network' ? `
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M16 17l-4 4-4-4M4 7l4-4 4 4M12 3v18"/>
                </svg>
            ` : `
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
                </svg>
            `}
            <span>${item.name}</span>
        `;
        
        button.addEventListener('click', () => {
            // Remove selection from others
            document.querySelectorAll('.folder-item.selected').forEach(el => {
                el.classList.remove('selected');
            });
            button.classList.add('selected');
            selectedFolder = item.path || item.name;
        });
        
        button.addEventListener('dblclick', () => {
            const showOnlyUnprocessed = currentBrowserTarget === 'input';
            browsePath(item.path || item.name, showOnlyUnprocessed);
        });
        
        folderList.appendChild(button);
    });
}

// Go back
function goBack() {
    const showOnlyUnprocessed = currentBrowserTarget === 'input';
    if (parentPath) {
        browsePath(parentPath, showOnlyUnprocessed);
    } else if (currentPath) {
        browsePath('', showOnlyUnprocessed);
    }
}

// Select folder
function selectFolder() {
    const pathToUse = selectedFolder || currentPath;
    
    if (!pathToUse) {
        showNotification('Выберите папку', 'error');
        return;
    }
    
    if (currentBrowserTarget === 'input') {
        inputPath.value = pathToUse;
        validateInputPath(pathToUse);
        updateStep(2);
    } else if (currentBrowserTarget === 'output') {
        outputPath.value = pathToUse;
        updateStep(2);
    }
    
    updateArchiveButton();
    closeBrowser();
}

// Validate input path
async function validateInputPath(path) {
    try {
        const response = await fetch(`${API_BASE}/validate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ input_path: path })
        });
        
        const data = await response.json();
        
        if (data.valid) {
            inputValidation.className = 'validation-status valid';
            inputValidation.innerHTML = `
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
                    <polyline points="22 4 12 14.01 9 11.01"/>
                </svg>
                <span>Найдено: ${data.viloyat_count} вилоят (${data.total_files} файлов)</span>
            `;
        } else {
            inputValidation.className = 'validation-status invalid';
            inputValidation.innerHTML = `
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <circle cx="12" cy="12" r="10"/>
                    <line x1="15" y1="9" x2="9" y2="15"/>
                    <line x1="9" y1="9" x2="15" y2="15"/>
                </svg>
                <span>${data.error}</span>
            `;
        }
    } catch (error) {
        inputValidation.className = 'validation-status invalid';
        inputValidation.innerHTML = `
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="10"/>
                <line x1="15" y1="9" x2="9" y2="15"/>
                <line x1="9" y1="9" x2="15" y2="15"/>
            </svg>
            <span>Не удалось подключиться к серверу</span>
        `;
    }
}

// Update archive button state
function updateArchiveButton() {
    archiveBtn.disabled = !inputPath.value || !outputPath.value;
}

// Update step indicator
function updateStep(stepNum) {
    document.querySelectorAll('.step').forEach((step, index) => {
        const num = index + 1;
        step.classList.remove('active', 'completed');
        
        if (num < stepNum) {
            step.classList.add('completed');
        } else if (num === stepNum) {
            step.classList.add('active');
        }
    });
    
    document.querySelectorAll('.step-line').forEach((line, index) => {
        line.classList.toggle('active', index < stepNum - 1);
    });
}

// Format seconds to H:M:S
function formatDuration(seconds) {
    if (seconds <= 0 || !isFinite(seconds)) return '—';
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = Math.floor(seconds % 60);
    if (h > 0) return `${h}ч ${m}м ${s}с`;
    if (m > 0) return `${m}м ${s}с`;
    return `${s}с`;
}

function formatBytes(bytes) {
    if (!bytes) return '0 B';
    const units = ['B', 'KB', 'MB', 'GB', 'TB', 'PB'];
    let i = 0;
    let size = bytes;
    while (size >= 1024 && i < units.length - 1) {
        size /= 1024;
        i++;
    }
    return `${size.toFixed(2)} ${units[i]}`;
}

// Show/update progress UI
function renderProgress(data) {
    const section = document.getElementById('progressSection');
    if (!section) return;
    section.classList.add('show');
    
    const percent = Math.min(100, data.percent || 0);
    document.getElementById('progressBar').style.width = `${percent}%`;
    document.getElementById('progressPercent').textContent = `${percent.toFixed(1)}%`;
    
    const statusText = {
        'queued': 'В очереди...',
        'calculating': 'Подсчёт размера...',
        'archiving': 'Архивирование...',
        'completed': 'Завершено',
        'error': 'Ошибка'
    }[data.status] || data.status || '';
    document.getElementById('progressStatus').textContent = statusText;
    
    document.getElementById('progressBytes').textContent =
        `${formatBytes(data.processed_bytes || 0)} / ${formatBytes(data.total_bytes || 0)}`;
    document.getElementById('progressSpeed').textContent = data.current_speed || '—';
    document.getElementById('progressEta').textContent =
        data.eta_seconds !== undefined ? formatDuration(data.eta_seconds) : '—';
    document.getElementById('progressElapsed').textContent =
        data.elapsed !== undefined ? formatDuration(data.elapsed) : '—';
    document.getElementById('progressViloyats').textContent =
        `${data.completed_viloyats || 0} / ${data.total_viloyats || 0}`;
}

// Create archive (background job with progress polling)
async function createArchive() {
    if (!inputPath.value || !outputPath.value) return;
    
    archiveBtn.classList.add('loading');
    archiveBtn.disabled = true;
    resultSection.classList.remove('show');
    
    try {
        const response = await fetch(`${API_BASE}/archive`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                input_path: inputPath.value,
                output_path: outputPath.value,
                format: selectedFormat
            })
        });
        
        const data = await response.json();
        
        if (!data.success || !data.job_id) {
            showNotification(data.error || 'Ошибка создания архива', 'error');
            archiveBtn.classList.remove('loading');
            archiveBtn.disabled = false;
            return;
        }
        
        // Poll progress every 500ms
        const jobId = data.job_id;
        const pollInterval = setInterval(async () => {
            try {
                const res = await fetch(`${API_BASE}/progress/${jobId}`);
                const progress = await res.json();
                renderProgress(progress);
                
                if (progress.status === 'completed') {
                    clearInterval(pollInterval);
                    document.getElementById('resultViloyat').textContent = progress.viloyat_count;
                    document.getElementById('resultPath').textContent = progress.output_path;
                    resultSection.classList.add('show');
                    
                    document.querySelectorAll('.step').forEach(s => {
                        s.classList.remove('active');
                        s.classList.add('completed');
                    });
                    document.querySelectorAll('.step-line').forEach(l => l.classList.add('active'));
                    
                    showNotification(`Готово за ${progress.elapsed_seconds}с (${progress.speed})`, 'success');
                    archiveBtn.classList.remove('loading');
                    archiveBtn.disabled = false;
                } else if (progress.status === 'error') {
                    clearInterval(pollInterval);
                    showNotification(progress.error || 'Ошибка архивирования', 'error');
                    archiveBtn.classList.remove('loading');
                    archiveBtn.disabled = false;
                }
            } catch (err) {
                console.error('Poll error:', err);
            }
        }, 500);
    } catch (error) {
        showNotification('Не удалось подключиться к серверу', 'error');
        archiveBtn.classList.remove('loading');
        archiveBtn.disabled = false;
    }
}

// Show notification
function showNotification(message, type = 'info') {
    // Create notification element
    const notification = document.createElement('div');
    notification.style.cssText = `
        position: fixed;
        bottom: 24px;
        right: 24px;
        padding: 16px 24px;
        background: ${type === 'success' ? '#10b981' : type === 'error' ? '#ef4444' : '#6366f1'};
        color: white;
        border-radius: 12px;
        font-size: 14px;
        font-weight: 500;
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.3);
        z-index: 2000;
        animation: slideInRight 0.3s ease;
    `;
    notification.textContent = message;
    
    // Add animation keyframes
    if (!document.getElementById('notification-styles')) {
        const style = document.createElement('style');
        style.id = 'notification-styles';
        style.textContent = `
            @keyframes slideInRight {
                from { transform: translateX(100%); opacity: 0; }
                to { transform: translateX(0); opacity: 1; }
            }
            @keyframes slideOutRight {
                from { transform: translateX(0); opacity: 1; }
                to { transform: translateX(100%); opacity: 0; }
            }
        `;
        document.head.appendChild(style);
    }
    
    document.body.appendChild(notification);
    
    // Remove after 3 seconds
    setTimeout(() => {
        notification.style.animation = 'slideOutRight 0.3s ease';
        setTimeout(() => notification.remove(), 300);
    }, 3000);
}

// Keyboard shortcuts
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && browserModal.classList.contains('show')) {
        closeBrowser();
    }
});
