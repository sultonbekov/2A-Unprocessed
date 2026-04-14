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
document.addEventListener('DOMContentLoaded', () => {
    updateArchiveButton();
});

// Open file browser
async function openBrowser(target) {
    currentBrowserTarget = target;
    selectedFolder = null;
    browserModal.classList.add('show');
    await browsePath('');
}

// Close file browser
function closeBrowser() {
    browserModal.classList.remove('show');
    currentBrowserTarget = null;
    selectedFolder = null;
}

// Browse directory
async function browsePath(path) {
    try {
        const response = await fetch(`${API_BASE}/browse`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path })
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
    
    const folders = items.filter(item => item.type === 'folder' || item.type === 'drive');
    
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
        button.className = `folder-item ${item.type === 'drive' ? 'drive' : ''}`;
        button.innerHTML = `
            ${item.type === 'drive' ? `
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <rect x="2" y="4" width="20" height="16" rx="2"/>
                    <path d="M6 8h.01M6 12h.01M6 16h.01"/>
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
            browsePath(item.path || item.name);
        });
        
        folderList.appendChild(button);
    });
}

// Go back
function goBack() {
    if (parentPath) {
        browsePath(parentPath);
    } else if (currentPath) {
        browsePath('');
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

// Create archive
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
                output_path: outputPath.value
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            // Update result section
            document.getElementById('resultViloyat').textContent = data.viloyat_count;
            document.getElementById('resultPath').textContent = data.output_path;
            
            resultSection.classList.add('show');
            
            // Update steps
            document.querySelectorAll('.step').forEach(step => {
                step.classList.remove('active');
                step.classList.add('completed');
            });
            document.querySelectorAll('.step-line').forEach(line => {
                line.classList.add('active');
            });
            
            showNotification('Архив успешно создан!', 'success');
        } else {
            showNotification(data.error || 'Ошибка создания архива', 'error');
        }
    } catch (error) {
        showNotification('Не удалось подключиться к серверу', 'error');
    } finally {
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
