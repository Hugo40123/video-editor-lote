/* ═══════════════════════════════════════════════════
   VideoEditorLote v2.1 — Frontend Logic (Upload Flow)
   ═══════════════════════════════════════════════════ */

// ─── State ───────────────────────────────────────────────────────────────────
const STATE = {
    tab: 'editor',
    selectedContentIdx: null,
    selectedPostIdx: null,
    postQueue: [],
    outputVideos: [],
    processingTaskId: null,
    previewTimer: null,
    currentThumbnail: null,
    currentVideoName: null,
    // Upload state
    uploadedVideos: [],          // { server_path, original_name, size_mb }
    uploadedBgImage: null,       // { server_path, original_name }
    uploadedLogoImage: null,     // { server_path, original_name }
    sessionDir: null,            // server-side session directory
};

// ─── Init ────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    initNavigation();
    initUploadZone();
    initImageUploads();
    loadTemplates();
    loadDefaultPaths();
    checkFfmpeg();
    loadPostQueue();
    loadOutputVideos();
    loadSettings();
    loadDbPath();
    loadSchedulerStatus();
    // Load default background image into preview
    loadBgImage('/assets/fundo_padrao.jpg');
    drawPreview();
});

// ─── Navigation ──────────────────────────────────────────────────────────────
function initNavigation() {
    document.querySelectorAll('.nav-item[data-tab]').forEach(btn => {
        btn.addEventListener('click', () => {
            switchTab(btn.dataset.tab);
        });
    });
}

function switchTab(tab) {
    document.querySelectorAll('.nav-item').forEach(b => b.classList.remove('active'));
    const navBtn = document.querySelector(`.nav-item[data-tab="${tab}"]`);
    if (navBtn) navBtn.classList.add('active');
    document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
    const el = document.getElementById(`tab-${tab}`);
    if (el) el.classList.add('active');
    STATE.tab = tab;
    if (tab === 'posts') { loadPostQueue(); loadOutputVideos(); loadDashboardStats(); }
    if (tab === 'content') { loadPostQueue(); }
    if (tab === 'products') { loadLinkedProducts(); updateProductPostSelect(); loadAffiliateIds(); }
    if (tab === 'settings') { loadQueueStats(); checkFfmpeg(); loadSettings(); }
}

// ─── Toast ───────────────────────────────────────────────────────────────────
function toast(msg, type = 'info') {
    let c = document.querySelector('.toast-container');
    if (!c) { c = document.createElement('div'); c.className = 'toast-container'; document.body.appendChild(c); }
    const t = document.createElement('div');
    t.className = `toast ${type}`;
    t.textContent = msg;
    c.appendChild(t);
    setTimeout(() => { t.style.opacity = '0'; t.style.transition = 'opacity 0.3s'; setTimeout(() => t.remove(), 300); }, 3500);
}

// ─── Upload Zone ─────────────────────────────────────────────────────────────
function initUploadZone() {
    const zone = document.getElementById('uploadZone');
    const input = document.getElementById('fileInput');

    // Click to open file picker
    zone.addEventListener('click', () => input.click());

    // Drag events
    zone.addEventListener('dragover', (e) => { e.preventDefault(); zone.classList.add('dragover'); });
    zone.addEventListener('dragleave', () => zone.classList.remove('dragover'));
    zone.addEventListener('drop', (e) => {
        e.preventDefault();
        zone.classList.remove('dragover');
        if (e.dataTransfer.files.length) handleFiles(e.dataTransfer.files);
    });

    // File input change
    input.addEventListener('change', () => {
        if (input.files.length) handleFiles(input.files);
        input.value = '';
    });
}

function handleFiles(fileList) {
    const files = Array.from(fileList).filter(f => {
        const ext = f.name.split('.').pop().toLowerCase();
        return ['mp4', 'mov', 'avi', 'mkv', 'webm'].includes(ext);
    });

    if (!files.length) {
        toast('Nenhum arquivo de vídeo válido. Formatos: MP4, MOV, AVI, MKV, WEBM', 'warning');
        return;
    }

    if (STATE.uploadedVideos.length + files.length > 10) {
        toast(`Máximo de 10 vídeos por lote. Você já tem ${STATE.uploadedVideos.length}.`, 'warning');
        return;
    }

    uploadFiles(files);
}

async function uploadFiles(files) {
    const formData = new FormData();
    files.forEach(f => formData.append('files', f));

    toast(`Enviando ${files.length} vídeo(s)...`, 'info');

    try {
        const d = await apiUpload('/api/editor/upload', formData);
        STATE.sessionDir = d.session_dir;

        d.files.forEach(f => {
            STATE.uploadedVideos.push(f);
        });

        renderUploadedFiles();
        toast(`${d.count} vídeo(s) enviado(s)!`, 'success');

        // Update preview with first video
        if (STATE.uploadedVideos.length) {
            refreshPreview(STATE.uploadedVideos[0].server_path);
        }
    } catch (err) {
        toast(`Erro no upload: ${err.message}`, 'error');
    }
}

function renderUploadedFiles() {
    const container = document.getElementById('uploadedFiles');
    const zone = document.getElementById('uploadZone');
    const count = document.getElementById('uploadCount');

    if (STATE.uploadedVideos.length === 0) {
        container.innerHTML = '<div class="uploaded-files-empty">Nenhum vídeo enviado ainda.</div>';
        zone.classList.remove('has-files');
        count.textContent = '0';
        return;
    }

    zone.classList.add('has-files');
    count.textContent = STATE.uploadedVideos.length;

    container.innerHTML = STATE.uploadedVideos.map((v, i) =>
        `<div class="uploaded-file-item">
            <span class="uploaded-file-icon">🎬</span>
            <span class="uploaded-file-name" title="${v.original_name}">${v.original_name}</span>
            <span class="uploaded-file-size">${v.size_mb} MB</span>
            <span class="uploaded-file-remove" onclick="removeUploadedFile(${i})" title="Remover">✕</span>
        </div>`
    ).join('');
}

function removeUploadedFile(index) {
    STATE.uploadedVideos.splice(index, 1);
    renderUploadedFiles();
    if (STATE.uploadedVideos.length) {
        refreshPreview(STATE.uploadedVideos[0].server_path);
    } else {
        clearPreview();
    }
}

function clearUploadedFiles() {
    if (STATE.uploadedVideos.length && !confirm('Remover todos os vídeos enviados?')) return;
    STATE.uploadedVideos = [];
    STATE.sessionDir = null;
    renderUploadedFiles();
    clearPreview();
    toast('Vídeos removidos.', 'info');
}

// ─── Image Uploads (Background & Logo) ───────────────────────────────────────
function initImageUploads() {
    // Background image upload
    const bgInput = document.getElementById('bgFileInput');
    bgInput.addEventListener('change', async () => {
        if (!bgInput.files.length) return;
        await uploadImage(bgInput.files[0], 'bg');
        bgInput.value = '';
    });

    // Logo image upload
    const logoInput = document.getElementById('logoFileInput');
    logoInput.addEventListener('change', async () => {
        if (!logoInput.files.length) return;
        await uploadImage(logoInput.files[0], 'logo');
        logoInput.value = '';
    });
}

async function uploadImage(file, type) {
    const formData = new FormData();
    formData.append('file', file);

    try {
        const d = await apiUpload('/api/editor/upload-image', formData);
        if (type === 'bg') {
            STATE.uploadedBgImage = d;
            document.getElementById('bgImageName').textContent = `🖼️ ${d.original_name} (${d.size_mb} MB)`;
            // Load background image into preview cache
            const sessionMatch = d.server_path.match(/uploads[/\\]([^/\\]+)[/\\]/);
            if (sessionMatch) {
                const fname = d.server_path.split(/[/\\]/).pop();
                loadBgImage(`/uploads/${sessionMatch[1]}/${encodeURIComponent(fname)}`);
            }
        } else {
            STATE.uploadedLogoImage = d;
            document.getElementById('logoImageName').textContent = `©️ ${d.original_name} (${d.size_mb} MB)`;
        }
        toast(`${type === 'bg' ? 'Fundo' : 'Logo'} atualizado!`, 'success');
        drawPreview();
    } catch (err) {
        toast(`Erro ao enviar imagem: ${err.message}`, 'error');
    }
}

function resetImages() {
    STATE.uploadedBgImage = null;
    STATE.uploadedLogoImage = null;
    document.getElementById('bgImageName').textContent = '📷 Padrão (assets/fundo_padrao.jpg)';
        document.getElementById('logoImageName').textContent = '📷 Padrão (assets/logo_padrao.png)';
    drawPreview();
}

// ─── API helpers ─────────────────────────────────────────────────────────────
async function api(url, opts = {}) {
    const headers = { 'Content-Type': 'application/json' };
    const res = await fetch(url, { headers, ...opts });
    if (!res.ok) {
        const e = await res.json().catch(() => ({}));
        throw new Error(e.detail || `HTTP ${res.status}`);
    }
    return res.json();
}

