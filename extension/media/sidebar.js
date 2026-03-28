// @ts-nocheck
'use strict';

(function () {
    const vscode = acquireVsCodeApi();

    // ── SVG Icon system ──
    // Compact inline SVGs (16x16) for a professional look
    const SVG = {
        search:     '<svg class="ic" viewBox="0 0 16 16"><circle cx="6.5" cy="6.5" r="5" fill="none" stroke="currentColor" stroke-width="1.5"/><line x1="10" y1="10" x2="15" y2="15" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>',
        code:       '<svg class="ic" viewBox="0 0 16 16"><polyline points="4.5,2 0.5,8 4.5,14" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/><polyline points="11.5,2 15.5,8 11.5,14" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>',
        refresh:    '<svg class="ic" viewBox="0 0 16 16"><path d="M13.5 8A5.5 5.5 0 1 1 8 2.5" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/><polyline points="10,1 13.5,2.5 12,5.5" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>',
        flask:      '<svg class="ic" viewBox="0 0 16 16"><path d="M5.5 1h5v4l3.5 9H2L5.5 5z" fill="none" stroke="currentColor" stroke-width="1.2" stroke-linejoin="round"/><line x1="4" y1="1" x2="12" y2="1" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>',
        bolt:       '<svg class="ic" viewBox="0 0 16 16"><polygon points="9,1 3,9 7.5,9 6.5,15 13,7 8.5,7" fill="currentColor"/></svg>',
        bot:        '<svg class="ic" viewBox="0 0 16 16"><rect x="2" y="4" width="12" height="9" rx="2" fill="none" stroke="currentColor" stroke-width="1.2"/><circle cx="5.5" cy="8.5" r="1.2" fill="currentColor"/><circle cx="10.5" cy="8.5" r="1.2" fill="currentColor"/><line x1="8" y1="4" x2="8" y2="1.5" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/><circle cx="8" cy="1" r="0.8" fill="currentColor"/></svg>',
        users:      '<svg class="ic" viewBox="0 0 16 16"><circle cx="6" cy="4" r="2.5" fill="none" stroke="currentColor" stroke-width="1.2"/><path d="M1 14c0-3 2.2-5 5-5s5 2 5 5" fill="none" stroke="currentColor" stroke-width="1.2"/><circle cx="11" cy="5" r="2" fill="none" stroke="currentColor" stroke-width="1"/><path d="M12 9c2 0.5 3 2.3 3 5" fill="none" stroke="currentColor" stroke-width="1"/></svg>',
        block:      '<svg class="ic" viewBox="0 0 16 16"><circle cx="8" cy="8" r="6.5" fill="none" stroke="currentColor" stroke-width="1.5"/><line x1="3.4" y1="3.4" x2="12.6" y2="12.6" stroke="currentColor" stroke-width="1.5"/></svg>',
        file:       '<svg class="ic" viewBox="0 0 16 16"><path d="M4 1h5.5L13 4.5V14a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V2a1 1 0 0 1 1-1z" fill="none" stroke="currentColor" stroke-width="1.2"/><polyline points="9,1 9,5 13,5" fill="none" stroke="currentColor" stroke-width="1.2"/></svg>',
        fileEdit:   '<svg class="ic" viewBox="0 0 16 16"><path d="M4 1h5.5L13 4.5V9" fill="none" stroke="currentColor" stroke-width="1.2"/><polyline points="9,1 9,5 13,5" fill="none" stroke="currentColor" stroke-width="1.2"/><path d="M3 14V2a1 1 0 0 1 1-1" fill="none" stroke="currentColor" stroke-width="1.2"/><path d="M9 15l-2 .5.5-2L12.3 8.7a1 1 0 0 1 1.4 0l.6.6a1 1 0 0 1 0 1.4z" fill="none" stroke="currentColor" stroke-width="1.2"/></svg>',
        terminal:   '<svg class="ic" viewBox="0 0 16 16"><rect x="1" y="2" width="14" height="12" rx="1.5" fill="none" stroke="currentColor" stroke-width="1.2"/><polyline points="4,6 7,8.5 4,11" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/><line x1="8" y1="11" x2="12" y2="11" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>',
        folder:     '<svg class="ic" viewBox="0 0 16 16"><path d="M1.5 3A1.5 1.5 0 0 1 3 1.5h3l2 2h5A1.5 1.5 0 0 1 14.5 5v7.5A1.5 1.5 0 0 1 13 14H3A1.5 1.5 0 0 1 1.5 12.5z" fill="none" stroke="currentColor" stroke-width="1.2"/></svg>',
        think:      '<svg class="ic" viewBox="0 0 16 16"><path d="M2 2h12a1 1 0 0 1 1 1v7a1 1 0 0 1-1 1H5l-3 3V3a1 1 0 0 1 1-1z" fill="none" stroke="currentColor" stroke-width="1.2"/><circle cx="5" cy="7" r="0.8" fill="currentColor"/><circle cx="8" cy="7" r="0.8" fill="currentColor"/><circle cx="11" cy="7" r="0.8" fill="currentColor"/></svg>',
        check:      '<svg class="ic" viewBox="0 0 16 16"><polyline points="2,8.5 6,12.5 14,3.5" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>',
        warn:       '<svg class="ic" viewBox="0 0 16 16"><path d="M8 1L1 14h14z" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linejoin="round"/><line x1="8" y1="6" x2="8" y2="10" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/><circle cx="8" cy="12" r="0.7" fill="currentColor"/></svg>',
        clip:       '<svg class="ic" viewBox="0 0 16 16"><path d="M10 2a3 3 0 0 0-3 3v6a2 2 0 0 0 4 0V5.5" fill="none" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/><path d="M11 5.5V11a4 4 0 0 1-8 0V5a3 3 0 0 1 6 0" fill="none" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/></svg>',
        gear:       '<svg class="ic" viewBox="0 0 16 16"><circle cx="8" cy="8" r="2.5" fill="none" stroke="currentColor" stroke-width="1.2"/><path d="M8 0.5l1.2 2.1 2.3-.4.4 2.3 2.1 1.2-1.2 2 1.2 2-2.1 1.2-.4 2.3-2.3-.4L8 15.5l-1.2-2.1-2.3.4-.4-2.3-2.1-1.2 1.2-2-1.2-2 2.1-1.2.4-2.3 2.3.4z" fill="none" stroke="currentColor" stroke-width="0.8"/></svg>',
        tool:       '<svg class="ic" viewBox="0 0 16 16"><path d="M10.5 1.5a3.5 3.5 0 0 0-3.2 4.8L2 11.5V14h2.5l5.2-5.3a3.5 3.5 0 0 0 4.8-3.2 3.5 3.5 0 0 0-4-4z" fill="none" stroke="currentColor" stroke-width="1.2" stroke-linejoin="round"/></svg>',
    };

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

    // Streaming state
    let streamProgressEl = null;

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

        const customModels = models.filter(m => m.tags && m.tags.includes('custom'));
        if (customModels.length) {
            tierOrder.push('custom');
            tierLabels['custom'] = '🧩 Загруженные пользователем';
        }

        tierOrder.forEach(tier => {
            let group;
            if (tier === 'custom') {
                group = customModels;
            } else {
                group = models.filter(m => m.tier === tier && !(m.tags && m.tags.includes('custom')));
            }
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
                if (m.tags && m.tags.includes('custom')) badges.push('<span class="model-badge badge-custom">custom</span>');

                opt.innerHTML = `
                    <div class="model-option-radio"></div>
                    <div class="model-option-info">
                        <div class="model-option-name">${m.name}</div>
                        <div class="model-option-meta">${m.description || ''}</div>
                    </div>
                    <div style="display:flex;flex-direction:column;align-items:flex-end;gap:2px">
                        <div class="model-ram">${m.ram_required || ''}</div>
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
            const dateStr = a.created_at ? new Date(a.created_at).toLocaleDateString() : '';
            opt.innerHTML = `
                <div class="model-option-radio" style="width:11px;height:11px"></div>
                <span class="adapter-option-name" title="${a.project}">${a.id}</span>
                <span class="adapter-option-meta">${a.examples} примеров ${dateStr ? '| ' + dateStr : ''}</span>
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
        addSystemMsg('Адаптер убран. Перезагрузите модель.');
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

        const lr = parseFloat(document.getElementById('ftLearningRate')?.value) || undefined;
        const bs = parseInt(document.getElementById('ftBatchSize')?.value) || undefined;
        const ga = parseInt(document.getElementById('ftGradAccum')?.value) || undefined;
        const loraR = parseInt(document.getElementById('ftLoraR')?.value) || undefined;
        const loraAlpha = parseInt(document.getElementById('ftLoraAlpha')?.value) || undefined;
        const maxSeq = parseInt(document.getElementById('ftMaxSeqLen')?.value) || undefined;

        ftProgress.style.display = 'block';
        ftResult.style.display = 'none';
        ftProgressMsg.textContent = 'Отправляю задачу дообучения…';
        ftProgressBar.style.width = '0%';
        startFtBtn.disabled = true;

        vscode.postMessage({
            type: 'fineTune', modelId, epochs, strategies,
            learning_rate: lr, batch_size: bs, gradient_accumulation_steps: ga,
            lora_r: loraR, lora_alpha: loraAlpha, max_seq_length: maxSeq,
        });

        if (ftPolling) clearInterval(ftPolling);
        ftPolling = setInterval(() => {
            vscode.postMessage({ type: 'getFtStatus' });
        }, 2000);
    });

    // ════════════════════════════════════════════
    //  CODE REVIEW
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

        const prompt = `Проведи детальное code review текущего файла. Сфокусируйся на: ${focus.join(', ')}. Для каждой проблемы укажи: файл, строку (если возможно), описание проблемы и конкретное предложение по исправлению с кодом.`;

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
            analyst: SVG.search + ' Аналитик',
            coder: SVG.code + ' Кодер',
            refactor: SVG.refresh + ' Рефактор',
            tester: SVG.flask + ' Тестер',
            multi: SVG.users + ' Мульти',
            filter: SVG.block + ' Фильтр',
            react: SVG.bolt + ' ReAct',
            read_file: SVG.file,
            write_file: SVG.fileEdit,
            edit_file: SVG.fileEdit,
            run_command: SVG.terminal,
            search_code: SVG.search,
            list_files: SVG.folder,
        };
        const steps = trace.map(a => agentIcons[a] || a).join(' → ');
        agentTraceText.innerHTML = `<span style="color:var(--accent)">Агенты:</span> ${steps}`;
        agentTraceBar.style.display = 'block';
        setTimeout(() => { agentTraceBar.style.display = 'none'; }, 15000);
    }

    // ════════════════════════════════════════════
    //  STREAMING PROGRESS PANEL
    // ════════════════════════════════════════════

    function showStreamProgress(text) {
        if (!streamProgressEl) {
            streamProgressEl = document.createElement('div');
            streamProgressEl.className = 'stream-progress';
            streamProgressEl.id = 'streamProgress';
            chatArea.appendChild(streamProgressEl);
        }
        streamProgressEl.innerHTML = `
            <div class="stream-progress-inner">
                <div class="stream-progress-spinner"></div>
                <div class="stream-progress-text">${escHtml(text)}</div>
            </div>
        `;
        chatArea.scrollTop = chatArea.scrollHeight;
    }

    function addStreamThinking(text) {
        if (!streamProgressEl) showStreamProgress('Размышляю...');

        let thinkingEl = streamProgressEl.querySelector('.stream-thinking');
        if (!thinkingEl) {
            thinkingEl = document.createElement('details');
            thinkingEl.className = 'thinking-block stream-thinking';
            thinkingEl.innerHTML = `
                <summary class="thinking-summary">${SVG.think} Размышления модели (live)</summary>
                <div class="thinking-content"></div>
            `;
            streamProgressEl.appendChild(thinkingEl);
        }

        const content = thinkingEl.querySelector('.thinking-content');
        content.innerHTML = renderMarkdown(text);
        chatArea.scrollTop = chatArea.scrollHeight;
    }

    function addStreamToolCall(tool, args) {
        if (!streamProgressEl) showStreamProgress('Использую инструменты...');

        const toolEl = document.createElement('div');
        toolEl.className = 'stream-tool-call';

        const toolIcons = {
            read_file: SVG.file, write_file: SVG.fileEdit, edit_file: SVG.fileEdit,
            run_command: SVG.terminal, search_code: SVG.search, list_files: SVG.folder,
        };
        const icon = toolIcons[tool] || SVG.tool;
        const argsStr = args ? Object.entries(args).map(([k, v]) => {
            const val = typeof v === 'string' ? (v.length > 60 ? v.slice(0, 60) + '…' : v) : JSON.stringify(v);
            return `<span class="tool-arg-key">${k}</span>: ${escHtml(val)}`;
        }).join(', ') : '';

        toolEl.innerHTML = `${icon} <span class="tool-name">${tool}</span>(${argsStr})`;
        streamProgressEl.appendChild(toolEl);
        chatArea.scrollTop = chatArea.scrollHeight;
    }

    function addStreamToolResult(tool, success, output) {
        if (!streamProgressEl) return;

        const resultEl = document.createElement('div');
        resultEl.className = 'stream-tool-result ' + (success ? 'success' : 'error');
        const short = output && output.length > 200 ? output.slice(0, 200) + '…' : (output || '');
        resultEl.innerHTML = `${success ? '✓' : '✗'} ${escHtml(short)}`;
        streamProgressEl.appendChild(resultEl);
        chatArea.scrollTop = chatArea.scrollHeight;
    }

    function removeStreamProgress() {
        if (streamProgressEl) {
            streamProgressEl.remove();
            streamProgressEl = null;
        }
    }

    // ════════════════════════════════════════════
    //  CHAT
    // ════════════════════════════════════════════

    sendBtn.onclick = sendMessage;
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
        chatArea.querySelectorAll('.msg, .typing-indicator, .streaming-msg, .stream-progress').forEach(el => el.remove());
        welcomeState.style.display = '';
        agentTraceBar.style.display = 'none';
        streamProgressEl = null;
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
        _showStopButton();
        showStreamProgress('Анализирую запрос...');
    }

    function cancelRequest() {
        vscode.postMessage({ type: 'cancelRequest' });
        _resetLoadingState();
        removeStreamProgress();
        removeTyping();
        // Убираем создание cancelNote — SidebarProvider сам пришлёт chatResponse
    }

    function _showStopButton() {
        sendBtn.classList.add('stop-mode');
        sendBtn.innerHTML = SVG.block;
        sendBtn.disabled = false;
        sendBtn.title = 'Остановить генерацию';
        sendBtn.onclick = cancelRequest;
    }

    function _resetLoadingState() {
        isLoading = false;
        sendBtn.classList.remove('stop-mode');
        sendBtn.innerHTML = '<svg viewBox="0 0 20 20" fill="currentColor" width="16" height="16"><path d="M3.105 2.289a.75.75 0 00-.826.95l1.414 4.925A1.5 1.5 0 005.135 9.25h6.115a.75.75 0 010 1.5H5.135a1.5 1.5 0 00-1.442 1.086l-1.414 4.926a.75.75 0 00.826.95 28.896 28.896 0 0015.293-7.154.75.75 0 000-1.115A28.897 28.897 0 003.105 2.289z"/></svg>';
        sendBtn.disabled = false;
        sendBtn.title = 'Отправить';
        sendBtn.onclick = sendMessage;
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
                analyst: SVG.search + ' Аналитик',
                coder: SVG.code + ' Кодер',
                refactor: SVG.refresh + ' Рефактор',
                tester: SVG.flask + ' Тестер',
                general: SVG.bot + ' Ассистент',
                multi: SVG.users + ' Мультиагент',
                filter: SVG.block + ' Фильтр',
                react: SVG.bolt + ' ReAct-агент',
            };
            const agentClass = extra.agent === 'filter' ? 'agent-general' : `agent-${extra.agent}`;
            html += `<div class="agent-tag ${agentClass}">${labels[extra.agent] || extra.agent}</div>`;
        }

        // Thinking block (collapsible)
        if (extra.thinking) {
            html += `<details class="thinking-block">
                <summary class="thinking-summary">${SVG.think} Размышления модели</summary>
                <div class="thinking-content">${renderMarkdown(extra.thinking)}</div>
            </details>`;
        }

        html += renderMarkdown(content);

        // File changes section
        if (extra.file_changes && extra.file_changes.length) {
            html += '<div class="file-changes-section">';
            html += '<div class="file-changes-header">' + SVG.folder + ' Изменения файлов:</div>';
            extra.file_changes.forEach((fc, idx) => {
                const icon = fc.action === 'write' ? SVG.fileEdit + ' Создан' : SVG.fileEdit + ' Изменён';
                html += `<div class="file-change-item">
                    <span class="file-change-icon">${icon}</span>
                    <a class="file-change-path" data-file="${escHtml(fc.file)}">${escHtml(fc.file)}</a>
                </div>`;
            });
            html += '</div>';
        }

        // ── Proposed Changes section ──
        if (extra.proposed_changes && extra.proposed_changes.length) {
            html += '<div class="proposed-changes-section">';
            html += '<div class="proposed-changes-header">' + SVG.fileEdit + ' Предложенные изменения (' + extra.proposed_changes.length + ')</div>';

            if (extra.proposed_changes.length > 1) {
                html += '<button class="proposed-apply-all-btn">' + SVG.check + ' Применить все</button>';
            }

            extra.proposed_changes.forEach((pc, idx) => {
                const fileName = (pc.file || '').replace(/\\/g, '/').split('/').pop() || pc.file;
                const actionLabels = {
                    replace: '↻ Заменить',
                    add: '+ Добавить',
                    delete: '✕ Удалить',
                    create: '★ Создать',
                };
                const actionClasses = {
                    replace: 'action-replace',
                    add: 'action-add',
                    delete: 'action-delete',
                    create: 'action-create',
                };
                const lineInfo = pc.lineStart
                    ? (pc.lineEnd ? ` :${pc.lineStart}-${pc.lineEnd}` : ` :${pc.lineStart}`)
                    : '';

                html += `<div class="proposed-change-card" data-idx="${idx}">
                    <div class="proposed-change-info">
                        <span class="proposed-action-badge ${actionClasses[pc.action] || ''}">${actionLabels[pc.action] || pc.action}</span>
                        <span class="proposed-file-path">${escHtml(pc.file)}${lineInfo}</span>
                    </div>
                    <div class="proposed-change-actions">
                        <button class="proposed-diff-btn" data-idx="${idx}" title="Показать diff">${SVG.search} Diff</button>
                        <button class="proposed-apply-btn" data-idx="${idx}" title="Применить изменение">${SVG.check} Применить</button>
                    </div>
                </div>`;
            });
            html += '</div>';
        }

        // Store code for reference (no global button)
        if (extra.code) {
            bubble.setAttribute('data-code', extra.code);
        }

        if (extra.references && extra.references.length) {
            const uniqueRefs = [...new Set(extra.references)];
            html += `<div class="references">${SVG.clip} ${uniqueRefs.map(r =>
                `<a class="ref-link" data-file="${escHtml(r)}">${escHtml(r)}</a>`).join(', ')}</div>`;
        }

        bubble.innerHTML = html;

        // ── Per-code-block action buttons ──
        bubble.querySelectorAll('pre').forEach(pre => {
            // Read file/line/lineEnd/action from data attributes set by renderMarkdown()
            let blockFile = pre.dataset.file || null;
            let blockLine = pre.dataset.line ? parseInt(pre.dataset.line) : null;
            let blockLineEnd = pre.dataset.lineEnd ? parseInt(pre.dataset.lineEnd) : null;
            let blockAction = pre.dataset.action || null; // 'replace' | 'add' | 'delete'
            const blockLang = pre.dataset.lang || '';

            const codeEl = pre.querySelector('code');
            const codeText = codeEl ? codeEl.textContent : pre.textContent;

            // Also check first comment line for file path
            if (!blockFile) {
                const codeFileHint = codeText.match(/^(?:\/\/|#|\/\*)\s*(?:file|файл|File):\s*(\S+\.\w{1,6})/im);
                if (codeFileHint) blockFile = codeFileHint[1];
            }

            // Shell command detection
            const isCommand = isShellCommand(blockLang, codeText);

            // ─── Copy button (inside pre, top-right) ───
            const copyBtn = document.createElement('button');
            copyBtn.className = 'copy-code-btn';
            copyBtn.textContent = 'Копировать';
            copyBtn.addEventListener('click', () => {
                navigator.clipboard.writeText(codeText).then(() => {
                    copyBtn.textContent = '✓';
                    setTimeout(() => { copyBtn.textContent = 'Копировать'; }, 1500);
                });
            });
            pre.style.position = 'relative';
            pre.appendChild(copyBtn);

            // ─── Action bar (below pre) ───
            const actionBar = document.createElement('div');
            actionBar.className = 'insert-bar';

            if (isCommand) {
                // ═══ EXECUTE for terminal commands ═══
                const execBtn = document.createElement('button');
                execBtn.className = 'exec-cmd-btn';
                execBtn.innerHTML = SVG.terminal + ' Выполнить в терминале';
                execBtn.title = `Выполнить: ${codeText.trim().split('\n')[0]}`;
                execBtn.addEventListener('click', () => {
                    vscode.postMessage({ type: 'runCommand', command: codeText.trim() });
                    execBtn.innerHTML = SVG.check + ' Запущено';
                    setTimeout(() => { execBtn.innerHTML = SVG.terminal + ' Выполнить в терминале'; }, 2000);
                });
                actionBar.appendChild(execBtn);
            } else {
                // ═══ Context-aware code action buttons ═══
                const fileLabel = blockFile
                    ? blockFile.replace(/\\/g, '/').split('/').slice(-2).join('/')
                    : null;
                const lineInfo = blockLine
                    ? (blockLineEnd ? ` :${blockLine}-${blockLineEnd}` : ` :${blockLine}`)
                    : '';
                const filePart = fileLabel ? `<span class="insert-file-hint">${escHtml(fileLabel)}${lineInfo}</span>` : '';

                // Determine which button(s) to show
                if (blockAction === 'delete' && blockFile && blockLine) {
                    // ── DELETE button ──
                    const delBtn = document.createElement('button');
                    delBtn.className = 'action-btn action-delete';
                    delBtn.innerHTML = SVG.block + ' Удалить из ' + filePart;
                    delBtn.title = `Удалить строки ${blockLine}-${blockLineEnd || blockLine} из ${blockFile}`;
                    delBtn.addEventListener('click', () => {
                        vscode.postMessage({
                            type: 'codeAction', action: 'delete',
                            targetFile: blockFile, lineStart: blockLine, lineEnd: blockLineEnd || blockLine,
                        });
                        delBtn.innerHTML = SVG.check + ' Удалено';
                        setTimeout(() => { delBtn.innerHTML = SVG.block + ' Удалить из ' + filePart; }, 2000);
                    });
                    actionBar.appendChild(delBtn);

                } else if (blockAction === 'add' && blockFile) {
                    // ── ADD button ──
                    const addBtn = document.createElement('button');
                    addBtn.className = 'action-btn action-add';
                    addBtn.innerHTML = '+ Добавить в ' + filePart;
                    addBtn.title = `Добавить код в ${blockFile}${blockLine ? ' после строки ' + blockLine : ''}`;
                    addBtn.addEventListener('click', () => {
                        vscode.postMessage({
                            type: 'codeAction', action: 'add',
                            code: codeText, targetFile: blockFile,
                            lineStart: blockLine, lineEnd: blockLineEnd,
                        });
                        addBtn.innerHTML = SVG.check + ' Добавлено';
                        setTimeout(() => { addBtn.innerHTML = '+ Добавить в ' + filePart; }, 2000);
                    });
                    actionBar.appendChild(addBtn);

                } else if (blockFile && blockLine) {
                    // ── REPLACE button (default when file+lines present) ──
                    const replBtn = document.createElement('button');
                    replBtn.className = 'action-btn action-replace';
                    replBtn.innerHTML = SVG.refresh + ' Заменить в ' + filePart;
                    replBtn.title = `Заменить строки ${blockLine}-${blockLineEnd || '...'} в ${blockFile}`;
                    replBtn.addEventListener('click', () => {
                        vscode.postMessage({
                            type: 'codeAction', action: 'replace',
                            code: codeText, targetFile: blockFile,
                            lineStart: blockLine, lineEnd: blockLineEnd,
                        });
                        replBtn.innerHTML = SVG.check + ' Заменено';
                        setTimeout(() => { replBtn.innerHTML = SVG.refresh + ' Заменить в ' + filePart; }, 2000);
                    });
                    actionBar.appendChild(replBtn);

                } else if (blockFile) {
                    // ── ADD to file (no line specified) ──
                    const addBtn = document.createElement('button');
                    addBtn.className = 'action-btn action-add';
                    addBtn.innerHTML = '+ Добавить в ' + filePart;
                    addBtn.title = `Добавить код в конец ${blockFile}`;
                    addBtn.addEventListener('click', () => {
                        vscode.postMessage({
                            type: 'codeAction', action: 'add',
                            code: codeText, targetFile: blockFile,
                        });
                        addBtn.innerHTML = SVG.check + ' Добавлено';
                        setTimeout(() => { addBtn.innerHTML = '+ Добавить в ' + filePart; }, 2000);
                    });
                    actionBar.appendChild(addBtn);

                } else {
                    // ── No file info — показываем Diff + Insert ──
                    // Кнопка Diff (показывает изменения в текущем файле)
                    const diffBtn = document.createElement('button');
                    diffBtn.className = 'action-btn action-replace';
                    diffBtn.innerHTML = SVG.search + ' Показать Diff';
                    diffBtn.title = 'Показать diff в текущем файле';
                    diffBtn.addEventListener('click', () => {
                        vscode.postMessage({
                            type: 'showProposedDiff',
                            file: null, // текущий файл
                            code: codeText,
                            action: 'replace',
                            lineStart: null,
                            lineEnd: null,
                        });
                    });
                    actionBar.appendChild(diffBtn);

                    // Кнопка Apply (заменяет в текущем файле)
                    const applyBtn = document.createElement('button');
                    applyBtn.className = 'action-btn action-add';
                    applyBtn.innerHTML = SVG.check + ' Применить';
                    applyBtn.title = 'Применить код в текущий файл';
                    applyBtn.addEventListener('click', () => {
                        vscode.postMessage({ type: 'codeAction', action: 'insert', code: codeText });
                        applyBtn.innerHTML = SVG.check + ' Применено';
                        setTimeout(() => { applyBtn.innerHTML = SVG.check + ' Применить'; }, 2000);
                    });
                    actionBar.appendChild(applyBtn);
                }
            }

            pre.parentNode.insertBefore(actionBar, pre.nextSibling);
        });

        // (global copy-btn removed — each code block has its own Copy button)

        // File change links — click to open
        bubble.querySelectorAll('.file-change-path, .ref-link').forEach(link => {
            link.addEventListener('click', () => {
                const file = link.getAttribute('data-file');
                if (file) vscode.postMessage({ type: 'openFile', filePath: file });
            });
        });

        // ── Proposed Changes buttons ──
        if (extra.proposed_changes && extra.proposed_changes.length) {
            const proposedChanges = extra.proposed_changes;

            // Show Diff buttons
            bubble.querySelectorAll('.proposed-diff-btn').forEach(btn => {
                btn.addEventListener('click', () => {
                    const idx = parseInt(btn.getAttribute('data-idx'));
                    const pc = proposedChanges[idx];
                    if (pc) {
                        vscode.postMessage({
                            type: 'showProposedDiff',
                            file: pc.file,
                            code: pc.code,
                            action: pc.action,
                            lineStart: pc.lineStart,
                            lineEnd: pc.lineEnd,
                        });
                    }
                });
            });

            // Apply single change buttons
            bubble.querySelectorAll('.proposed-apply-btn').forEach(btn => {
                btn.addEventListener('click', () => {
                    const idx = parseInt(btn.getAttribute('data-idx'));
                    const pc = proposedChanges[idx];
                    if (pc) {
                        vscode.postMessage({
                            type: 'applyProposedChange',
                            file: pc.file,
                            code: pc.code,
                            action: pc.action,
                            lineStart: pc.lineStart,
                            lineEnd: pc.lineEnd,
                        });
                        btn.innerHTML = SVG.check + ' Применено';
                        btn.disabled = true;
                        btn.classList.add('applied');
                        // Mark card as applied
                        const card = btn.closest('.proposed-change-card');
                        if (card) card.classList.add('applied');
                    }
                });
            });

            // Apply All button
            const applyAllBtn = bubble.querySelector('.proposed-apply-all-btn');
            if (applyAllBtn) {
                applyAllBtn.addEventListener('click', () => {
                    vscode.postMessage({
                        type: 'applyAllProposed',
                        changes: proposedChanges,
                    });
                    applyAllBtn.innerHTML = SVG.check + ' Применено';
                    applyAllBtn.disabled = true;
                    applyAllBtn.classList.add('applied');
                    // Mark all cards
                    bubble.querySelectorAll('.proposed-change-card').forEach(card => {
                        card.classList.add('applied');
                    });
                });
            }
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

    /**
     * Extract file path, line range, and ACTION type from text preceding a code block.
     * Returns { file, line, lineEnd, action }
     * action: 'replace' | 'add' | 'delete' | null
     */
        function extractFileLineHints(textBefore) {
        const ctx = textBefore.slice(-1000);
        
        let file = null;
        let line = null;
        let lineEnd = null;
        let action = null;

        // ACTION detection — теперь на чистом тексте, regex'ы работают корректно
        const actionMatch = ctx.match(/(?:Действие|Action)\s*[:：]\s*(заменить|добавить|удалить|replace|add|delete)/i);
        if (actionMatch) {
            const a = actionMatch[1].toLowerCase();
            if (a === 'заменить' || a === 'replace') action = 'replace';
            else if (a === 'добавить' || a === 'add') action = 'add';
            else if (a === 'удалить' || a === 'delete') action = 'delete';
        }

        if (!action) {
            const tail = ctx.slice(-400).toLowerCase();
            if (/(?:удал(?:ить|и|яем|ите)|remove|delete)\s/.test(tail)) action = 'delete';
            else if (/(?:добав(?:ить|ь|ляем|ьте)|add|insert|вставить)\s/.test(tail)) action = 'add';
            else if (/(?:замен(?:ить|и|яем|ите)|replace|refactor|рефактор|перепиш|оптимизир|исправ|fix)/i.test(tail)) action = 'replace';
        }

        // FILE detection — чистый текст, без &quot; и т.п.
        const filePatterns = [
            /(?:Файл|File|файл[еа]?)\s*[:：]\s*[`"']?([^\s`"'\n]+\.\w{1,6})[`"']?/gi,
            /(?:в файле|in file|из файла|from file)\s+[`"']?([^\s`"'\n]+\.\w{1,6})[`"']?/gi,
            /(?:файл|file)\s+[`]([^`]+\.\w{1,6})[`]/gi,
            /[`]([^\s`]+[\/\\][^\s`]+\.\w{1,6})[`]/g,
        ];

        for (const pattern of filePatterns) {
            pattern.lastIndex = 0;
            const matches = [...ctx.matchAll(pattern)];
            if (matches.length) {
                file = matches[matches.length - 1][1];
                break;
            }
        }

        // LINE RANGE detection
        const rangePatterns = [
            /(?:строк[аи]?|lines?|line)\s*[:：]?\s*~?(\d+)\s*[-–—]\s*(\d+)/gi,
            /\((?:строк[аи]?|lines?)\s+~?(\d+)\s*[-–—]\s*(\d+)\)/gi,
        ];
        for (const pattern of rangePatterns) {
            pattern.lastIndex = 0;
            const matches = [...ctx.matchAll(pattern)];
            if (matches.length) {
                const m = matches[matches.length - 1];
                line = parseInt(m[1]);
                lineEnd = parseInt(m[2]);
                break;
            }
        }

        // Single line
        if (!line) {
            const singlePatterns = [
                /(?:Строк[аи]?|Lines?|line|строк[аи]?)\s*[:：]?\s*~?(\d+)/gi,
            ];
            for (const pattern of singlePatterns) {
                pattern.lastIndex = 0;
                const matches = [...ctx.matchAll(pattern)];
                if (matches.length) {
                    line = parseInt(matches[matches.length - 1][1]);
                    break;
                }
            }
        }

        if (file && line && !action) action = 'replace';

        return { file, line, lineEnd, action };
    }

    /**
     * Detect if a code block contains a shell/terminal command (not programming code).
     */
    function isShellCommand(lang, code) {
        const shellLangs = ['bash', 'sh', 'shell', 'cmd', 'powershell', 'bat', 'zsh', 'terminal', 'console'];
        if (lang && shellLangs.includes(lang.toLowerCase())) return true;

        const trimmed = code.trim();
        const lines = trimmed.split('\n').filter(l => l.trim() && !l.trim().startsWith('#'));
        if (lines.length === 0 || lines.length > 5) return false;

        const cmdPrefixes = [
            'npm ', 'npx ', 'pip ', 'pip3 ', 'python ', 'python3 ', 'node ',
            'git ', 'cd ', 'rm ', 'del ', 'mkdir ', 'ls ', 'dir ', 'cat ',
            'docker ', 'yarn ', 'pnpm ', 'cargo ', 'go ', 'make ', 'cmake ',
            'apt ', 'brew ', 'choco ', 'curl ', 'wget ', './', 'sudo ',
            'cp ', 'mv ', 'touch ', 'echo ', 'export ', 'set ', 'source ',
        ];
        return lines.every(l => {
            const lt = l.trim().replace(/^\$\s*/, '');
            return cmdPrefixes.some(p => lt.startsWith(p)) || lt.startsWith('./');
        });
    }

// sidebar.js, в renderMarkdown() — ИЗМЕНИТЬ порядок:
// Сохраняем оригинальный текст для извлечения хинтов ПЕРЕД escaping

    function renderMarkdown(text) {
        if (!text) return '';

        // Убираем артефакты модели
        text = text.replace(/<\|(?:system|user|assistant|end|im_start|im_end|endoftext)\|>/g, '');
        text = text.replace(/<\/?(?:system|user|assistant)>/g, '');
        text = text.replace(/(?:^|\n)user\n[\s\S]*?\nassistant(?:\n|$)/g, '\n');
        text = text.replace(/^(?:user|assistant|system)\s*$/gm, '');

        const qMatch = text.search(/\n(?:Question|## Question|Вопрос):\s/);
        if (qMatch > text.length * 0.5 && qMatch > 100) {
            text = text.substring(0, qMatch);
        }

        // КЛЮЧЕВОЕ: сохраняем оригинал ДО escaping для парсинга хинтов
        const originalText = text;
        const esc = escHtml(text);

        let result = '';
        let remaining = esc;
        // Трекаем позицию в оригинальном тексте параллельно
        let origPos = 0;

        while (remaining.length) {
            const idx = remaining.indexOf('```');
            if (idx === -1) { result += processInline(remaining); break; }

            const textBefore = remaining.slice(0, idx);
            result += processInline(textBefore);

            // Находим соответствующую позицию в оригинальном тексте
            const origIdx = originalText.indexOf('```', origPos);
            const originalTextBefore = origIdx >= 0 ? originalText.slice(Math.max(0, origIdx - 1000), origIdx) : '';

            const after = remaining.slice(idx + 3);
            const nl = after.indexOf('\n');
            let lang = '', code = after;
            if (nl !== -1 && nl < 20) { lang = after.slice(0, nl).trim(); code = after.slice(nl + 1); }

            // Хинты из ОРИГИНАЛЬНОГО текста (не escape'нного!)
            const hints = extractFileLineHints(originalTextBefore);
            const dataAttrs = [];
            if (hints.file) dataAttrs.push(`data-file="${escHtml(hints.file)}"`);
            if (hints.line) dataAttrs.push(`data-line="${hints.line}"`);
            if (hints.lineEnd) dataAttrs.push(`data-line-end="${hints.lineEnd}"`);
            if (hints.action) dataAttrs.push(`data-action="${hints.action}"`);
            if (lang) dataAttrs.push(`data-lang="${lang}"`);
            const attrStr = dataAttrs.length ? ' ' + dataAttrs.join(' ') : '';

            const end = code.indexOf('```');
            if (end === -1) {
                result += `<pre${attrStr}><code class="language-${lang}">${code}</code></pre>`;
                break;
            }
            result += `<pre${attrStr}><code class="language-${lang}">${code.slice(0, end)}</code></pre>`;
            remaining = code.slice(end + 3);

            // Синхронизируем позицию в оригинале
            if (origIdx >= 0) {
                const origAfter = originalText.slice(origIdx + 3);
                const origNl = origAfter.indexOf('\n');
                let origCode = origAfter;
                if (origNl !== -1 && origNl < 20) origCode = origAfter.slice(origNl + 1);
                const origEnd = origCode.indexOf('```');
                origPos = origEnd >= 0 ? originalText.indexOf('```', origIdx + 3) + 3 + origEnd + 3 : originalText.length;
            }
        }

        return result;
    }

    function processInline(text) {
        text = processTable(text);

        // Horizontal rules: --- or *** or ___ on their own line (BEFORE other processing)
        text = text.replace(/^[\t ]*[-*_]{3,}[\t ]*$/gm, '<hr>');

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
        // Convert newlines to <br>, but skip lines that are already block-level HTML
        text = text.replace(/\n/g, '<br>');
        // Clean up <br> right before/after block elements
        text = text.replace(/<br>\s*(<(?:h[1-4]|hr|ul|li|table|div|details))/g, '$1');
        text = text.replace(/(<\/(?:h[1-4]|hr|ul|li|table|div|details)>)\s*<br>/g, '$1');
        return text;
    }

    function processTable(text) {
        const lines = text.split('\n');
        let result = [];
        let tableLines = [];
        let inTable = false;

        for (let i = 0; i < lines.length; i++) {
            const line = lines[i].trim();
            const isTableRow = line.startsWith('|') && line.endsWith('|') && line.includes('|');
            const isSeparator = /^\|[-:\s|]+\|$/.test(line);

            if (isTableRow || isSeparator) {
                if (!inTable) inTable = true;
                tableLines.push(line);
            } else {
                if (inTable && tableLines.length >= 2) {
                    result.push(buildHtmlTable(tableLines));
                    tableLines = [];
                    inTable = false;
                } else if (inTable) {
                    result.push(...tableLines);
                    tableLines = [];
                    inTable = false;
                }
                result.push(lines[i]);
            }
        }

        if (inTable && tableLines.length >= 2) {
            result.push(buildHtmlTable(tableLines));
        } else if (tableLines.length) {
            result.push(...tableLines);
        }

        return result.join('\n');
    }

    function buildHtmlTable(lines) {
        const rows = lines.filter(l => !/^\|[-:\s|]+\|$/.test(l.trim()));
        if (rows.length === 0) return '';

        let html = '<table class="md-table">';

        rows.forEach((row, idx) => {
            const cells = row.split('|').filter((c, i, arr) => i > 0 && i < arr.length - 1);
            const tag = idx === 0 ? 'th' : 'td';

            if (idx === 0) html += '<thead>';
            if (idx === 1) html += '<tbody>';

            html += '<tr>';
            cells.forEach(cell => {
                html += `<${tag}>${cell.trim()}</${tag}>`;
            });
            html += '</tr>';

            if (idx === 0) html += '</thead>';
        });

        html += '</tbody></table>';
        return html;
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

            // ── Streaming events (new!) ──
            case 'streamStatus':
                showStreamProgress(msg.content);
                break;

            case 'streamThinking':
                addStreamThinking(msg.content);
                break;

            case 'streamAgentStart':
                showStreamProgress(`${msg.agents ? msg.agents.join(' → ') : 'агент'} работает...`);
                break;

            case 'streamToolCall':
                addStreamToolCall(msg.tool, msg.args);
                break;

            case 'streamToolResult':
                addStreamToolResult(msg.tool, msg.success, msg.output);
                break;

            case 'streamAgentDone':
                // Will be followed by chatResponse
                break;

            // ── Final response ──
            case 'chatResponse':
                removeStreamProgress();
                removeTyping();
                _resetLoadingState();
                if (msg.agent_trace) {
                    showAgentTrace(msg.agent_trace, msg.intent);
                }
                addMessage('assistant', msg.content, {
                    agent: msg.agent,
                    code: msg.code,
                    references: msg.references,
                    agent_trace: msg.agent_trace,
                    thinking: msg.thinking || '',
                    file_changes: msg.file_changes || [],
                    proposed_changes: msg.proposed_changes || [],
                });
                break;

            case 'streamToken':
                removeTyping();
                removeStreamProgress();
                let streamEl = document.getElementById('streaming-bubble');
                if (!streamEl) {
                    const wrapper = document.createElement('div');
                    wrapper.className = 'msg msg-assistant streaming-msg';
                    const bubble = document.createElement('div');
                    bubble.className = 'msg-bubble';
                    bubble.id = 'streaming-bubble';
                    bubble.innerHTML = '<span class="streaming-cursor"></span>';
                    wrapper.appendChild(bubble);
                    chatArea.appendChild(wrapper);
                }
                streamEl = document.getElementById('streaming-bubble');
                const cursor = streamEl.querySelector('.streaming-cursor');
                if (cursor) {
                    const tokenSpan = document.createTextNode(msg.content);
                    streamEl.insertBefore(tokenSpan, cursor);
                }
                chatArea.scrollTop = chatArea.scrollHeight;
                break;

            case 'streamEnd':
                const streamBubble = document.getElementById('streaming-bubble');
                if (streamBubble) {
                    const rawText = streamBubble.textContent;
                    streamBubble.parentElement.remove();
                    addMessage('assistant', rawText, {
                        agent: msg.agent || 'analyst',
                        references: msg.context_files || [],
                        thinking: msg.thinking || '',
                    });
                }
                _resetLoadingState();
                break;

            case 'error':
                removeStreamProgress();
                removeTyping();
                _resetLoadingState();
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
                    if (llm_engine_loaded) {
                        setStatus('online', 'готов');
                    } else {
                        setStatus('', 'нет модели');
                        activeModelName.textContent = 'Не загружена';
                    }
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
                            addSystemMsg(`✅ ${m.name} скачана!`);
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
                        ftResult.style.background = 'rgba(63,185,80,0.08)';
                        ftResult.style.borderColor = 'rgba(63,185,80,0.2)';
                        ftResult.style.color = 'var(--green)';
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
                chatInput.value = 'Объясни этот код подробно: что он делает, как работает, какие есть потенциальные проблемы — и предложи улучшенную версию кода';
                sendMessage();
                break;
        }
    });

    // Track model loaded state
    let llm_engine_loaded = false;
    window.addEventListener('message', e => {
        if (e.data.type === 'modelLoaded') llm_engine_loaded = true;
    });

    // Health poll
    setInterval(() => { vscode.postMessage({ type: 'getModels' }); }, 30000);

})();
