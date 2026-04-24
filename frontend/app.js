/**
 * KOSMIK Arxivlash - Frontend logikasi
 *
 * Foydalanuvchi kirish va chiqish yo'llarini yozadi, tugma bosadi.
 * Server arxivlashni boshlaydi, biz progressni har 500ms da so'raymiz.
 */

const API = 'http://localhost:5000/api';

// DOM elementlari
const inputPath = document.getElementById('inputPath');
const outputPath = document.getElementById('outputPath');
const archiveBtn = document.getElementById('archiveBtn');
const inputValidation = document.getElementById('inputValidation');
const resultSection = document.getElementById('resultSection');
const progressSection = document.getElementById('progressSection');

// =====================================================================
// Yordamchi funksiyalar
// =====================================================================

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

function formatDuration(seconds) {
    if (seconds <= 0 || !isFinite(seconds)) return '—';
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = Math.floor(seconds % 60);
    if (h > 0) return `${h}s ${m}d ${s}s`;
    if (m > 0) return `${m}d ${s}s`;
    return `${s}s`;
}

function showNotification(message, type = 'info') {
    const el = document.createElement('div');
    const colors = { success: '#10b981', error: '#ef4444', info: '#6366f1' };
    el.style.cssText = `
        position: fixed; bottom: 24px; right: 24px;
        padding: 16px 24px;
        background: ${colors[type] || colors.info};
        color: white; border-radius: 12px;
        font-size: 14px; font-weight: 500;
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.3);
        z-index: 2000;
    `;
    el.textContent = message;
    document.body.appendChild(el);
    setTimeout(() => el.remove(), 4000);
}

// =====================================================================
// Kirish yo'lini tekshirish
// =====================================================================

async function validateInput(path) {
    try {
        const res = await fetch(`${API}/validate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ input_path: path }),
        });
        const data = await res.json();

        if (data.valid) {
            inputValidation.className = 'validation-status valid';
            inputValidation.innerHTML =
                `<span>✓ Topildi: ${data.viloyat_count} viloyat</span>`;
        } else {
            inputValidation.className = 'validation-status invalid';
            inputValidation.innerHTML = `<span>✗ ${data.error}</span>`;
        }
    } catch {
        inputValidation.className = 'validation-status invalid';
        inputValidation.innerHTML = '<span>✗ Serverga ulanib bo\'lmadi</span>';
    }
}

function updateButton() {
    archiveBtn.disabled = !inputPath.value.trim() || !outputPath.value.trim();
}

// Kirish yo'li o'zgarganda avtomatik tekshiruv (500ms delay)
let validateTimer = null;
inputPath.addEventListener('input', () => {
    clearTimeout(validateTimer);
    const v = inputPath.value.trim();
    if (!v) {
        inputValidation.innerHTML = '';
        inputValidation.className = 'validation-status';
        updateButton();
        return;
    }
    validateTimer = setTimeout(() => validateInput(v), 500);
    updateButton();
});

outputPath.addEventListener('input', updateButton);

// =====================================================================
// Progress ko'rsatish
// =====================================================================

function renderProgress(data) {
    progressSection.classList.add('show');

    const percent = Math.min(100, data.percent || 0);
    document.getElementById('progressBar').style.width = `${percent}%`;
    document.getElementById('progressPercent').textContent = `${percent.toFixed(1)}%`;

    const statusMap = {
        queued: 'Navbatda...',
        calculating: 'Hajm hisoblanmoqda...',
        archiving: 'Arxivlanmoqda...',
        completed: 'Tayyor',
        error: 'Xatolik',
    };
    document.getElementById('progressStatus').textContent =
        statusMap[data.status] || data.status || '';

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

// =====================================================================
// Arxivlashni boshlash
// =====================================================================

async function createArchive() {
    const input = inputPath.value.trim();
    const output = outputPath.value.trim();
    if (!input || !output) return;

    archiveBtn.classList.add('loading');
    archiveBtn.disabled = true;
    resultSection.classList.remove('show');

    try {
        const res = await fetch(`${API}/archive`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ input_path: input, output_path: output }),
        });
        const data = await res.json();

        if (!data.success || !data.job_id) {
            showNotification(data.error || 'Arxivlashni boshlab bo\'lmadi', 'error');
            archiveBtn.classList.remove('loading');
            archiveBtn.disabled = false;
            return;
        }

        // Har 500ms da progressni so'raymiz
        const jobId = data.job_id;
        const poll = setInterval(async () => {
            try {
                const r = await fetch(`${API}/progress/${jobId}`);
                const p = await r.json();
                renderProgress(p);

                if (p.status === 'completed') {
                    clearInterval(poll);
                    document.getElementById('resultViloyat').textContent = p.viloyat_count;
                    document.getElementById('resultPath').textContent = p.output_path;
                    resultSection.classList.add('show');
                    showNotification(
                        `Tayyor! ${p.elapsed_seconds}s (${p.speed})`, 'success');
                    archiveBtn.classList.remove('loading');
                    archiveBtn.disabled = false;
                } else if (p.status === 'error') {
                    clearInterval(poll);
                    showNotification(p.error || 'Arxivlash xatoligi', 'error');
                    archiveBtn.classList.remove('loading');
                    archiveBtn.disabled = false;
                }
            } catch (e) {
                console.error('Progress xatoligi:', e);
            }
        }, 500);
    } catch {
        showNotification('Serverga ulanib bo\'lmadi', 'error');
        archiveBtn.classList.remove('loading');
        archiveBtn.disabled = false;
    }
}