async function apiUpload(url, formData) {
    const res = await fetch(url, { method: 'POST', body: formData });
    if (!res.ok) {
        const e = await res.json().catch(() => ({}));
        throw new Error(e.detail || `HTTP ${res.status}`);
    }
    return res.json();
}

// ─── Preview ─────────────────────────────────────────────────────────────────
function updateSlider(inputId, displayId, s) {
    document.getElementById(displayId).textContent = document.getElementById(inputId).value + s;
}

let _ps = false;
function schedulePreview() {
    if (_ps) return; _ps = true;
    setTimeout(() => { _ps = false; drawPreview(); }, 120);
}

// Loaded images for preview
let _bgImg = null;
let _thumbImg = null;

function loadBgImage(src) {
    if (!src) return;
    const img = new Image();
    img.onload = () => { _bgImg = img; drawPreview(); };
    img.onerror = () => { _bgImg = null; drawPreview(); };
    img.src = src;
}

function loadThumbImage(src) {
    if (!src) { _thumbImg = null; drawPreview(); return; }
    const img = new Image();
    img.onload = () => { _thumbImg = img; drawPreview(); };
    img.onerror = () => { _thumbImg = null; drawPreview(); };
    img.src = src;
}

async function refreshPreview(videoPath) {
    if (!videoPath && STATE.uploadedVideos.length) {
        videoPath = STATE.uploadedVideos[0].server_path;
    }
    if (!videoPath) { clearPreview(); return; }

    STATE.currentThumbnail = null;
    STATE.currentVideoName = null;

    try {
        const d = await api('/api/editor/thumbnail', {
            method: 'POST',
            body: JSON.stringify({ video_path: videoPath })
        });
        if (d.thumbnail) {
            STATE.currentThumbnail = d.thumbnail;
            loadThumbImage(d.thumbnail);
        } else {
            _thumbImg = null;
            drawPreview();
        }
        if (d.video_name) STATE.currentVideoName = d.video_name;
        document.getElementById('previewVideoName').textContent =
            `${d.video_name || 'Video'} - ${STATE.uploadedVideos.length} enviado(s)`;
    } catch (e) {
        _thumbImg = null;
        drawPreview();
        document.getElementById('previewVideoName').textContent =
            `${STATE.uploadedVideos.length} video(s) enviado(s)`;
    }
}

function clearPreview() {
    STATE.currentThumbnail = null;
    STATE.currentVideoName = null;
    _thumbImg = null;
    document.getElementById('previewVideoName').textContent = 'Nenhum video enviado';
    drawPreview();
}

function resetPreview() {
    ['videoSize', 'videoWidth', 'videoOffsetX', 'videoOffsetY', 'textMarkOffsetX', 'textMarkOffsetY']
        .forEach(id => { document.getElementById(id).value = /Offset/.test(id) ? 0 : 100; });
    updateSlider('videoSize', 'videoSizeVal', '%');
    updateSlider('videoWidth', 'videoWidthVal', '%');
    ['videoOffsetX', 'videoOffsetY', 'textMarkOffsetX', 'textMarkOffsetY']
        .forEach(id => updateSlider(id, id.replace('video', '').replace('text', '') + 'Val', ' px'));
    drawPreview();
}

function drawPreview() {
    const canvas = document.getElementById('previewCanvas');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const W = canvas.width, H = canvas.height;
    ctx.clearRect(0, 0, W, H);

    const pad = 6;
    const sc = Math.min((W - pad * 2) / 1080, (H - pad * 2) / 1920);
    const pw = Math.round(1080 * sc);
    const ph = Math.round(1920 * sc);
    const ox = Math.round((W - pw) / 2);
    const oy = Math.round((H - ph) / 2);

    // 1) Background
    ctx.fillStyle = '#0A0A12';
    ctx.fillRect(0, 0, W, H);

    if (_bgImg && _bgImg.complete && _bgImg.naturalWidth > 0) {
        try {
            ctx.save();
            ctx.beginPath();
            ctx.rect(ox, oy, pw, ph);
            ctx.clip();
            const imgR = _bgImg.naturalWidth / _bgImg.naturalHeight;
            const canR = pw / ph;
            let dw, dh, ddx, ddy;
            if (imgR > canR) { dh = ph; dw = Math.round(ph * imgR); }
            else { dw = pw; dh = Math.round(pw / imgR); }
            ddx = ox + Math.round((pw - dw) / 2);
            ddy = oy + Math.round((ph - dh) / 2);
            ctx.drawImage(_bgImg, ddx, ddy, dw, dh);
            ctx.restore();
        } catch (e) {}
    }

    ctx.strokeStyle = '#2A2A3A';
    ctx.lineWidth = 1;
    ctx.strokeRect(ox, oy, pw, ph);

    // 2) Video area
    const vs = +g('videoSize') || 100;
    const vw = +g('videoWidth') || 100;
    const vwi = Math.round(900 * vs / 100 * vw / 100 * sc);
    const vhi = Math.round(1460 * vs / 100 * sc);
    const vx = +g('videoOffsetX') || 0;
    const vy = +g('videoOffsetY') || 0;
    const vcx = Math.round(ox + (pw - vwi) / 2 + vx * sc);
    const vcy = Math.round(oy + (ph - vhi) / 2 + vy * sc);

    if (_thumbImg && _thumbImg.complete && _thumbImg.naturalWidth > 0) {
        try {
            ctx.save();
            ctx.beginPath();
            ctx.roundRect(vcx, vcy, vwi, vhi, 4);
            ctx.clip();
            const tR = _thumbImg.naturalWidth / _thumbImg.naturalHeight;
            const vR = vwi / vhi;
            let tw, th, ttx, tty;
            if (tR > vR) { th = vhi; tw = Math.round(vhi * tR); }
            else { tw = vwi; th = Math.round(vwi / tR); }
            ttx = vcx + Math.round((vwi - tw) / 2);
            tty = vcy + Math.round((vhi - th) / 2);
            ctx.drawImage(_thumbImg, ttx, tty, tw, th);
            ctx.restore();
        } catch (e) {
            // Fallback: draw placeholder
            ctx.fillStyle = '#1A1A2E';
            ctx.beginPath(); ctx.roundRect(vcx, vcy, vwi, vhi, 4); ctx.fill();
        }
    } else {
        ctx.fillStyle = '#1A1A2E';
        ctx.beginPath(); ctx.roundRect(vcx, vcy, vwi, vhi, 4); ctx.fill();
        ctx.fillStyle = '#9090A8';
        ctx.font = 'bold 8px Inter,sans-serif';
        ctx.textAlign = 'center';
        const label = STATE.currentVideoName || 'video';
        const shortName = label.length > 18 ? label.substring(0, 16) + '...' : label;
        ctx.fillText('\u{1F3AC} ' + shortName, vcx + vwi / 2, vcy + vhi / 2 + 3);
    }

    ctx.strokeStyle = '#6C63FF';
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.roundRect(vcx, vcy, vwi, vhi, 4);
    ctx.stroke();

    // 3) Watermark mask
    if (cb('removeWatermark')) {
        const dx = +g('delogoX') || 190, dy = +g('delogoY') || 860;
        const dw = +g('delogoWidth') || 700, dh = +g('delogoHeight') || 160;
        ctx.strokeStyle = '#F59E0B';
        ctx.lineWidth = 1.5;
        ctx.setLineDash([3, 3]);
        ctx.strokeRect(ox + dx * sc, oy + dy * sc, dw * sc, dh * sc);
        ctx.setLineDash([]);
        ctx.fillStyle = '#F6C06A';
        ctx.font = '6px Inter,sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('area ocultada', ox + dx * sc + dw * sc / 2, Math.max(oy + 6, oy + dy * sc - 2));
    }

    // 4) Logo
    if (cb('applyLogo')) {
        const lw = Math.round(180 * sc), lh = Math.round(78 * sc);
        ctx.fillStyle = '#E8E8F0';
        ctx.fillRect(ox + pw - lw - 40 * sc, oy + ph - lh - 40 * sc, lw, lh);
        ctx.fillStyle = '#0A0A12';
        ctx.font = 'bold 6px Inter,sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('LOGO', ox + pw - lw / 2 - 40 * sc, oy + ph - lh / 2 - 40 * sc + 2);
    }

    // 5) @ text
    if (cb('applyTextMark')) {
        const txt = g('textMark').trim() || '@marca';
        const fs = +g('textMarkSize') || 76;
        const mtx = +g('textMarkOffsetX') || 0, mty = +g('textMarkOffsetY') || 0;
        const fz = Math.max(7, Math.min(16, fs * sc * 1.4));
        ctx.font = 'bold ' + fz + 'px Inter,sans-serif';
        ctx.textAlign = 'center';
        ctx.fillStyle = '#1D2430';
        ctx.fillText(txt, ox + pw / 2 + mtx * sc + 1, oy + ph / 2 + mty * sc + 1);
        ctx.fillStyle = '#B8C7DA';
        ctx.fillText(txt, ox + pw / 2 + mtx * sc, oy + ph / 2 + mty * sc);
    }
}

