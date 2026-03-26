// @ts-nocheck
'use strict';

(function () {
    const vscode = acquireVsCodeApi();

    // ── DOM refs ──
    const chatArea = document.getElementById('chatArea');
    const chatInput = document.getElementById('chatInput');
    const sendBtn = document.getElementById('sendBtn');
    const welcomeState = document.getElementById('welcomeState');

    const statusDot = document.getElementById('statusDot');
    const statusLabel = document.getElementById('statusLabel');

    const activeModelName = document.getElementById('activeModelName');
    const changeModelBtn = document.getElementById('changeModelBtn');
    const modelPicker = document.getElementById('modelPicker');
    const closePickerBtn = document.getElementById('closePickerBtn');
    const pickerTiers = document.getElementById('pickerTiers');
    const loadSelectedBtn = document.getElementById('loadSelectedBtn');
    const downloadSelectedBtn = document.getElementById('downloadSelectedBtn');
    const downloadProgressWrap = document.getElementById('downloadProgressWrap');
    const downloadProgressLabel = document.getElementById('downloadProgressLabel');
    const downloadProgressBar = document.getElementById('downloadProgressBar');

    const adapterBadgeRow = document.getElementById('adapterBadgeRow');
    const activeAdapterName = document.getElementById('activeAdapterName');
    const removeAdapterBtn = document.getElementById('removeAdapterBtn');
    const adapterSection = document.getElementById('adapterSection');
    const adapterList = document.getElementById('adapterList');

    const indexBtn = document.getElementById('indexBtn');
    const fineTuneBtn = document.getElementById('fineTuneBtn');
    const clearBtn = document.getElementById('clearBtn');
    const codeReviewBtn = document.getElementById('codeReviewBtn');

    const finetunePanelEl = document.getElementById('finetunePanelEl');
    const closeFinetuneBtn = document.getElementById('closeFinetuneBtn');
    const ftModelSelect = document.getElementById('ftModelSelect');
    const ftEpochs = document.getElementById('ftEpochs');
    const startFtBtn = document.getElementById('startFtBtn');
    const ftProgress = document.getElementById('ftProgress');
    const ftProgressMsg = document.getElementById('ftProgressMsg');
    const ftProgressBar = document.getElementById('ftProgressBar');
    const ftStats = document.getElementById('ftStats');
    const ftResult = document.getElementById('ftResult');

    const codeReviewPanel = document.getElementById('codeReviewPanel');
    const closeReviewBtn = document.getElementById('closeReviewBtn');
    const startReviewBtn = document.getElementById('startReviewBtn');

    const agentTraceBar = document.getElementById('agentTraceBar');
    const agentTraceText = document.getElementById('agentTraceText');

    // ── State ──
    let models = [];
    let adapters = [];
    let selectedModelId = null;
    let selectedAdapterId = null;
    let conversationHistory = [];
    let isLoading = false;
    let ftPolling = null;
    let downloadPolling = {};

    // Restore state
    const prev = vscode.getState() || {};
    conversationHistory = prev.conversationHistory || [];
    if (conversationHistory.length > 0) {
        welcomeState.style.display = 'none';
        conversationHistory.forEach(m => renderMessage(m.role, m.content, m.extra || {}));
    }

    vscode.postMessage({ type: 'getModels' });
    vscode.postMessage({ type: 'getAdapters' });

    // ════════════════════════════════════════════
    //  MODEL PICKER
    // ════════════════════════════════════════════

    changeModelBtn.addEventListener('click', () => {
        const open = modelPicker.style.display !== 'none';
        modelPicker.style.display = open ? 'none' : 'block';
        if (!open) renderPicker();
    });

    closePickerBtn.addEventListener('click', () => { modelPicker.style.display = 'none'; });

    function renderPicker() {
        pickerTiers.innerHTML = '';
        const tierOrder = ['ultralight', 'light', 'balanced', 'powerful', 'finetune-base'];
        const tierLabels = {
            ultralight: '⚡ Ультралёгкие (CPU)',
            light: '🟢 Лёгкие (3–4 GB)',
            balanced: '🔵 Сбалансированные (8 GB)',
            powerful: '🔥 Мощные (16 GB)',
            'finetune-base': '🏗️ Базовые для дообучения',
        };

        tierOrder.forEach(tier => {
            const group = models.filter(m => m.tier === tier);
            if (!group.length) return;

            const tierDiv = document.createElement('div');
            tierDiv.className = 'tier-group';
            tierDiv.innerHTML = `<div class="tier-label">${tierLabels[tier] || tier}</div>`;

            group.forEach(m => {
                const opt = document.createElement('div');
                opt.className = 'model-option' + (m.id === selectedModelId ? ' selected' : '');
                opt.dataset.id = m.id;

                const badges = [];
                if (m.downloaded) badges.push('<span class="model-badge badge-downloaded">скачана</span>');
                if (m.active) badges.push('<span class="model-badge badge-active">активна</span>');
                if (m.tier === 'finetune-base') badges.push('<span class="model-badge badge-base">base</span>');

                opt.innerHTML = `
                    <div class="model-option-radio"></div>
                    <div class="model-option-info">
                        <div class="model-option-name">${m.name}</div>
                        <div class="model-option-meta">${m.description}</div>
                    </div>
                    <div style="display:flex;flex-direction:column;align-items:flex-end;gap:2px">
                        <div class="model-ram">${m.ram_required}</div>
                        <div class="model-badges">${badges.join('')}</div>
                    </div>
                `;

                opt.addEventListener('click', () => {
                    selectedModelId = m.id;
                    document.querySelectorAll('.model-option').forEach(el => el.classList.remove('selected'));
                    opt.classList.add('selected');
                    renderAdapterSection(m.id);
                });

                tierDiv.appendChild(opt);
            });

            pickerTiers.appendChild(tierDiv);
        });

        if (selectedModelId) {
            const el = pickerTiers.querySelector(`[data-id="${selectedModelId}"]`);
            if (el) el.classList.add('selected');
        }

        renderAdapterSection(selectedModelId);
    }

    function renderAdapterSection(modelId) {
        const modelAdapters = adapters.filter(a => a.model_id === modelId);
        if (!modelAdapters.length) {
            adapterSection.style.display = 'none';
            return;
        }
        adapterSection.style.display = 'block';
        adapterList.innerHTML = '';

        const noneOpt = document.createElement('div');
        noneOpt.className = 'adapter-option' + (!selectedAdapterId ? ' selected' : '');
        noneOpt.innerHTML = `
            <div class="model-option-radio" style="width:11px;height:11px"></div>
            <span class="adapter-option-name">Без адаптера (базовая модель)</span>
        `;
        noneOpt.addEventListener('click', () => {
            selectedAdapterId = null;
            document.querySelectorAll('.adapter-option').forEach(el => el.classList.remove('selected'));
            noneOpt.classList.add('selected');
        });
        adapterList.appendChild(noneOpt);

        modelAdapters.forEach(a => {
            const opt = document.createElement('div');
            opt.className = 'adapter-option' + (a.id === selectedAdapterId ? ' selected' : '');
            opt.innerHTML = `
                <div class="model-option-radio" style="width:11px;height:11px"></div>
                <span class="adapter-option-name" title="${a.project}">${a.id}</span>
                <span class="adapter-option-meta">${a.examples} примеров</span>
            `;
            opt.addEventListener('click', () => {
                selectedAdapterId = a.id;
                document.querySelectorAll('.adapter-option').forEach(el => el.classList.remove('selected'));
                opt.classList.add('selected');
            });
            adapterList.appendChild(opt);
        });
    }

    loadSelectedBtn.addEventListener('click', () => {
        if (!selectedModelId) { addSystemMsg('Выберите модель'); return; }
        modelPicker.style.display = 'none';
        const m = models.find(x => x.id === selectedModelId);
        const label = m ? m.name : selectedModelId;
        addSystemMsg(`Загружаю ${label}…${selectedAdapterId ? ' + адаптер ' + selectedAdapterId : ''}`);
        setStatus('loading', 'Загрузка…');
        vscode.postMessage({ type: 'loadModel', modelId: selectedModelId, adapterId: selectedAdapterId || null });
    });

    downloadSelectedBtn.addEventListener('click', () => {
        if (!selectedModelId) { addSystemMsg('Выберите модель'); return; }
        const m = models.find(x => x.id === selectedModelId);
        if (m && m.downloaded) { addSystemMsg('Модель уже скачана'); return; }
        addSystemMsg(`Скачиваю ${selectedModelId}…`);
        downloadProgressWrap.style.display = 'block';
        downloadProgressBar.style.width = '0%';
        downloadProgressLabel.textContent = 'Начинаю загрузку…';
        vscode.postMessage({ type: 'startDownload', modelId: selectedModelId });

        if (downloadPolling[selectedModelId]) clearInterval(downloadPolling[selectedModelId]);
        downloadPolling[selectedModelId] = setInterval(() => {
            vscode.postMessage({ type: 'getDownloadProgress', modelId: selectedModelId });
        }, 1500);
    });

    removeAdapterBtn.addEventListener('click', () => {
        selectedAdapterId = null;
        adapterBadgeRow.style.display = 'none';
        addSystemMsg('Адаптер убран. Перезагрузите модель для использования базовых весов.');
    });

    // ════════════════════════════════════════════
    //  CUSTOM MODEL
    // ════════════════════════════════════════════

    const customModelInput = document.getElementById('customModelInput');
    const customModelName = document.getElementById('customModelName');
    const customModelQuant = document.getElementById('customModelQuant');
    const loadCustomModelBtn = document.getElementById('loadCustomModelBtn');
    const downloadCustomModelBtn = document.getElementById('downloadCustomModelBtn');

    loadCustomModelBtn.addEventListener('click', () => {
        const repo = customModelInput.value.trim();
        if (!repo) { addSystemMsg('Введите путь или репозиторий модели'); return; }
        const name = customModelName.value.trim() || repo.split('/').pop();
        const quant = customModelQuant.value;
        addSystemMsg(`Загружаю модель: ${name}...`);
        setStatus('loading', 'Загрузка...');
        modelPicker.style.display = 'none';
        vscode.postMessage({ type: 'loadCustomModel', repo, name, quantization: quant });
    });

    downloadCustomModelBtn.addEventListener('click', () => {
        const repo = customModelInput.value.trim();
        if (!repo) { addSystemMsg('Введите HuggingFace репозиторий'); return; }
        if (repo.startsWith('/') || repo.match(/^[A-Z]:\\/)) {
            addSystemMsg('Обнаружен локальный путь — используйте Загрузить вместо Скачать');
            return;
        }
        const name = customModelName.value.trim() || repo.split('/').pop();
        addSystemMsg(`Скачиваю ${repo}... Это может занять время.`);
        vscode.postMessage({ type: 'downloadCustomModel', repo, name, quantization: customModelQuant.value });
    });

    // ════════════════════════════════════════════
    //  FINE-TUNE PANEL
    // ════════════════════════════════════════════

    fineTuneBtn.addEventListener('click', () => {
        const open = finetunePanelEl.style.display !== 'none';
        finetunePanelEl.style.display = open ? 'none' : 'block';
        codeReviewPanel.style.display = 'none';
        if (!open) populateFtModelSelect();
    });

    closeFinetuneBtn.addEventListener('click', () => { finetunePanelEl.style.display = 'none'; });

    function populateFtModelSelect() {
        ftModelSelect.innerHTML = '';
        models.forEach(m => {
            const opt = document.createElement('option');
            opt.value = m.id;
            opt.textContent = m.name + (m.downloaded ? '' : ' [не скачана]');
            opt.disabled = !m.downloaded;
            if (m.active) opt.selected = true;
            ftModelSelect.appendChild(opt);
        });
    }

    startFtBtn.addEventListener('click', () => {
        const modelId = ftModelSelect.value;
        const epochs = parseInt(ftEpochs.value) || 3;
        const strategies = Array.from(document.querySelectorAll('.ft-check input:checked')).map(el => el.value);

        if (!strategies.length) { addSystemMsg('Выберите хотя бы одну стратегию обучения'); return; }

        ftProgress.style.display = 'block';
        ftResult.style.display = 'none';
        ftProgressMsg.textContent = 'Отправляю задачу дообучения…';
        ftProgressBar.style.width = '0%';
        startFtBtn.disabled = true;

        vscode.postMessage({ type: 'fineTune', modelId, epochs, strategies });

        if (ftPolling) clearInterval(ftPolling);
        ftPolling = setInterval(() => {
            vscode.postMessage({ type: 'getFtStatus' });
        }, 2000);
    });

    // ════════════════════════════════════════════
    //  CODE REVIEW (новая фича)
    // ════════════════════════════════════════════

    codeReviewBtn.addEventListener('click', () => {
        const open = codeReviewPanel.style.display !== 'none';
        codeReviewPanel.style.display = open ? 'none' : 'block';
        finetunePanelEl.style.display = 'none';
    });

    closeReviewBtn.addEventListener('click', () => { codeReviewPanel.style.display = 'none'; });

    startReviewBtn.addEventListener('click', () => {
        const focus = [];
        if (document.getElementById('rv-security').checked) focus.push('безопасность и уязвимости');
        if (document.getElementById('rv-perf').checked) focus.push('производительность и оптимизация');
        if (document.getElementById('rv-style').checked) focus.push('стиль кода и конвенции');
        if (document.getElementById('rv-bugs').checked) focus.push('баги и edge cases');
        if (document.getElementById('rv-docs').checked) focus.push('документация и комментарии');

        if (!focus.length) { addSystemMsg('Выберите хотя бы один аспект ревью'); return; }

        const prompt = `Проведи детальное code review текущего файла. Сфокусируйся на: ${focus.join(', ')}. Для каждой проблемы укажи: файл, строку (если возможно), описание проблемы и конкретное предложение по исправлению.`;

        codeReviewPanel.style.display = 'none';
        welcomeState.style.display = 'none';
        chatInput.value = prompt;
        sendMessage();
    });

    // ════════════════════════════════════════════
    //  AGENT TRACE
    // ════════════════════════════════════════════

    function showAgentTrace(trace, intent) {
        if (!trace || !trace.length) {
            agentTraceBar.style.display = 'none';
            return;
        }

        const agentIcons = {
            analyst: '🔍 Аналитик',
            coder: '💻 Кодер',
            refactor: '🔄 Рефактор',
            tester: '🧪 Тестер',
            multi: '🤝 Мультиагент',
            filter: '🚫 Фильтр',
        };

        const steps = trace.map(a => agentIcons[a] || a).join(' → ');
        agentTraceText.innerHTML = `<span style="color:var(--accent)">Агенты:</span> ${steps}`;
        agentTraceBar.style.display = 'block';

        // Скрываем через 10 секунд
        setTimeout(() => { agentTraceBar.style.display = 'none'; }, 10000);
    }

    // ════════════════════════════════════════════
    //  CHAT
    // ════════════════════════════════════════════

    sendBtn.addEventListener('click', sendMessage);
    chatInput.addEventListener('keydown', e => {
        if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
    });
    chatInput.addEventListener('input', () => {
        chatInput.style.height = 'auto';
        chatInput.style.height = Math.min(chatInput.scrollHeight, 140) + 'px';
    });

    document.querySelectorAll('.qp-chip').forEach(btn => {
        btn.addEventListener('click', () => {
            chatInput.value = btn.dataset.prompt;
            sendMessage();
        });
    });

    indexBtn.addEventListener('click', () => {
        addSystemMsg('Индексирую проект…');
        vscode.postMessage({ type: 'indexProject' });
    });

    clearBtn.addEventListener('click', () => {
        conversationHistory = [];
        chatArea.querySelectorAll('.msg, .typing-indicator').forEach(el => el.remove());
        welcomeState.style.display = '';
        agentTraceBar.style.display = 'none';
        saveState();
    });

    function sendMessage() {
        const text = chatInput.value.trim();
        if (!text || isLoading) return;
        welcomeState.style.display = 'none';

        addMessage('user', text);
        vscode.postMessage({ type: 'chat', content: text, history: conversationHistory.slice(-10) });

        chatInput.value = '';
        chatInput.style.height = 'auto';
        isLoading = true;
        sendBtn.disabled = true;
        showTyping();
    }

    function addMessage(role, content, extra) {
        extra = extra || {};
        conversationHistory.push({ role, content, extra, ts: Date.now() });
        renderMessage(role, content, extra);
        saveState();
    }

    function renderMessage(role, content, extra) {
        extra = extra || {};
        const wrapper = document.createElement('div');
        wrapper.className = `msg msg-${role}`;

        const bubble = document.createElement('div');
        bubble.className = 'msg-bubble';

        let html = '';

        if (extra.agent && role === 'assistant') {
            const labels = {
                analyst: '🔍 Аналитик',
                coder: '💻 Кодер',
                refactor: '🔄 Рефактор',
                tester: '🧪 Тестер',
                general: '🤖 Ассистент',
                multi: '🤝 Мультиагент',
                filter: '🚫 Фильтр',
            };
            const agentClass = extra.agent === 'filter' ? 'agent-general' : `agent-${extra.agent}`;
            html += `<div class="agent-tag ${agentClass}">${labels[extra.agent] || extra.agent}</div>`;
        }

        html += renderMarkdown(content);

        if (extra.code) {
            html += `<div class="code-actions">
                <button class="code-action-btn primary-action insert-btn">↳ Вставить</button>
                <button class="code-action-btn copy-btn">Копировать</button>
            </div>`;
            bubble.setAttribute('data-code', extra.code);
        }

        if (extra.references && extra.references.length) {
            html += `<div class="references">📎 ${extra.references.map(r =>
                `<a class="ref-link">${escHtml(r)}</a>`).join(', ')}</div>`;
        }

        bubble.innerHTML = html;

        // Copy buttons on code blocks
        bubble.querySelectorAll('pre').forEach(pre => {
            const btn = document.createElement('button');
            btn.className = 'copy-code-btn';
            btn.textContent = 'Копировать';
            btn.addEventListener('click', () => {
                const code = pre.querySelector('code');
                navigator.clipboard.writeText(code ? code.textContent : pre.textContent).then(() => {
                    btn.textContent = 'Скопировано!';
                    setTimeout(() => { btn.textContent = 'Копировать'; }, 2000);
                });
            });
            pre.style.position = 'relative';
            pre.appendChild(btn);
        });

        const insertBtn = bubble.querySelector('.insert-btn');
        if (insertBtn) {
            insertBtn.addEventListener('click', () => {
                vscode.postMessage({ type: 'insertCode', code: bubble.getAttribute('data-code') });
            });
        }
        const copyBtn2 = bubble.querySelector('.copy-btn');
        if (copyBtn2) {
            copyBtn2.addEventListener('click', () => {
                navigator.clipboard.writeText(bubble.getAttribute('data-code')).then(() => {
                    copyBtn2.textContent = 'Скопировано!';
                    setTimeout(() => { copyBtn2.textContent = 'Копировать'; }, 2000);
                });
            });
        }

        wrapper.appendChild(bubble);
        chatArea.appendChild(wrapper);
        chatArea.scrollTop = chatArea.scrollHeight;
    }

    function showTyping() {
        removeTyping();
        const t = document.createElement('div');
        t.className = 'typing-indicator';
        t.id = 'typing';
        t.innerHTML = '<div class="typing-dot"></div><div class="typing-dot"></div><div class="typing-dot"></div>';
        chatArea.appendChild(t);
        chatArea.scrollTop = chatArea.scrollHeight;
    }

    function removeTyping() {
        const el = document.getElementById('typing');
        if (el) el.remove();
    }

    function addSystemMsg(text) {
        const w = document.createElement('div');
        w.className = 'msg msg-system';
        const b = document.createElement('div');
        b.className = 'msg-bubble';
        b.textContent = text;
        w.appendChild(b);
        chatArea.appendChild(w);
        chatArea.scrollTop = chatArea.scrollHeight;
    }

    // ── Markdown renderer ──
    function renderMarkdown(text) {
        if (!text) return '';
        const esc = escHtml(text);
        let result = '';
        let remaining = esc;

        while (remaining.length) {
            const idx = remaining.indexOf('```');
            if (idx === -1) { result += processInline(remaining); break; }

            result += processInline(remaining.slice(0, idx));
            const after = remaining.slice(idx + 3);
            const nl = after.indexOf('\n');
            let lang = '', code = after;
            if (nl !== -1 && nl < 20) { lang = after.slice(0, nl).trim(); code = after.slice(nl + 1); }

            const end = code.indexOf('```');
            if (end === -1) { result += `<pre><code>${code}</code></pre>`; break; }

            result += `<pre><code class="language-${lang}">${code.slice(0, end)}</code></pre>`;
            remaining = code.slice(end + 3);
        }
        return result;
    }

    function processInline(text) {
        const parts = text.split('`');
        let out = '';
        parts.forEach((p, i) => { out += i % 2 === 1 ? `<code>${p}</code>` : p; });
        text = out;
        text = text.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
        text = text.replace(/\*(.+?)\*/g, '<em>$1</em>');
        text = text.replace(/^#### (.+)$/gm, '<h4>$1</h4>');
        text = text.replace(/^### (.+)$/gm, '<h3>$1</h3>');
        text = text.replace(/^## (.+)$/gm, '<h2>$1</h2>');
        text = text.replace(/^# (.+)$/gm, '<h1>$1</h1>');
        text = text.replace(/^[-*] (.+)$/gm, '<li>$1</li>');
        text = text.replace(/(<li>.*<\/li>)+/gs, '<ul>$&</ul>');
        text = text.replace(/\n/g, '<br>');
        return text;
    }

    function escHtml(t) {
        const d = document.createElement('div');
        d.textContent = t;
        return d.innerHTML;
    }

    function setStatus(state, label) {
        statusDot.className = 'status-dot' + (state === 'online' ? ' online' : state === 'loading' ? ' loading' : '');
        statusLabel.textContent = label;
    }

    function saveState() {
        vscode.setState({ conversationHistory: conversationHistory.slice(-50) });
    }

    // ════════════════════════════════════════════
    //  MESSAGE HANDLER
    // ════════════════════════════════════════════

    window.addEventListener('message', e => {
        const msg = e.data;

        switch (msg.type) {

            case 'chatResponse':
                removeTyping();
                isLoading = false;
                sendBtn.disabled = false;
                // Показываем трейс агентов
                if (msg.agent_trace) {
                    showAgentTrace(msg.agent_trace, msg.intent);
                }
                addMessage('assistant', msg.content, {
                    agent: msg.agent,
                    code: msg.code,
                    references: msg.references,
                    agent_trace: msg.agent_trace,
                });
                break;

            case 'error':
                removeTyping();
                isLoading = false;
                sendBtn.disabled = false;
                addSystemMsg('⚠ ' + msg.content);
                break;

            case 'status':
                addSystemMsg(msg.content);
                break;

            case 'modelList':
                models = msg.models || [];
                const active = models.find(m => m.active);
                if (active) {
                    selectedModelId = active.id;
                    activeModelName.textContent = active.name;
                    setStatus('online', 'готов');
                } else {
                    setStatus('', 'нет модели');
                    activeModelName.textContent = 'Не загружена';
                }
                if (finetunePanelEl.style.display !== 'none') populateFtModelSelect();
                models.forEach(m => {
                    if (m.download_progress != null) {
                        downloadProgressBar.style.width = m.download_progress + '%';
                        downloadProgressLabel.textContent = `Скачивание… ${m.download_progress}%`;
                        if (m.download_progress >= 100 && downloadPolling[m.id]) {
                            clearInterval(downloadPolling[m.id]);
                            delete downloadPolling[m.id];
                            downloadProgressWrap.style.display = 'none';
                            addSystemMsg(`✅ ${m.name} скачана! Нажмите Загрузить для активации.`);
                        }
                    }
                });
                break;

            case 'adapterList':
                adapters = msg.adapters || [];
                break;

            case 'modelLoaded':
                selectedModelId = msg.modelId;
                const loadedModel = models.find(m => m.id === msg.modelId);
                activeModelName.textContent = loadedModel ? loadedModel.name : msg.modelId;
                setStatus('online', 'готов');
                if (msg.adapterId) {
                    adapterBadgeRow.style.display = 'flex';
                    activeAdapterName.textContent = msg.adapterId;
                    selectedAdapterId = msg.adapterId;
                } else {
                    adapterBadgeRow.style.display = 'none';
                    selectedAdapterId = null;
                }
                addSystemMsg(`✅ ${loadedModel ? loadedModel.name : msg.modelId} загружена${msg.adapterId ? ' + адаптер' : ''}!`);
                vscode.postMessage({ type: 'getModels' });
                break;

            case 'modelDownloaded':
                addSystemMsg(`✅ ${msg.modelId} скачана! Нажмите Загрузить.`);
                vscode.postMessage({ type: 'getModels' });
                break;

            case 'ftStatus':
                const s = msg.status;
                if (s.running) {
                    ftProgressMsg.textContent = s.message;
                    ftProgressBar.style.width = s.progress + '%';
                    if (s.examples_count) {
                        const bd = s.strategy_breakdown || {};
                        ftStats.textContent = `${s.examples_count} примеров | ` +
                            Object.entries(bd).map(([k,v]) => `${k}: ${v}`).join(', ');
                    }
                    if (s.epoch > 0) {
                        ftProgressMsg.textContent = `Эпоха ${s.epoch}/${s.total_epochs} — Loss: ${s.loss}`;
                    }
                } else {
                    if (ftPolling) { clearInterval(ftPolling); ftPolling = null; }
                    startFtBtn.disabled = false;
                    if (s.adapter_path) {
                        ftProgressBar.style.width = '100%';
                        ftResult.style.display = 'block';
                        ftResult.innerHTML = `✅ Дообучение завершено!<br>Адаптер: <strong>${s.adapter_path}</strong><br>Примеров: ${s.examples_count}`;
                        vscode.postMessage({ type: 'getAdapters' });
                        addSystemMsg('🎯 Дообучение завершено! Загрузите модель с новым адаптером.');
                    } else if (s.message && s.message.includes('Error')) {
                        ftResult.style.display = 'block';
                        ftResult.style.background = 'rgba(248,81,73,0.08)';
                        ftResult.style.borderColor = 'rgba(248,81,73,0.2)';
                        ftResult.style.color = 'var(--red)';
                        ftResult.textContent = '⚠ ' + s.message;
                    }
                }
                break;

            case 'downloadProgress':
                downloadProgressBar.style.width = msg.progress + '%';
                downloadProgressLabel.textContent = msg.message || `${msg.progress}%`;
                if (msg.progress >= 100) {
                    downloadProgressWrap.style.display = 'none';
                    if (downloadPolling[msg.modelId]) {
                        clearInterval(downloadPolling[msg.modelId]);
                        delete downloadPolling[msg.modelId];
                    }
                }
                break;

            case 'explain':
                if (welcomeState) welcomeState.style.display = 'none';
                chatInput.value = 'Объясни этот код подробно: что он делает, как работает и какие есть потенциальные проблемы';
                sendMessage();
                break;
        }
    });

    // Health poll every 30s
    setInterval(() => { vscode.postMessage({ type: 'getModels' }); }, 30000);

})();