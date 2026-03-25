// @ts-nocheck
(function () {
    var vscode = acquireVsCodeApi();

    var chatContainer = document.getElementById('chatContainer');
    var chatInput = document.getElementById('chatInput');
    var sendBtn = document.getElementById('sendBtn');
    var modelSelect = document.getElementById('modelSelect');
    var loadModelBtn = document.getElementById('loadModelBtn');
    var downloadModelBtn = document.getElementById('downloadModelBtn');
    var indexBtn = document.getElementById('indexBtn');
    var clearBtn = document.getElementById('clearBtn');
    var statusDot = document.getElementById('statusDot');
    var statusText = document.getElementById('statusText');
    var welcome = document.getElementById('welcome');
    var finetuneBtn = document.getElementById('finetuneBtn');


    var conversationHistory = [];
    var isLoading = false;
    var currentModel = null;
    var messageIdCounter = 0;

    // Restore state
    var previousState = vscode.getState();
    if (previousState) {
        conversationHistory = previousState.conversationHistory || [];
        currentModel = previousState.currentModel || null;
        if (conversationHistory.length > 0 && welcome) {
            welcome.style.display = 'none';
            for (var i = 0; i < conversationHistory.length; i++) {
                addMessageToDOM(conversationHistory[i].role, conversationHistory[i].content, conversationHistory[i].extra || {});
            }
        }
    }

    vscode.postMessage({ type: 'getModels' });

    // ──── Event Listeners ────

    sendBtn.addEventListener('click', sendMessage);

    chatInput.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    chatInput.addEventListener('input', function () {
        chatInput.style.height = 'auto';
        chatInput.style.height = Math.min(chatInput.scrollHeight, 150) + 'px';
    });

    loadModelBtn.addEventListener('click', function () {
        var modelId = modelSelect.value;
        if (!modelId) {
            addSystemMessage('Please select a model first');
            return;
        }
        addSystemMessage('Loading model ' + modelId + '...');
        statusDot.className = 'status-dot';
        statusText.textContent = 'Loading ' + modelId + '...';
        vscode.postMessage({ type: 'loadModel', modelId: modelId });
    });

    downloadModelBtn.addEventListener('click', function () {
        var modelId = modelSelect.value;
        if (!modelId) {
            addSystemMessage('Please select a model first');
            return;
        }
        addSystemMessage('Downloading ' + modelId + '... This may take several minutes.');
        vscode.postMessage({ type: 'startDownload', modelId: modelId });
    });

    indexBtn.addEventListener('click', function () {
        addSystemMessage('Indexing project...');
        vscode.postMessage({ type: 'indexProject' });
    });

    clearBtn.addEventListener('click', function () {
        conversationHistory = [];
        var messages = chatContainer.querySelectorAll('.message, .loading');
        for (var i = 0; i < messages.length; i++) {
            messages[i].remove();
        }
        if (welcome) { welcome.style.display = ''; }
        saveState();
    });

    finetuneBtn.addEventListener('click', function () {
        addSystemMessage('Starting fine-tuning on project codebase...');
        vscode.postMessage({ type: 'fineTune' });
    });

    var quickBtns = document.querySelectorAll('.quick-action');
    for (var qi = 0; qi < quickBtns.length; qi++) {
        quickBtns[qi].addEventListener('click', function () {
            chatInput.value = this.getAttribute('data-prompt');
            sendMessage();
        });
    }

    // ──── Core ────

    function sendMessage() {
        var content = chatInput.value.trim();
        if (!content || isLoading) { return; }
        if (welcome) { welcome.style.display = 'none'; }

        addMessage('user', content);

        vscode.postMessage({
            type: 'chat',
            content: content,
            history: conversationHistory.slice(-10),
        });

        chatInput.value = '';
        chatInput.style.height = 'auto';
        isLoading = true;
        sendBtn.disabled = true;
        showLoading();
    }

    function addMessage(role, content, extra) {
        extra = extra || {};
        conversationHistory.push({ role: role, content: content, extra: extra, timestamp: Date.now() });
        addMessageToDOM(role, content, extra);
        saveState();
    }

    function addMessageToDOM(role, content, extra) {
        extra = extra || {};
        var msgDiv = document.createElement('div');
        msgDiv.className = 'message ' + role;
        messageIdCounter++;
        msgDiv.id = 'msg-' + messageIdCounter;

        var html = '';

        if (extra.agent && role === 'assistant') {
            var agentNames = { 'analyst': 'Analyst', 'coder': 'Coder', 'refactor': 'Refactor', 'tester': 'Tester', 'general': 'Assistant' };
            html += '<span class="agent-badge ' + extra.agent + '">' + (agentNames[extra.agent] || extra.agent) + '</span><br>';
        }

        html += formatMarkdown(content);

        if (extra.code) {
            html += '<div class="code-actions">';
            html += '<button class="btn-small btn-primary insert-code-btn">Insert into Editor</button> ';
            html += '<button class="btn-small copy-code-btn">Copy Code</button>';
            html += '</div>';
            msgDiv.setAttribute('data-code', extra.code);
        }

        if (extra.references && extra.references.length > 0) {
            html += '<div class="references">Files: ';
            for (var ri = 0; ri < extra.references.length; ri++) {
                html += '<a class="ref-link">' + escapeHtml(extra.references[ri]) + '</a>';
                if (ri < extra.references.length - 1) { html += ', '; }
            }
            html += '</div>';
        }

        msgDiv.innerHTML = html;

        // Insert code button
        var insertBtns = msgDiv.querySelectorAll('.insert-code-btn');
        for (var ib = 0; ib < insertBtns.length; ib++) {
            insertBtns[ib].addEventListener('click', function () {
                var codeData = this.closest('.message').getAttribute('data-code');
                if (codeData) { vscode.postMessage({ type: 'insertCode', code: codeData }); }
            });
        }

        // Copy code button
        var copyBtns = msgDiv.querySelectorAll('.copy-code-btn');
        for (var cb = 0; cb < copyBtns.length; cb++) {
            copyBtns[cb].addEventListener('click', function () {
                var codeData = this.closest('.message').getAttribute('data-code');
                if (codeData) {
                    var el = this;
                    navigator.clipboard.writeText(codeData).then(function () {
                        el.textContent = 'Copied!';
                        setTimeout(function () { el.textContent = 'Copy Code'; }, 2000);
                    });
                }
            });
        }

        // Copy button on code blocks
        var codeBlocks = msgDiv.querySelectorAll('pre');
        for (var cb2 = 0; cb2 < codeBlocks.length; cb2++) {
            (function (pre) {
                var btn = document.createElement('button');
                btn.className = 'copy-btn';
                btn.textContent = 'Copy';
                btn.addEventListener('click', function () {
                    var codeEl = pre.querySelector('code');
                    var text = codeEl ? codeEl.textContent : pre.textContent;
                    navigator.clipboard.writeText(text).then(function () {
                        btn.textContent = 'OK!';
                        setTimeout(function () { btn.textContent = 'Copy'; }, 2000);
                    });
                });
                pre.style.position = 'relative';
                pre.appendChild(btn);
            })(codeBlocks[cb2]);
        }

        chatContainer.appendChild(msgDiv);
        chatContainer.scrollTop = chatContainer.scrollHeight;
    }

    function showLoading() {
        var ex = document.getElementById('loadingIndicator');
        if (ex) { ex.remove(); }
        var el = document.createElement('div');
        el.className = 'loading';
        el.id = 'loadingIndicator';
        el.innerHTML = '<span></span><span></span><span></span>';
        chatContainer.appendChild(el);
        chatContainer.scrollTop = chatContainer.scrollHeight;
    }

    function hideLoading() {
        var el = document.getElementById('loadingIndicator');
        if (el) { el.remove(); }
    }

    // ──── Markdown ────

    function formatMarkdown(text) {
        if (!text) { return ''; }
        var escaped = escapeHtml(text);

        // Split by code blocks (```) manually
        var result = '';
        var remaining = escaped;
        var marker = '```';

        while (true) {
            var startIdx = remaining.indexOf(marker);
            if (startIdx === -1) {
                result += processInline(remaining);
                break;
            }

            result += processInline(remaining.substring(0, startIdx));

            var afterStart = remaining.substring(startIdx + 3);
            var nlIdx = afterStart.indexOf('\n');
            var lang = '';
            if (nlIdx !== -1 && nlIdx < 30) {
                lang = afterStart.substring(0, nlIdx).trim();
                afterStart = afterStart.substring(nlIdx + 1);
            }

            var endIdx = afterStart.indexOf(marker);
            if (endIdx === -1) {
                result += '<pre><code>' + afterStart + '</code></pre>';
                break;
            }

            result += '<pre><code class="language-' + lang + '">' + afterStart.substring(0, endIdx) + '</code></pre>';
            remaining = afterStart.substring(endIdx + 3);
        }

        return result;
    }

    function processInline(text) {
        // Inline code via backtick split
        var parts = text.split('`');
        var out = '';
        for (var pi = 0; pi < parts.length; pi++) {
            if (pi % 2 === 1) {
                out += '<code>' + parts[pi] + '</code>';
            } else {
                out += parts[pi];
            }
        }
        text = out;

        text = text.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
        text = text.replace(/^#### (.+)$/gm, '<h4>$1</h4>');
        text = text.replace(/^### (.+)$/gm, '<h3>$1</h3>');
        text = text.replace(/^## (.+)$/gm, '<h2>$1</h2>');
        text = text.replace(/^# (.+)$/gm, '<h1>$1</h1>');
        text = text.replace(/\n/g, '<br>');
        return text;
    }

    function escapeHtml(text) {
        var d = document.createElement('div');
        d.textContent = text;
        return d.innerHTML;
    }

    // ──── Models ────

    function updateModelList(models, defaultModelId) {
        modelSelect.innerHTML = '';

        for (var mi = 0; mi < models.length; mi++) {
            var m = models[mi];
            var opt = document.createElement('option');
            opt.value = m.id;
            var lbl = m.name;
            if (m.downloaded) { lbl += ' [downloaded]'; }
            if (m.active) { lbl += ' [ACTIVE]'; }
            lbl += ' | ' + m.ram_required;
            opt.textContent = lbl;
            if (m.active) {
                opt.selected = true;
            } else if (!currentModel && m.id === defaultModelId) {
                opt.selected = true;
            }
            modelSelect.appendChild(opt);
        }

        var activeModel = null;
        for (var ai = 0; ai < models.length; ai++) {
            if (models[ai].active) { activeModel = models[ai]; break; }
        }

        if (activeModel) {
            statusDot.className = 'status-dot connected';
            statusText.textContent = 'Ready: ' + activeModel.name;
            currentModel = activeModel.id;
        } else {
            statusDot.className = 'status-dot';
            statusText.textContent = 'No model loaded — click Load';
        }
    }

    function saveState() {
        vscode.setState({
            conversationHistory: conversationHistory.slice(-50),
            currentModel: currentModel
        });
    }

    function addSystemMessage(text) {
        var el = document.createElement('div');
        el.className = 'message system';
        el.textContent = text;
        chatContainer.appendChild(el);
        chatContainer.scrollTop = chatContainer.scrollHeight;
    }

    // ──── Messages from Extension ────

    window.addEventListener('message', function (event) {
        var msg = event.data;

        switch (msg.type) {
            case 'chatResponse':
                hideLoading();
                isLoading = false;
                sendBtn.disabled = false;
                addMessage('assistant', msg.content, {
                    agent: msg.agent,
                    code: msg.code,
                    references: msg.references
                });
                break;

            case 'error':
                hideLoading();
                isLoading = false;
                sendBtn.disabled = false;
                addSystemMessage('ERROR: ' + msg.content);
                break;

            case 'status':
                addSystemMessage(msg.content);
                break;

            case 'modelList':
                updateModelList(msg.models, msg['default']);
                break;

            case 'modelLoaded':
                currentModel = msg.modelId;
                statusDot.className = 'status-dot connected';
                statusText.textContent = 'Ready: ' + msg.modelId;
                addSystemMessage('Model ' + msg.modelId + ' loaded and ready!');
                saveState();
                vscode.postMessage({ type: 'getModels' });
                break;

            case 'modelDownloaded':
                addSystemMessage('Model ' + msg.modelId + ' downloaded! Now click Load to activate it.');
                vscode.postMessage({ type: 'getModels' });
                break;

            case 'explain':
                if (welcome) { welcome.style.display = 'none'; }
                chatInput.value = 'Explain this code in detail';
                sendMessage();
                break;
        }
    });

    // Health check every 30s
    setInterval(function () {
        vscode.postMessage({ type: 'getModels' });
    }, 30000);

})();