// ─── Shortcuts ───────────────────────────────────────────────────────────────
function g(id) { return document.getElementById(id)?.value || ''; }
function cb(id) { return document.getElementById(id)?.checked || false; }

// ─── Templates ───────────────────────────────────────────────────────────────
async function loadTemplates() {
    try {
        const d = await api('/api/editor/templates');
        const s = document.getElementById('templateSelect');
        s.innerHTML = '';
        d.labels.forEach(l => { const o = document.createElement('option'); o.value = l; o.textContent = l; s.appendChild(o); });
    } catch {}
}

// ─── Default paths ───────────────────────────────────────────────────────────
async function loadDefaultPaths() {
    try {
        const d = await api('/api/editor/default-paths');
        if (d.output_folder) document.getElementById('settingOutputDir').textContent = d.output_folder;
        if (d.upload_dir) document.getElementById('settingUploadDir').textContent = d.upload_dir;
        document.getElementById('settingOutputDir').textContent = d.output_folder || '---';
    } catch {}
}

// ─── DB Path ─────────────────────────────────────────────────────────────────
async function loadDbPath() {
    try {
        const d = await api('/api/config/paths');
        const el = document.getElementById('settingDbPath');
        if (el) el.textContent = d.writable_root + '\\config\\app.db';
    } catch {}
}

// ─── FFmpeg ──────────────────────────────────────────────────────────────────
async function checkFfmpeg() {
    try {
        const d = await api('/api/editor/ffmpeg-check');
        const el = document.getElementById('ffmpegStatus');
        el.textContent = d.found ? 'Encontrado' : 'Nao encontrado';
        el.style.color = d.found ? 'var(--green)' : 'var(--red)';
    } catch { document.getElementById('ffmpegStatus').textContent = 'Erro'; }
}

// ─── Processing ──────────────────────────────────────────────────────────────
async function startProcessing() {
    if (!STATE.uploadedVideos.length) {
        toast('Envie vídeos primeiro! Arraste para a área de upload.', 'warning');
        return;
    }

    const btn = document.getElementById('processBtn');
    btn.disabled = true; btn.textContent = 'Processando...';

    const ind = document.getElementById('processingIndicator');
    ind.classList.add('active');
    document.getElementById('processingStatus').textContent = 'Iniciando...';

    const log = document.getElementById('editorLog'); log.innerHTML = '';
    const pf = document.getElementById('progressFill'); pf.style.width = '0%';
    logLine(log, 'Iniciando processamento...', 'info');

    try {
        const videoFiles = STATE.uploadedVideos.map(v => v.server_path);
        const bgImage = STATE.uploadedBgImage ? STATE.uploadedBgImage.server_path : '';
        const logoImage = STATE.uploadedLogoImage ? STATE.uploadedLogoImage.server_path : '';

        const d = await api('/api/editor/process', {
            method: 'POST',
            body: JSON.stringify({
                video_files: videoFiles,
                background_image: bgImage,
                logo_image: logoImage,
                max_duration: parseFloat(g('maxDuration')) || null,
                template: g('templateSelect'),
                apply_watermark: cb('applyLogo'),
                apply_text_watermark: cb('applyTextMark'),
                text_watermark: g('textMark'),
                text_watermark_size: +g('textMarkSize')||76,
                text_watermark_offset_x: +g('textMarkOffsetX')||0,
                text_watermark_offset_y: +g('textMarkOffsetY')||0,
                video_size: +g('videoSize')||100,
                video_width: +g('videoWidth')||100,
                video_offset_x: +g('videoOffsetX')||0,
                video_offset_y: +g('videoOffsetY')||0,
                remove_center_watermark: cb('removeWatermark'),
                delogo_x: +g('delogoX')||190,
                delogo_y: +g('delogoY')||860,
                delogo_width: +g('delogoWidth')||700,
                delogo_height: +g('delogoHeight')||160,
            }),
        });
        STATE.processingTaskId = d.task_id;
        document.getElementById('processingStatus').textContent = `Processando ${d.video_count} video(s)...`;
        listenToStream(d.task_id);
    } catch (err) {
        logLine(log, `Erro: ${err.message}`, 'error');
        btn.disabled = false; btn.textContent = '▶ Gerar vídeos';
        ind.classList.remove('active');
        toast(err.message, 'error');
    }
}

function listenToStream(taskId) {
    const log = document.getElementById('editorLog');
    const pf = document.getElementById('progressFill');
    const ind = document.getElementById('processingIndicator');
    const es = new EventSource(`/api/editor/stream/${taskId}`);

    es.onmessage = e => {
        try {
            const d = JSON.parse(e.data);
            if (d.type === 'log') logLine(log, d.message);
            else if (d.type === 'progress') pf.style.width = `${Math.round(d.value*100)}%`;
            else if (d.type === 'complete') {
                es.close();
                const btn = document.getElementById('processBtn');
                btn.disabled = false; btn.textContent = '\u25B6 Gerar v\u00eddeos';
                ind.classList.remove('active');
                if (d.summary.error) {
                    logLine(log, `Erro: ${d.summary.error}`, 'error');
                    toast('Processamento com erros', 'error');
                } else {
                    pf.style.width = '100%';
                    logLine(log, `Concluido: ${d.summary.successes} sucesso(s)`, 'success');
                    toast(`${d.summary.successes} video(s) gerado(s)!`, 'success');

                    // Show download links
                    if (d.summary.output_files?.length) {
                        logLine(log, 'Links para download:', 'info');
                        d.summary.output_files.forEach((fp, i) => {
                            const fname = fp.split(/[/\\\\]/).pop();
                            const url = `/output/${encodeURIComponent(fname)}`;
                            logLineHtml(log, `  ${i+1}. <a href="${url}" download class="log-download-link">${fname}</a>`, 'info');
                        });
                    }

                    // Auto-add output videos to the post queue (async, not awaited in onmessage)
                    if (d.summary.output_files?.length) {
                        api('/api/posts', {
                            method: 'POST',
                            body: JSON.stringify({ video_paths: d.summary.output_files }),
                        }).then(result => {
                            if (result.added > 0) toast(`${result.added} video(s) adicionado(s) a fila!`, 'success');
                        }).catch(() => {});
                    }

                    loadOutputVideos();
                    loadPostQueue();

                    // Auto-switch to content tab
                    setTimeout(() => {
                        switchTab('content');
                        toast('Aba Conteudo - gere as legendas!', 'info');
                    }, 1500);
                }
            }
        } catch {}
    };
    es.onerror = () => {
        es.close();
        document.getElementById('processBtn').disabled = false;
        document.getElementById('processBtn').textContent = '▶ Gerar vídeos';
        ind.classList.remove('active');
    };
}

function logLine(container, msg, type = '') {
    const d = document.createElement('div');
    d.className = `log-entry ${type}`;
    d.textContent = msg;
    container.appendChild(d);
    container.scrollTop = container.scrollHeight;
}

function logLineHtml(container, html, type = '') {
    const d = document.createElement('div');
    d.className = `log-entry ${type}`;
    d.innerHTML = html;
    container.appendChild(d);
    container.scrollTop = container.scrollHeight;
}

// ─── AI Provider Toggle ─────────────────────────────────────────────────────
function toggleAiProvider() {
    const provider = g('aiProvider');
    document.getElementById('groqConfig').style.display = provider === 'groq' ? 'block' : 'none';
    document.getElementById('geminiConfig').style.display = provider === 'gemini' ? 'block' : 'none';
}

// ─── Groq Settings ──────────────────────────────────────────────────────────
async function saveGroqSettings() {
    const key = g('settingsGroqKey');
    const model = g('settingsGroqModel') || 'llama-3.1-8b-instant';
    if (!key) { toast('Informe a chave da API Groq.', 'warning'); return; }
    try {
        await api('/api/settings', {
            method: 'PUT',
            body: JSON.stringify({ groq_api_key: key, groq_model: model, ai_provider: 'groq' }),
        });
        document.getElementById('settingsGroqStatus').textContent = 'Salvo';
        document.getElementById('settingsGroqStatus').style.color = 'var(--green)';
        toast('Configuracao Groq salva!', 'success');
    } catch { toast('Erro ao salvar.', 'error'); }
}

async function testGroqFromSettings() {
    const key = g('settingsGroqKey');
    if (!key) { toast('Informe a chave da API Groq primeiro.', 'warning'); return; }
    const log = document.getElementById('contentLog'); log.innerHTML = '';
    logLine(log, 'Testando conexao com Groq...', 'info');
    try {
        const d = await api('/api/content/test-groq', {
            method: 'POST',
            body: JSON.stringify({
                groq_api_key: key,
                groq_model: g('settingsGroqModel') || 'llama-3.1-8b-instant',
            }),
        });
        if (d.logs) d.logs.forEach(m => logLine(log, m));
        if (d.success) {
            logLine(log, 'Groq API OK!', 'success');
            document.getElementById('settingsGroqStatus').textContent = 'Conectado';
            document.getElementById('settingsGroqStatus').style.color = 'var(--green)';
            toast('Groq conectado!', 'success');
        } else {
            logLine(log, `Falha: ${d.error}`, 'error');
            document.getElementById('settingsGroqStatus').textContent = 'Falha';
            document.getElementById('settingsGroqStatus').style.color = 'var(--red)';
            toast('Falha no Groq.', 'error');
        }
    } catch (err) { logLine(log, `Erro: ${err.message}`, 'error'); }
}

// ─── Gemini Settings ─────────────────────────────────────────────────────────
async function saveGeminiSettings() {
    const key = g('settingsGeminiKey');
    const model = g('settingsGeminiModel') || 'gemini-2.0-flash';
    if (!key) { toast('Informe a chave da API Gemini.', 'warning'); return; }
    try {
        await api('/api/settings', {
            method: 'PUT',
            body: JSON.stringify({ ai_gemini_key: key, ai_gemini_model: model }),
        });
        document.getElementById('settingsGeminiStatus').textContent = 'Salvo';
        document.getElementById('settingsGeminiStatus').style.color = 'var(--green)';
        toast('Configuracao Gemini salva!', 'success');
    } catch { toast('Erro ao salvar.', 'error'); }
}

async function testGeminiFromSettings() {
    const key = g('settingsGeminiKey');
    if (!key) { toast('Informe a chave da API primeiro.', 'warning'); return; }
    const log = document.getElementById('contentLog'); log.innerHTML = '';
    logLine(log, 'Testando conexao com Google Gemini...', 'info');
    try {
        const d = await api('/api/content/test-gemini', {
            method: 'POST',
            body: JSON.stringify({
                gemini_api_key: key,
                gemini_model: g('settingsGeminiModel') || 'gemini-2.0-flash',
            }),
        });
        // Show detailed logs
        if (d.logs) d.logs.forEach(m => logLine(log, m));

        if (d.success) {
            logLine(log, 'Gemini API OK!', 'success');
            document.getElementById('settingsGeminiStatus').textContent = 'Conectado';
            document.getElementById('settingsGeminiStatus').style.color = 'var(--green)';
            toast('Gemini conectado!', 'success');
        } else {
            logLine(log, `Falha: ${d.error}`, 'error');
            document.getElementById('settingsGeminiStatus').textContent = 'Falha';
            document.getElementById('settingsGeminiStatus').style.color = 'var(--red)';
            toast('Falha no Gemini. Veja os logs.', 'error');
        }
    } catch (err) { logLine(log, `Erro: ${err.message}`, 'error'); }
}

// ─── Content ─────────────────────────────────────────────────────────────────
async function loadPostQueue() {
    try {
        // Clean orphan posts first
        await api('/api/posts/maintenance/cleanup-orphans', { method: 'POST' });
        STATE.postQueue = await api('/api/posts');
        renderContentQueue(STATE.postQueue);
        renderPostQueue(STATE.postQueue);
    } catch {}
}

function renderContentQueue(items) {
    const list = document.getElementById('contentQueueList');
    if (!items?.length) {
        list.innerHTML = '<div class="queue-placeholder"><span class="placeholder-icon">🎬</span>Nenhum video na fila.<br>Processe videos na aba <strong>Edicao</strong> ou importe da pasta de saida.</div>';
        return;
    }
    list.innerHTML = items.map((item, idx) => {
        const name = item.video_path?.split(/[/\\\\]/).pop() || 'video';
        const st = item.content_status || 'Pendente';
        return `<div class="queue-item ${STATE.selectedContentIdx === idx ? 'selected' : ''}" onclick="selectContentItem(${idx})">
            <span class="queue-item-name">${name}</span>
            <span class="queue-item-status ${st.toLowerCase().replace(/\\s+/g,'')}">${st}</span>
        </div>`;
    }).join('');
}

function selectContentItem(idx) {
    STATE.selectedContentIdx = idx;
    renderContentQueue(STATE.postQueue);
    const item = STATE.postQueue[idx];
    if (!item) return;
    document.getElementById('contentMeta').textContent =
        `${item.video_path?.split(/[/\\\\]/).pop() || 'video'}  |  Status: ${item.content_status || 'Pendente'}`;
    document.getElementById('contentKeywords').value = item.product_keywords || '';
    document.getElementById('contentProductQuery').value = item.product_query || '';
    document.getElementById('contentAffiliateLink').value = item.affiliate_link || '';
    document.getElementById('contentTitle').value = item.content_title || '';
    document.getElementById('contentCta').value = item.content_cta || '';
    document.getElementById('contentHashtags').value = item.content_hashtags || '';
    document.getElementById('contentCaption').value = item.caption || '';
}

async function importOutputVideos() {
    try {
        const v = await api('/api/posts/output/videos');
        if (!v.videos?.length) { toast('Nenhum video na pasta de saida.', 'warning'); return; }
        const d = await api('/api/posts', { method: 'POST', body: JSON.stringify({ video_paths: v.videos }) });
        toast(`${d.added} video(s) importado(s)!`, 'success');
        loadPostQueue();
    } catch (err) { toast('Erro: ' + err.message, 'error'); }
}

async function generateLocalContent() {
    if (STATE.selectedContentIdx === null) { toast('Selecione um video da fila.', 'warning'); return; }
    const item = STATE.postQueue[STATE.selectedContentIdx];
    if (!item?.video_path) { toast('Item invalido.', 'error'); return; }
    try {
        const d = await api('/api/content/generate-local', {
            method: 'POST',
            body: JSON.stringify({
                video_path: item.video_path, keywords: g('contentKeywords'),
                base_hashtags: g('postDefaultHashtags') || '#achadinhos #shopee #mercadolivre',
            }),
        });
        if (!d.success) { toast('Erro ao gerar.', 'error'); return; }
        document.getElementById('contentTitle').value = d.title || '';
        document.getElementById('contentCta').value = d.cta || '';
        document.getElementById('contentHashtags').value = d.hashtags || '';
        document.getElementById('contentProductQuery').value = d.product_query || '';
        document.getElementById('contentCaption').value = d.caption || '';
        toast('Rascunho rapido gerado!', 'success');
    } catch (err) { toast('Erro: ' + err.message, 'error'); }
}

async function generateAIContent() {
    if (STATE.selectedContentIdx === null) { toast('Selecione um video da fila.', 'warning'); return; }
    const item = STATE.postQueue[STATE.selectedContentIdx];
    if (!item?.video_path) { toast('Item invalido.', 'error'); return; }
    const log = document.getElementById('contentLog'); log.innerHTML = '';

    const provider = g('aiProvider') || 'groq';

    if (provider === 'groq') {
        const groqKey = g('settingsGroqKey');
        const groqModel = g('settingsGroqModel') || 'llama-3.1-8b-instant';
        if (!groqKey) {
            logLine(log, 'Configure a chave da API Groq na aba Configuracoes.', 'error');
            toast('Configure o Groq nas Configuracoes.', 'warning');
            return;
        }
        logLine(log, 'Extraindo audio e transcrevendo com Groq...', 'info');
        try {
            const d = await api('/api/content/generate-ai', {
                method: 'POST',
                body: JSON.stringify({
                    video_path: item.video_path,
                    keywords: g('contentKeywords'),
                    base_hashtags: g('postDefaultHashtags') || '#achadinhos #shopee #mercadolivre',
                    ai_config: { provider: 'groq', groq_api_key: groqKey, groq_model: groqModel },
                }),
            });
            if (d.logs) d.logs.forEach(m => logLine(log, m));
            if (!d.success) { logLine(log, `Erro: ${d.error}`, 'error'); toast('Erro na IA.', 'error'); return; }
            if (d.has_audio) {
                logLine(log, 'Audio transcrito com sucesso!', 'success');
            } else {
                logLine(log, 'Sem audio. Revise a legenda manualmente.', 'warning');
                toast('Sem audio no video. Revise a legenda!', 'warning');
            }
            document.getElementById('contentTitle').value = d.title || '';
            document.getElementById('contentCta').value = d.cta || '';
            document.getElementById('contentHashtags').value = d.hashtags || '';
            document.getElementById('contentProductQuery').value = d.product_query || '';
            document.getElementById('contentCaption').value = d.caption || '';
            logLine(log, 'Conteudo gerado com Groq!', 'success');
            toast('Conteudo gerado com Groq!', 'success');
        } catch (err) { logLine(log, `Erro: ${err.message}`, 'error'); toast('Erro: ' + err.message, 'error'); }
    } else {
        // Gemini
        const geminiKey = g('settingsGeminiKey');
        const geminiModel = g('settingsGeminiModel') || 'gemini-2.0-flash';
        if (!geminiKey) {
            logLine(log, 'Configure a chave da API Gemini na aba Configuracoes.', 'error');
            toast('Configure o Gemini nas Configuracoes.', 'warning');
            return;
        }
        logLine(log, 'Enviando frame para Gemini...', 'info');
        try {
            const d = await api('/api/content/generate-ai', {
                method: 'POST',
                body: JSON.stringify({
                    video_path: item.video_path,
                    keywords: g('contentKeywords'),
                    base_hashtags: g('postDefaultHashtags') || '#achadinhos #shopee #mercadolivre',
                    ai_config: { provider: 'gemini', gemini_api_key: geminiKey, gemini_model: geminiModel },
                }),
            });
            if (d.logs) d.logs.forEach(m => logLine(log, m));
            if (!d.success) { logLine(log, `Erro: ${d.error}`, 'error'); toast('Erro na IA.', 'error'); return; }
            if (d.has_audio) {
                logLine(log, 'Audio detectado!', 'success');
            } else {
                logLine(log, 'Sem audio. Revise manualmente.', 'warning');
            }
            document.getElementById('contentTitle').value = d.title || '';
            document.getElementById('contentCta').value = d.cta || '';
            document.getElementById('contentHashtags').value = d.hashtags || '';
            document.getElementById('contentProductQuery').value = d.product_query || '';
            document.getElementById('contentCaption').value = d.caption || '';
            logLine(log, 'Conteudo gerado com Gemini!', 'success');
            toast('Conteudo gerado com Gemini!', 'success');
        } catch (err) { logLine(log, `Erro: ${err.message}`, 'error'); toast('Erro: ' + err.message, 'error'); }
    }
}

async function saveContent() {
    if (STATE.selectedContentIdx === null) { toast('Selecione um item.', 'warning'); return; }
    const item = STATE.postQueue[STATE.selectedContentIdx];
    if (!item?.id) { toast('Item invalido.', 'error'); return; }
    try {
        const d = await api(`/api/posts/${item.id}`, {
            method: 'PUT',
            body: JSON.stringify({
                content_title: g('contentTitle'), content_cta: g('contentCta'),
                content_hashtags: g('contentHashtags'), product_keywords: g('contentKeywords'),
                product_query: g('contentProductQuery'), affiliate_link: g('contentAffiliateLink'),
                caption: document.getElementById('contentCaption')?.value || '', content_status: 'Gerado',
            }),
        });
        if (d.updated) { toast('Salvo na fila!', 'success'); loadPostQueue(); }
    } catch { toast('Erro ao salvar.', 'error'); }
}

async function approveContent() {
    await saveContent();
    if (STATE.selectedContentIdx === null) return;
    const item = STATE.postQueue[STATE.selectedContentIdx];
    if (!item?.id) return;
    try {
        await api(`/api/posts/${item.id}`, { method: 'PUT', body: JSON.stringify({ content_status: 'Aprovado' }) });
        toast('Conteudo aprovado!', 'success'); loadPostQueue();
    } catch { toast('Erro ao aprovar.', 'error'); }
}

function copyCaption(id) {
    const el = document.getElementById(id);
    if (!el?.value) { toast('Legenda vazia.', 'warning'); return; }
    navigator.clipboard.writeText(el.value).then(() => toast('Copiado!', 'success')).catch(() => toast('Erro ao copiar.', 'error'));
}

// ─── Post Queue ──────────────────────────────────────────────────────────────
function renderPostQueue(items) {
    const list = document.getElementById('postQueueList');
    if (!items?.length) {
        list.innerHTML = '<div class="queue-placeholder"><span class="placeholder-icon">📋</span>Fila vazia.</div>';
        return;
    }
    list.innerHTML = items.map((item, idx) => {
        const name = item.video_path?.split(/[/\\\\]/).pop() || 'video';
        const st = (item.status || 'Pronto').toLowerCase();
        const sched = item.scheduled_for ? ` - ${item.scheduled_for}` : '';
        return `<div class="queue-item ${STATE.selectedPostIdx === idx ? 'selected' : ''}" onclick="selectPostItem(${idx})">
            <span class="queue-item-name">${name}${sched}</span>
            <span class="queue-item-status ${st}">${item.status || 'Pronto'}</span>
        </div>`;
    }).join('');
}

function selectPostItem(idx) {
    STATE.selectedPostIdx = idx;
    renderPostQueue(STATE.postQueue);
    const item = STATE.postQueue[idx];
    if (!item) return;
    document.getElementById('postMeta').textContent =
        `${item.video_path?.split(/[/\\\\]/).pop() || 'video'}  |  ${item.profile || 'Perfil principal'}`;
    document.getElementById('postStatus').value = item.status || 'Pronto';
    document.getElementById('postScheduledFor').value = item.scheduled_for || '';
    document.getElementById('postCaption').value = item.caption || '';
}

async function loadOutputVideos() {
    try {
        const d = await api('/api/posts/output/videos');
        STATE.outputVideos = d.videos || [];
        renderOutputVideos(STATE.outputVideos);
    } catch {}
}

function renderOutputVideos(videos) {
    const list = document.getElementById('postVideoList');
    if (!videos?.length) {
        list.innerHTML = '<div class="queue-placeholder"><span class="placeholder-icon">📂</span>Nenhum video na pasta de saida.</div>';
        return;
    }
    const queued = new Set(STATE.postQueue.map(i => i.video_path));
    list.innerHTML = videos.map(v => {
        const name = v.split(/[/\\\\]/).pop();
        const downloadUrl = `/output/${encodeURIComponent(name)}`;
        return `<div class="output-video-item">
            <span class="output-video-name">${name} ${queued.has(v) ? '\u2705' : '\u2B1C'}</span>
            <a href="${downloadUrl}" class="output-video-download" download title="Baixar">⬇️</a>
        </div>`;
    }).join('');
}

async function addAllToQueue() {
    const vids = STATE.outputVideos;
    if (!vids?.length) { toast('Nenhum video disponivel.', 'warning'); return; }
    try {
        const d = await api('/api/posts', { method: 'POST', body: JSON.stringify({ video_paths: vids }) });
        toast(`${d.added} video(s) adicionado(s)!`, 'success');
        loadPostQueue(); loadOutputVideos();
    } catch (err) { toast('Erro: ' + err.message, 'error'); }
}

async function savePostItem() {
    if (STATE.selectedPostIdx === null) { toast('Selecione um item.', 'warning'); return; }
    const item = STATE.postQueue[STATE.selectedPostIdx];
    if (!item?.id) return;
    try {
        await api(`/api/posts/${item.id}`, {
            method: 'PUT',
            body: JSON.stringify({
                caption: document.getElementById('postCaption')?.value || '',
                status: g('postStatus'), scheduled_for: g('postScheduledFor'),
            }),
        });
        toast('Salvo!', 'success'); loadPostQueue();
    } catch { toast('Erro ao salvar.', 'error'); }
}

async function removePostItem() {
    if (STATE.selectedPostIdx === null) { toast('Selecione um item.', 'warning'); return; }
    const item = STATE.postQueue[STATE.selectedPostIdx];
    if (!item?.id) return;
    if (!confirm('Remover este item da fila?')) return;
    try {
        await api(`/api/posts/${item.id}`, { method: 'DELETE' });
        STATE.selectedPostIdx = null;
        toast('Removido.', 'success');
        loadPostQueue(); loadOutputVideos();
    } catch { toast('Erro ao remover.', 'error'); }
}

async function publishPost() {
    if (STATE.selectedPostIdx === null) { toast('Selecione um item.', 'warning'); return; }
    const item = STATE.postQueue[STATE.selectedPostIdx];
    if (!item?.id) return;
    const uid = g('settingsIgUserId');
    const tok = g('settingsIgAccessToken');
    if (!uid || !tok) { toast('Configure IG User ID e Token na aba Configuracoes.', 'warning'); return; }
    await savePostItem();
    const log = document.getElementById('postLog'); log.innerHTML = '';
    logLine(log, 'Publicando no Instagram...', 'info');
    try {
        const d = await api(`/api/posts/${item.id}/publish`, {
            method: 'POST',
            body: JSON.stringify({
                ig_user_id: uid, access_token: tok,
                api_version: 'v25.0', media_type: 'REELS', share_to_feed: true,
            }),
        });
        if (d.logs) d.logs.forEach(m => logLine(log, m));
        if (d.success) {
            logLine(log, `Publicado! ID: ${d.instagram_post_id}`, 'success');
            toast('Publicado com sucesso!', 'success');
            loadPostQueue();
        } else { logLine(log, `Erro: ${d.error}`, 'error'); toast('Erro na publicacao.', 'error'); }
    } catch (err) { logLine(log, `Erro: ${err.message}`, 'error'); toast('Erro: ' + err.message, 'error'); }
}

// ─── Instagram Settings ──────────────────────────────────────────────────────
async function saveIgSettings() {
    const uid = g('settingsIgUserId');
    const tok = g('settingsIgAccessToken');
    if (!uid || !tok) { toast('Preencha o User ID e o Token.', 'warning'); return; }
    try {
        await api('/api/settings', {
            method: 'PUT',
            body: JSON.stringify({ instagram_user_id: uid, instagram_access_token: tok }),
        });
        document.getElementById('settingsIgStatus').textContent = 'Salvo';
        document.getElementById('settingsIgStatus').style.color = 'var(--green)';
        updatePostIgStatus('Configurado');
        toast('Credenciais salvas!', 'success');
    } catch { toast('Erro ao salvar.', 'error'); }
}

async function testIgConnectionReal() {
    const uid = g('settingsIgUserId');
    const tok = g('settingsIgAccessToken');
    if (!uid || !tok) { toast('Configure o User ID e Token primeiro.', 'warning'); return; }
    toast('Testando conexao com Instagram...', 'info');
    try {
        const url = `https://graph.facebook.com/v25.0/${encodeURIComponent(uid)}?fields=id,username&access_token=${encodeURIComponent(tok)}`;
        const response = await fetch(url);
        const data = await response.json();
        if (data.id && data.username) {
            document.getElementById('settingsIgStatus').textContent = `@${data.username}`;
            document.getElementById('settingsIgStatus').style.color = 'var(--green)';
            updatePostIgStatus(`@${data.username}`);
            toast(`Conectado como @${data.username}`, 'success');
        } else {
            const errMsg = data.error?.message || 'Token invalido';
            document.getElementById('settingsIgStatus').textContent = `Falha: ${errMsg.substring(0, 40)}`;
            document.getElementById('settingsIgStatus').style.color = 'var(--red)';
            updatePostIgStatus('Falha');
            toast('Falha na conexao.', 'error');
        }
    } catch (err) {
        document.getElementById('settingsIgStatus').textContent = 'Erro de conexao';
        document.getElementById('settingsIgStatus').style.color = 'var(--red)';
        toast('Erro de conexao.', 'error');
    }
}

function updatePostIgStatus(status) {
    const el = document.getElementById('postIgStatus');
    if (el) el.textContent = status;
}

// ─── Settings ────────────────────────────────────────────────────────────────
async function loadSettings() {
    try {
        const d = await api('/api/settings');
        const s = d.settings || {};

        // AI provider
        if (s.ai_provider) {
            document.getElementById('aiProvider').value = s.ai_provider;
            toggleAiProvider();
        }

        // Groq settings
        if (s.groq_api_key) {
            document.getElementById('settingsGroqKey').value = s.groq_api_key;
            document.getElementById('settingsGroqStatus').textContent = 'Configurado';
            document.getElementById('settingsGroqStatus').style.color = 'var(--green)';
        }
        if (s.groq_model) document.getElementById('settingsGroqModel').value = s.groq_model;

        // Gemini settings
        if (s.ai_gemini_key) {
            document.getElementById('settingsGeminiKey').value = s.ai_gemini_key;
            document.getElementById('settingsGeminiStatus').textContent = 'Configurado';
            document.getElementById('settingsGeminiStatus').style.color = 'var(--green)';
        }
        if (s.ai_gemini_model) document.getElementById('settingsGeminiModel').value = s.ai_gemini_model;

        // Instagram settings
        if (s.instagram_user_id) document.getElementById('settingsIgUserId').value = s.instagram_user_id;
        if (s.instagram_access_token) {
            document.getElementById('settingsIgAccessToken').value = s.instagram_access_token;
            if (s.instagram_user_id) {
                document.getElementById('settingsIgStatus').textContent = 'Configurado';
                document.getElementById('settingsIgStatus').style.color = 'var(--green)';
                updatePostIgStatus('Configurado');
            }
        }

        // Default captions
        if (s.post_default_caption) document.getElementById('postDefaultCaption').value = s.post_default_caption;
        if (s.post_default_hashtags) document.getElementById('postDefaultHashtags').value = s.post_default_hashtags;

        // Video editing settings
        if (s.video_template) document.getElementById('templateSelect').value = s.video_template;
        if (s.video_size) document.getElementById('videoSize').value = s.video_size;
        if (s.video_width) document.getElementById('videoWidth').value = s.video_width;
        if (s.video_offset_x !== undefined) document.getElementById('videoOffsetX').value = s.video_offset_x;
        if (s.video_offset_y !== undefined) document.getElementById('videoOffsetY').value = s.video_offset_y;
        if (s.text_watermark) document.getElementById('textMark').value = s.text_watermark;
        if (s.text_watermark_size) document.getElementById('textMarkSize').value = s.text_watermark_size;
        if (s.text_watermark_offset_x !== undefined) document.getElementById('textMarkOffsetX').value = s.text_watermark_offset_x;
        if (s.text_watermark_offset_y !== undefined) document.getElementById('textMarkOffsetY').value = s.text_watermark_offset_y;
        if (s.delogo_x !== undefined) document.getElementById('delogoX').value = s.delogo_x;
        if (s.delogo_y !== undefined) document.getElementById('delogoY').value = s.delogo_y;
        if (s.delogo_width !== undefined) document.getElementById('delogoWidth').value = s.delogo_width;
        if (s.delogo_height !== undefined) document.getElementById('delogoHeight').value = s.delogo_height;
        if (s.max_duration) document.getElementById('maxDuration').value = s.max_duration;

        // Checkboxes
        if (s.apply_watermark !== undefined) document.getElementById('applyLogo').checked = s.apply_watermark === true || s.apply_watermark === 'true';
        if (s.apply_text_watermark !== undefined) document.getElementById('applyTextMark').checked = s.apply_text_watermark === true || s.apply_text_watermark === 'true';
        if (s.remove_center_watermark !== undefined) document.getElementById('removeWatermark').checked = s.remove_center_watermark === true || s.remove_center_watermark === 'true';

        // Background and logo images
        if (s.background_image) {
            STATE.uploadedBgImage = { server_path: s.background_image };
            loadBgImage(s.background_image);
        }
        if (s.logo_image) {
            STATE.uploadedLogoImage = { server_path: s.logo_image };
        }
    } catch {}
}

async function saveSettingsToServer() {
    try {
        await api('/api/settings', {
            method: 'PUT',
            body: JSON.stringify({
                // AI provider
                ai_provider: g('aiProvider'),
                // Groq settings
                groq_api_key: g('settingsGroqKey'),
                groq_model: g('settingsGroqModel'),
                // Gemini settings
                ai_gemini_key: g('settingsGeminiKey'),
                ai_gemini_model: g('settingsGeminiModel') || 'gemini-2.0-flash',
                // Instagram settings
                instagram_user_id: g('settingsIgUserId'),
                instagram_access_token: g('settingsIgAccessToken'),
                // Default captions
                post_default_caption: g('postDefaultCaption'),
                post_default_hashtags: g('postDefaultHashtags'),
                // Video editing settings
                video_template: g('templateSelect'),
                video_size: +g('videoSize') || 100,
                video_width: +g('videoWidth') || 100,
                video_offset_x: +g('videoOffsetX') || 0,
                video_offset_y: +g('videoOffsetY') || 0,
                apply_watermark: cb('applyLogo'),
                apply_text_watermark: cb('applyTextMark'),
                text_watermark: g('textMark'),
                text_watermark_size: +g('textMarkSize') || 76,
                text_watermark_offset_x: +g('textMarkOffsetX') || 0,
                text_watermark_offset_y: +g('textMarkOffsetY') || 0,
                remove_center_watermark: cb('removeWatermark'),
                delogo_x: +g('delogoX') || 190,
                delogo_y: +g('delogoY') || 860,
                delogo_width: +g('delogoWidth') || 700,
                delogo_height: +g('delogoHeight') || 160,
                max_duration: g('maxDuration'),
                // Image paths
                background_image: STATE.uploadedBgImage ? STATE.uploadedBgImage.server_path : '',
                logo_image: STATE.uploadedLogoImage ? STATE.uploadedLogoImage.server_path : '',
            }),
        });
    } catch {}
}

setInterval(saveSettingsToServer, 30000);

async function loadQueueStats() {
    try {
        const d = await api('/api/posts/stats/summary');
        document.getElementById('queueTotal').textContent = d.total || '0';
        const bs = d.by_status || {};
        document.getElementById('queuePendente').textContent = bs['PENDENTE'] || '0';
        document.getElementById('queueAgendado').textContent = bs['AGENDADO'] || '0';
        document.getElementById('queuePublicado').textContent = bs['PUBLICADO'] || '0';
        document.getElementById('queueErro').textContent = bs['ERRO'] || '0';
    } catch {}
}

async function loadDashboardStats() {
    try {
        const d = await api('/api/posts/stats/summary');
        const bs = d.by_status || {};
        document.getElementById('dashTotalCount').textContent = d.total || '0';
        document.getElementById('dashPendenteCount').textContent = bs['PENDENTE'] || '0';
        document.getElementById('dashAgendadoCount').textContent = bs['AGENDADO'] || '0';
        document.getElementById('dashPublicadoCount').textContent = bs['PUBLICADO'] || '0';
        document.getElementById('dashErroCount').textContent = bs['ERRO'] || '0';
    } catch {}
}

// ─── Scheduler ───────────────────────────────────────────────────────────────
async function loadSchedulerStatus() {
    try {
        const d = await api('/api/posts/scheduler/status');
        const el = document.getElementById('schedulerStatus');
        if (el) {
            el.textContent = d.running ? 'Rodando' : 'Parado';
            el.style.color = d.running ? 'var(--green)' : 'var(--text-dim)';
        }
    } catch {}
}

async function schedulerStart() {
    try {
        await api('/api/posts/scheduler/start', { method: 'POST' });
        toast('Scheduler iniciado!', 'success');
        loadSchedulerStatus();
    } catch (err) { toast('Erro: ' + err.message, 'error'); }
}

async function schedulerStop() {
    try {
        await api('/api/posts/scheduler/stop', { method: 'POST' });
        toast('Scheduler parado.', 'info');
        loadSchedulerStatus();
    } catch (err) { toast('Erro: ' + err.message, 'error'); }
}

// ─── Worker Logs ─────────────────────────────────────────────────────────────
async function loadWorkerLogs() {
    const section = document.getElementById('workerLogsSection');
    const box = document.getElementById('workerLogsBox');
    section.style.display = 'block';
    box.innerHTML = '<span class="log-placeholder">Carregando...</span>';
    try {
        const logs = await api('/api/posts/logs?limit=100');
        if (!logs.length) { box.innerHTML = '<span class="log-placeholder">Nenhum log encontrado.</span>'; return; }
        box.innerHTML = logs.map(l => {
            const time = l.created_at || '';
            const msg = l.message || l.level || JSON.stringify(l);
            const cls = (l.level || '').toLowerCase();
            return `<div class="log-entry ${cls}">[${time}] ${msg}</div>`;
        }).join('');
    } catch { box.innerHTML = '<span class="log-placeholder">Erro ao carregar logs.</span>'; }
}

// ─── Batch History ───────────────────────────────────────────────────────────
async function loadBatchHistory() {
    const section = document.getElementById('batchHistorySection');
    const list = document.getElementById('batchHistoryList');
    section.style.display = 'block';
    list.innerHTML = '<span class="log-placeholder">Carregando...</span>';
    try {
        const batches = await api('/api/posts/batch-history?limit=20');
        if (!batches.length) { list.innerHTML = '<span class="log-placeholder">Nenhum histórico.</span>'; return; }
        list.innerHTML = batches.map(b => {
            const time = b.created_at || '';
            return `<div class="queue-item">
                <span class="queue-item-name">[${time}] Upload: ${b.upload_count || 0} | Processado: ${b.process_count || 0} | Sucesso: ${b.success_count || 0} | Erro: ${b.fail_count || 0}</span>
            </div>`;
        }).join('');
    } catch { list.innerHTML = '<span class="log-placeholder">Erro ao carregar histórico.</span>'; }
}

// ─── Duplicate Caption ──────────────────────────────────────────────────────
function duplicateCaption() {
    const src = document.getElementById('postCaption');
    const dst = document.getElementById('contentCaption');
    if (src && dst) {
        dst.value = src.value;
        toast('Legenda duplicada para aba Conteúdo!', 'success');
    }
}

function refreshAll() {
    loadPostQueue(); loadOutputVideos(); loadQueueStats(); loadSchedulerStatus();
    if (STATE.uploadedVideos.length) refreshPreview(STATE.uploadedVideos[0].server_path);
    toast('Dados recarregados!', 'success');
}

// ═══════════════════════════════════════════════════════════════════════════════
// PRODUCT SEARCH (v2.4)
// ═══════════════════════════════════════════════════════════════════════════════

// State
let STATE_PRODUCT = {
    lastResults: [],           // last search results
    selectedProductIdx: null,  // selected result index
    linkedProducts: [],        // products linked to posts
};

function toggleSourceBtn() {
    const ml = cb('searchML');
    const shopee = cb('searchShopee');
    const btn = document.querySelector('#tab-products .btn-primary');
    if (btn) {
        btn.disabled = !ml && !shopee;
        btn.title = (!ml && !shopee) ? 'Selecione pelo menos uma fonte' : '';
    }
}

// ─── Search Products ─────────────────────────────────────────────────────────
async function searchProducts() {
    const query = g('productSearchQuery').trim();
    if (!query) { toast('Digite um termo de busca.', 'warning'); return; }

    const sources = [];
    if (cb('searchML')) sources.push('mercadolivre');
    if (cb('searchShopee')) sources.push('shopee');
    if (!sources.length) { toast('Selecione ao menos uma fonte (ML ou Shopee).', 'warning'); return; }

    const limit = parseInt(g('productSearchLimit')) || 10;
    const log = document.getElementById('productSearchLog');
    log.innerHTML = '';
    logLine(log, `Buscando por "${query}" em ${sources.join(' + ')}...`, 'info');

    const btn = document.querySelector('#tab-products .btn-primary');
    if (btn) { btn.disabled = true; btn.textContent = '⏳ Buscando...'; }

    try {
        const d = await api('/api/products/search', {
            method: 'POST',
            body: JSON.stringify({ query, sources, limit }),
        });

        STATE_PRODUCT.lastResults = [];
        STATE_PRODUCT.selectedProductIdx = null;

        // Aggregate all products
        for (const [source, result] of Object.entries(d.results || {})) {
            if (result.success && result.products) {
                result.products.forEach(p => {
                    STATE_PRODUCT.lastResults.push({ ...p, _sourceLabel: source === 'mercadolivre' ? 'Mercado Livre' : 'Shopee' });
                });
            }
        }

        logLine(log, `Encontrados ${STATE_PRODUCT.lastResults.length} produto(s).`, 'success');
        renderProductResults(STATE_PRODUCT.lastResults);
        updateProductPostSelect();

        // Show errors
        if (d.errors && d.errors.length) {
            d.errors.forEach(e => logLine(log, `⚠️ ${e}`, 'warning'));
        }
    } catch (err) {
        logLine(log, `Erro: ${err.message}`, 'error');
        toast('Erro na busca: ' + err.message, 'error');
    } finally {
        if (btn) { btn.disabled = false; btn.textContent = '🔍 Buscar'; }
    }
}

// ─── Render Product Results ──────────────────────────────────────────────────
function renderProductResults(products) {
    const container = document.getElementById('productResults');
    const count = document.getElementById('productResultCount');
    count.textContent = `${products.length} produto(s)`;

    if (!products.length) {
        container.innerHTML = '<div class="queue-placeholder"><span class="placeholder-icon">🔍</span>Nenhum produto encontrado. Tente outro termo de busca.</div>';
        return;
    }

    container.innerHTML = products.map((p, idx) => {
        const selected = STATE_PRODUCT.selectedProductIdx === idx;
        const priceStr = p.price > 0 ? `R$ ${p.price.toFixed(2)}` : '—';
        const sourceIcon = p._sourceLabel === 'Mercado Livre' ? '📦' : '🛍️';

        return `<div class="product-item ${selected ? 'selected' : ''}" onclick="selectProductResult(${idx})">
            <div class="product-item-thumb">
                ${p.thumbnail_url
                    ? `<img src="${p.thumbnail_url}" alt="${p.title}" loading="lazy" onerror="this.style.display='none';this.nextElementSibling.style.display='flex'">
                       <div class="product-item-thumb-fallback" style="display:none;">📷</div>`
                    : '<div class="product-item-thumb-fallback">📷</div>'
                }
            </div>
            <div class="product-item-info">
                <div class="product-item-title">${escapeHtml(p.title)}</div>
                <div class="product-item-meta">
                    <span class="product-item-price">${priceStr}</span>
                    <span class="product-item-source">${sourceIcon} ${p._sourceLabel}</span>
                    ${p.store_name ? `<span class="product-item-store">🏪 ${escapeHtml(p.store_name)}</span>` : ''}
                </div>
                <div class="product-item-links">
                    ${p.permalink ? `<a href="${p.permalink}" target="_blank" class="product-item-link">🔗 Ver original</a>` : ''}
                </div>
            </div>
            <div class="product-item-select">
                <div class="radio-btn ${selected ? 'checked' : ''}"></div>
            </div>
        </div>`;
    }).join('');
}

function selectProductResult(idx) {
    const prev = STATE_PRODUCT.selectedProductIdx;
    STATE_PRODUCT.selectedProductIdx = idx;
    const p = STATE_PRODUCT.lastResults[idx];
    if (!p) return;

    // Update DOM directly without re-rendering all results
    const container = document.getElementById('productResults');
    const items = container.querySelectorAll('.product-item');
    if (items.length === STATE_PRODUCT.lastResults.length) {
        if (prev !== null && prev >= 0 && prev < items.length) {
            items[prev].classList.remove('selected');
            const radio = items[prev].querySelector('.radio-btn');
            if (radio) radio.classList.remove('checked');
        }
        if (idx >= 0 && idx < items.length) {
            items[idx].classList.add('selected');
            const radio = items[idx].querySelector('.radio-btn');
            if (radio) radio.classList.add('checked');
        }
    } else {
        // Fallback: re-render if DOM doesn't match
        renderProductResults(STATE_PRODUCT.lastResults);
    }

    // Show selected product info
    const info = document.getElementById('selectedProductInfo');
    info.innerHTML = `<strong>${escapeHtml(p.title)}</strong><br>
        R$ ${p.price.toFixed(2)} — ${p._sourceLabel}<br>
        ${p.permalink ? `<a href="${p.permalink}" target="_blank" style="color:var(--accent);font-size:11px;">🔗 Abrir link</a>` : ''}`;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text || '';
    return div.innerHTML;
}

// ─── Update Post Select ─────────────────────────────────────────────────────
async function updateProductPostSelect() {
    try {
        const posts = await api('/api/posts');
        const sel = document.getElementById('productPostSelect');
        sel.innerHTML = '<option value="">Selecione um post...</option>';
        posts.forEach(post => {
            const name = post.video_path?.split(/[/\\\\]/).pop() || 'video';
            const status = post.status || '';
            const opt = document.createElement('option');
            opt.value = post.id;
            opt.textContent = `${name} [${status}]`;
            sel.appendChild(opt);
        });
    } catch {}
}

// ─── Associate Product with Post ────────────────────────────────────────────
async function associateProduct() {
    const postId = g('productPostSelect');
    if (!postId) { toast('Selecione um post primeiro.', 'warning'); return; }
    if (STATE_PRODUCT.selectedProductIdx === null) { toast('Selecione um produto primeiro.', 'warning'); return; }

    const p = STATE_PRODUCT.lastResults[STATE_PRODUCT.selectedProductIdx];
    if (!p) { toast('Produto inválido.', 'error'); return; }

    // Generate affiliate link
    const mlId = g('mlAffiliateId');
    const shopeeId = g('shopeeAffiliateId');
    const subId = g('shopeeSubId');

    let affiliateUrl = p.permalink;
    if (p.source === 'mercadolivre' && mlId) {
        try {
            const d = await api('/api/products/affiliate-link', {
                method: 'POST',
                body: JSON.stringify({
                    source: 'mercadolivre',
                    product_url: p.permalink,
                    ml_affiliate_id: mlId,
                }),
            });
            affiliateUrl = d.affiliate_url;
        } catch {}
    } else if (p.source === 'shopee' && shopeeId) {
        try {
            const d = await api('/api/products/affiliate-link', {
                method: 'POST',
                body: JSON.stringify({
                    source: 'shopee',
                    product_url: p.permalink,
                    shopee_affiliate_id: shopeeId,
                    shopee_sub_id: subId,
                }),
            });
            affiliateUrl = d.affiliate_url;
        } catch {}
    }

    const log = document.getElementById('productAssociateLog');
    log.innerHTML = '';
    logLine(log, `Vinculando "${p.title}" ao post...`, 'info');

    try {
        const d = await api('/api/products/associate', {
            method: 'POST',
            body: JSON.stringify({
                post_id: postId,
                source: p.source,
                product_id: p.product_id,
                title: p.title,
                price: p.price,
                thumbnail_url: p.thumbnail_url,
                permalink: p.permalink,
                affiliate_url: affiliateUrl,
                store_name: p.store_name,
                store_id: p.store_id || '',
                query_used: g('productSearchQuery'),
            }),
        });

        logLine(log, `✅ Produto vinculado com sucesso!`, 'success');
        toast(`Produto vinculado: ${p.title}`, 'success');

        // Update the selected post's content fields
        try {
            await api(`/api/posts/${postId}`, {
                method: 'PUT',
                body: JSON.stringify({
                    product_query: g('productSearchQuery'),
                    affiliate_link: affiliateUrl,
                    product_keywords: p.title,
                }),
            });
        } catch {}

        loadLinkedProducts();
    } catch (err) {
        logLine(log, `❌ ${err.message}`, 'error');
        toast('Erro ao vincular: ' + err.message, 'error');
    }
}

// ─── Load Linked Products ───────────────────────────────────────────────────
async function loadLinkedProducts() {
    try {
        const products = await api('/api/products');
        STATE_PRODUCT.linkedProducts = products;
        renderLinkedProducts(products);
    } catch {}
}

function renderLinkedProducts(products) {
    const container = document.getElementById('productsLinked');
    if (!products?.length) {
        container.innerHTML = '<div class="queue-placeholder"><span class="placeholder-icon">📦</span>Nenhum produto vinculado ainda.</div>';
        return;
    }

    container.innerHTML = products.map(p => {
        const src = p.source === 'mercadolivre' ? '📦 ML' : '🛍️ Shopee';
        const priceStr = p.price > 0 ? `R$ ${parseFloat(p.price).toFixed(2)}` : '—';
        const sel = p.selected ? '⭐ ' : '';

        return `<div class="product-linked-item ${p.selected ? 'selected' : ''}">
            <div class="product-linked-thumb">
                ${p.thumbnail_url
                    ? `<img src="${p.thumbnail_url}" alt="" loading="lazy" onerror="this.style.display='none'">`
                    : '<span class="product-item-thumb-fallback" style="width:40px;height:40px;font-size:16px;">📷</span>'
                }
            </div>
            <div class="product-linked-info">
                <div class="product-linked-title">${sel}${escapeHtml(p.title)}</div>
                <div class="product-linked-meta">
                    ${priceStr} — ${src}
                    ${p.permalink ? `<a href="${p.permalink}" target="_blank" style="color:var(--accent);font-size:11px;margin-left:8px;">🔗</a>` : ''}
                    ${p.affiliate_url ? `<a href="${p.affiliate_url}" target="_blank" style="color:var(--green);font-size:11px;margin-left:4px;">🔗 Afiliado</a>` : ''}
                </div>
            </div>
            <button class="btn btn-sm btn-ghost" onclick="deleteLinkedProduct('${p.id}')" title="Remover">✕</button>
        </div>`;
    }).join('');
}

async function deleteLinkedProduct(prodId) {
    if (!confirm('Remover este produto?')) return;
    try {
        await api(`/api/products/${prodId}`, { method: 'DELETE' });
        toast('Produto removido.', 'info');
        loadLinkedProducts();
    } catch { toast('Erro ao remover.', 'error'); }
}

// ─── Affiliate IDs ──────────────────────────────────────────────────────────
async function saveAffiliateIds() {
    const ml = g('mlAffiliateId');
    const shopee = g('shopeeAffiliateId');
    const sub = g('shopeeSubId');

    try {
        await api('/api/settings', {
            method: 'PUT',
            body: JSON.stringify({
                ml_affiliate_id: ml,
                shopee_affiliate_id: shopee,
                shopee_sub_id: sub,
            }),
        });
        toast('IDs de afiliado salvos!', 'success');
    } catch { toast('Erro ao salvar.', 'error'); }
}

async function loadAffiliateIds() {
    try {
        const d = await api('/api/settings');
        const s = d.settings || {};
        if (s.ml_affiliate_id) document.getElementById('mlAffiliateId').value = s.ml_affiliate_id;
        if (s.shopee_affiliate_id) document.getElementById('shopeeAffiliateId').value = s.shopee_affiliate_id;
        if (s.shopee_sub_id) document.getElementById('shopeeSubId').value = s.shopee_sub_id;
    } catch {}
}

// ─── Collapse ────────────────────────────────────────────────────────────────
function toggleCollapse(btn) {
    const body = btn.nextElementSibling;
    body.classList.toggle('open');
    if (body.classList.contains('open')) {
        btn.textContent = btn.textContent.replace('\u25BC', '\u25B2');
    } else {
        btn.textContent = btn.textContent.replace('\u25B2', '\u25BC');
    }
}
