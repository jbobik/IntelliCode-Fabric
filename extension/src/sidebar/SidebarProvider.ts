import * as vscode from 'vscode';
import * as path from 'path';
import * as fs from 'fs';

export class SidebarProvider implements vscode.WebviewViewProvider {
    private _view?: vscode.WebviewView;
    private _serverUrl: string;
    private _pendingMessages: any[] = [];
    private _currentRequest: any = null; // Active HTTP request for cancellation
    private _isCancelled = false;         // True when user explicitly cancelled

    constructor(
        private readonly _extensionUri: vscode.Uri,
        serverUrl: string
    ) {
        this._serverUrl = serverUrl;
    }

    resolveWebviewView(
        webviewView: vscode.WebviewView,
        _context: vscode.WebviewViewResolveContext,
        _token: vscode.CancellationToken
    ) {
        this._view = webviewView;
        webviewView.webview.options = {
            enableScripts: true,
            localResourceRoots: [vscode.Uri.joinPath(this._extensionUri, 'media')],
        };
        webviewView.webview.html = this._getHtml(webviewView.webview);

        webviewView.webview.onDidReceiveMessage(async (msg) => {
            switch (msg.type) {
                case 'chat': await this._handleChat(msg); break;
                case 'getModels': await this._sendModelList(); break;
                case 'loadCustomModel':
                    await this._loadCustomModel(msg.repo, msg.name, msg.quantization);
                    break;
                case 'downloadCustomModel':
                    await this._downloadCustomModel(msg.repo, msg.name, msg.quantization);
                    break;
                case 'getAdapters':
                    await this._sendAdapterList();
                    break;
                case 'loadModel': await this._loadModel(msg.modelId, msg.adapterId); break;
                case 'startDownload': await this._downloadModel(msg.modelId); break;
                case 'getDownloadProgress':
                    await this._sendDownloadProgress(msg.modelId);
                    break;
                case 'indexProject': vscode.commands.executeCommand('intelliCodeFabric.indexProject'); break;
                case 'fineTune':
                    await this._startFineTune(msg.modelId, msg.epochs, msg.strategies, {
                        learning_rate: msg.learning_rate,
                        batch_size: msg.batch_size,
                        gradient_accumulation_steps: msg.gradient_accumulation_steps,
                        lora_r: msg.lora_r,
                        lora_alpha: msg.lora_alpha,
                        max_seq_length: msg.max_seq_length,
                    });
                    break;
                case 'getFtStatus':
                    await this._sendFtStatus();
                    break;
                case 'insertCode': this._insertCode(msg.code, msg.targetFile, msg.lineStart, msg.lineEnd); break;
                case 'codeAction': this._handleCodeAction(msg); break;
                case 'runCommand': this._runCommand(msg.command); break;
                case 'applyAllChanges': await this._applyAllChanges(msg.changes); break;
                case 'createFile': await this._createFile(msg.filePath, msg.content); break;
                case 'openFile': await this._openFile(msg.filePath, msg.lineStart); break;
                case 'showProposedDiff': await this._showProposedDiff(msg); break;
                case 'applyProposedChange': await this._applyProposedChange(msg); break;
                case 'applyAllProposed': await this._applyAllProposed(msg.changes); break;
                case 'cancelRequest': this._cancelCurrentRequest(); break;
            }
        });

        for (const m of this._pendingMessages) webviewView.webview.postMessage(m);
        this._pendingMessages = [];
    }

    sendMessage(message: any) {
        if (this._view) {
            this._view.webview.postMessage(message);
        } else {
            this._pendingMessages.push(message);
        }
    }

    // ─── Chat with SSE streaming ───────────────────────────────────────────

    private async _handleChat(message: any) {
        const editor = vscode.window.activeTextEditor;
        const selectedCode = editor?.selection.isEmpty ? undefined : editor?.document.getText(editor.selection);
        const contextFile = editor?.document.fileName;
        const workspacePath = vscode.workspace.workspaceFolders?.[0]?.uri?.fsPath;

        const body = JSON.stringify({
            message: message.content,
            selected_code: selectedCode,
            context_file: contextFile,
            workspace_path: workspacePath,
            conversation_history: message.history || [],
            platform: process.platform,
        });

        // Reset cancel flag for new request
        this._isCancelled = false;

        // Сначала пробуем SSE streaming, если не получится — fallback на обычный /chat
        try {
            const streamOk = await this._handleChatSSE(body);
            if (!streamOk) {
                await this._handleChatFallback(body);
            }
        } catch (error: any) {
            this._view?.webview.postMessage({
                type: 'error',
                content: `${error.message}. Запущен ли бэкенд? (cd backend && python server.py)`,
            });
        }
    }

    /**
     * SSE streaming через http module (работает в Node.js окружении VS Code).
     * Возвращает true если стриминг прошёл успешно, false если нужен fallback.
     */
    private _handleChatSSE(body: string): Promise<boolean> {
        return new Promise((resolve) => {
            try {
                const url = new URL(`${this._serverUrl}/chat/stream`);
                const http = require('http');

                const options = {
                    hostname: url.hostname,
                    port: url.port,
                    path: url.pathname,
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Accept': 'text/event-stream',
                        'Content-Length': Buffer.byteLength(body),
                    },
                };

                const req = http.request(options, (res: any) => {
                    if (res.statusCode !== 200) {
                        this._currentRequest = null;
                        resolve(false);
                        return;
                    }

                    let buffer = '';
                    let receivedFinalResult = false;

                    res.setEncoding('utf8');

                    res.on('data', (chunk: string) => {
                        buffer += chunk;
                        // Parse SSE events: split by double newline
                        const parts = buffer.split('\n\n');
                        buffer = parts.pop() || '';

                        for (const part of parts) {
                            const trimmed = part.trim();
                            if (!trimmed.startsWith('data: ')) continue;
                            try {
                                const event = JSON.parse(trimmed.slice(6));
                                this._handleStreamEvent(event);
                                if (event.type === 'final_result' || event.type === 'error') {
                                    receivedFinalResult = true;
                                }
                            } catch {}
                        }
                    });

                    res.on('end', () => {
                        this._currentRequest = null;
                        // Process remaining buffer
                        if (buffer.trim().startsWith('data: ')) {
                            try {
                                const event = JSON.parse(buffer.trim().slice(6));
                                this._handleStreamEvent(event);
                                if (event.type === 'final_result' || event.type === 'error') {
                                    receivedFinalResult = true;
                                }
                            } catch {}
                        }
                        resolve(receivedFinalResult);
                    });

                    res.on('error', () => {
                        this._currentRequest = null;
                        if (this._isCancelled) { this._isCancelled = false; resolve(true); return; }
                        resolve(false);
                    });
                });

                req.on('error', () => {
                    this._currentRequest = null;
                    if (this._isCancelled) { this._isCancelled = false; resolve(true); return; }
                    resolve(false);
                });

                // No timeout — LLM generation can take minutes
                req.setTimeout(0);

                // Store request for cancellation
                this._currentRequest = req;

                req.write(body);
                req.end();

            } catch {
                resolve(false);
            }
        });
    }

    private _handleStreamEvent(event: any) {
        switch (event.type) {
            case 'status':
                this._view?.webview.postMessage({
                    type: 'streamStatus',
                    content: event.data,
                });
                break;

            case 'thinking':
                this._view?.webview.postMessage({
                    type: 'streamThinking',
                    content: event.data,
                });
                break;

            case 'agent_start':
                this._view?.webview.postMessage({
                    type: 'streamAgentStart',
                    intent: event.data?.intent,
                    agents: event.data?.agents,
                });
                break;

            case 'tool_call':
                this._view?.webview.postMessage({
                    type: 'streamToolCall',
                    tool: event.data?.tool,
                    args: event.data?.args,
                });
                break;

            case 'tool_result':
                this._view?.webview.postMessage({
                    type: 'streamToolResult',
                    tool: event.data?.tool,
                    success: event.data?.success,
                    output: event.data?.output,
                });
                break;

            case 'agent_done':
                this._view?.webview.postMessage({
                    type: 'streamAgentDone',
                    agent: event.data?.agent,
                });
                break;

            case 'final_result':
                this._view?.webview.postMessage({
                    type: 'chatResponse',
                    content: event.data?.response,
                    code: event.data?.code,
                    agent: event.data?.agent,
                    intent: event.data?.intent,
                    references: event.data?.references || [],
                    agent_trace: event.data?.agent_trace || [],
                    rag_chunks: event.data?.rag_chunks || 0,
                    thinking: event.data?.thinking || '',
                    file_changes: event.data?.file_changes || [],
                    proposed_changes: event.data?.proposed_changes || [],
                });
                break;

            case 'error':
                this._view?.webview.postMessage({
                    type: 'error',
                    content: event.data || 'Unknown error',
                });
                break;
        }
    }

    private _handleChatFallback(body: string): Promise<void> {
        // Fallback: обычный /chat без streaming (через http module — без таймаута)
        this._view?.webview.postMessage({
            type: 'streamStatus',
            content: '🔍 Анализирую запрос...',
        });

        return new Promise((resolve) => {
            try {
                const url = new URL(`${this._serverUrl}/chat`);
                const http = require('http');

                const options = {
                    hostname: url.hostname,
                    port: url.port,
                    path: url.pathname,
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Content-Length': Buffer.byteLength(body),
                    },
                };

                const req = http.request(options, (res: any) => {
                    let data = '';
                    res.setEncoding('utf8');
                    res.on('data', (chunk: string) => { data += chunk; });
                    res.on('end', () => {
                        try {
                            if (res.statusCode !== 200) {
                                this._view?.webview.postMessage({
                                    type: 'error',
                                    content: `Ошибка сервера: ${data}`,
                                });
                            } else {
                                const result = JSON.parse(data);
                                this._view?.webview.postMessage({
                                    type: 'chatResponse',
                                    content: result.response,
                                    code: result.code,
                                    agent: result.agent,
                                    intent: result.intent,
                                    references: result.references,
                                    agent_trace: result.agent_trace || [],
                                    rag_chunks: result.rag_chunks || 0,
                                    thinking: result.thinking || '',
                                    file_changes: result.file_changes || [],
                                    proposed_changes: result.proposed_changes || [],
                                });
                            }
                        } catch (e: any) {
                            this._view?.webview.postMessage({
                                type: 'error',
                                content: `Ошибка парсинга ответа: ${e.message}`,
                            });
                        }
                        resolve();
                    });
                    res.on('error', (e: any) => {
                        this._view?.webview.postMessage({
                            type: 'error',
                            content: `${e.message}. Запущен ли бэкенд?`,
                        });
                        resolve();
                    });
                });

                req.on('error', (e: any) => {
                    this._view?.webview.postMessage({
                        type: 'error',
                        content: `${e.message}. Запущен ли бэкенд? (cd backend && python server.py)`,
                    });
                    resolve();
                });

                req.setTimeout(0); // No timeout — LLM can take minutes
                this._currentRequest = req;
                req.write(body);
                req.end();

            } catch (error: any) {
                this._view?.webview.postMessage({
                    type: 'error',
                    content: `${error.message}. Запущен ли бэкенд?`,
                });
                resolve();
            }
        });
    }

    // ─── Cancel Request ────────────────────────────────────────

    // SidebarProvider.ts, в _cancelCurrentRequest()
    private _cancelCurrentRequest() {
        this._isCancelled = true;

        if (this._currentRequest) {
            try {
                this._currentRequest.destroy();
            } catch {}
            this._currentRequest = null;
        }

        // Also call server-side cancel endpoint (best-effort)
        try {
            const url = new URL(`${this._serverUrl}/chat/cancel`);
            const http = require('http');
            const req = http.request({
                hostname: url.hostname,
                port: url.port,
                path: url.pathname,
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
            });
            req.on('error', () => {}); // ignore errors
            req.end();
        } catch {}

        // НОВОЕ: Сразу отправить UI-сообщение об отмене,
        // чтобы UI не ждал final_result который никогда не придёт
        this._view?.webview.postMessage({
            type: 'chatResponse',
            content: '⏹ Запрос отменён',
            code: null,
            agent: 'system',
            intent: 'cancelled',
            references: [],
            agent_trace: [],
            rag_chunks: 0,
            thinking: '',
            file_changes: [],
            proposed_changes: [],
        });
    }

    // ─── Models ────────────────────────────────────────────────

    private async _sendModelList() {
        try {
            const response = await fetch(`${this._serverUrl}/models`);
            if (!response.ok) throw new Error(response.statusText);
            const data = await response.json() as any;
            this._view?.webview.postMessage({ type: 'modelList', ...data });
        } catch {
            this._view?.webview.postMessage({
                type: 'error',
                content: 'Нет подключения к бэкенду. Запустите: cd backend && python server.py',
            });
        }
    }

    private async _loadModel(modelId: string, adapterId?: string) {
        try {
            this._view?.webview.postMessage({ type: 'status', content: `Загружаю ${modelId}…` });

            const response = await fetch(`${this._serverUrl}/models/select`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ model_id: modelId, adapter_id: adapterId || null }),
            });

            if (!response.ok) throw new Error(await response.text());

            this._view?.webview.postMessage({ type: 'modelLoaded', modelId, adapterId });
            vscode.window.showInformationMessage(
                `IntelliCode Fabric: ${modelId} загружена${adapterId ? ' + адаптер' : ''}!`
            );
        } catch (error: any) {
            this._view?.webview.postMessage({ type: 'error', content: `Ошибка загрузки: ${error.message}` });
        }
    }

    private async _downloadModel(modelId: string) {
        try {
            this._view?.webview.postMessage({ type: 'status', content: `Скачиваю ${modelId}…` });

            const response = await fetch(`${this._serverUrl}/models/download`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ model_id: modelId }),
            });

            if (!response.ok) throw new Error(await response.text());
            this._view?.webview.postMessage({ type: 'modelDownloaded', modelId });
            vscode.window.showInformationMessage(`Модель ${modelId} скачана!`);
            await this._sendModelList();
        } catch (error: any) {
            this._view?.webview.postMessage({ type: 'error', content: `Ошибка скачивания: ${error.message}` });
        }
    }

    // ─── Custom Models ──────────────────────────────────────────

    private async _loadCustomModel(repo: string, name: string, quantization: string) {
        try {
            this._view?.webview.postMessage({ type: 'status', content: `Загружаю ${name}...` });

            const response = await fetch(`${this._serverUrl}/models/load-custom`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ repo, name, quantization }),
            });

            if (!response.ok) throw new Error(await response.text());
            const result = (await response.json()) as any;

            this._view?.webview.postMessage({
                type: 'modelLoaded',
                modelId: result.model_id || name.toLowerCase().replace(/ /g, '-'),
            });

            await this._sendModelList();
            vscode.window.showInformationMessage(`Своя модель ${name} загружена!`);
        } catch (error: any) {
            this._view?.webview.postMessage({ type: 'error', content: `Ошибка загрузки: ${error.message}` });
        }
    }

    private async _downloadCustomModel(repo: string, name: string, quantization: string) {
        try {
            this._view?.webview.postMessage({ type: 'status', content: `Скачиваю ${repo}...` });

            const response = await fetch(`${this._serverUrl}/models/download-custom`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ repo, name, quantization }),
            });

            if (!response.ok) throw new Error(await response.text());
            const result = (await response.json()) as any;

            this._view?.webview.postMessage({
                type: 'modelLoaded',
                modelId: result.model_id || name.toLowerCase().replace(/ /g, '-'),
            });

            await this._sendModelList();
            vscode.window.showInformationMessage(`Своя модель ${name} скачана и загружена!`);
        } catch (error: any) {
            this._view?.webview.postMessage({ type: 'error', content: `Ошибка: ${error.message}` });
        }
    }

    // ─── Adapters ──────────────────────────────────────────────

    private async _sendAdapterList() {
        try {
            const response = await fetch(`${this._serverUrl}/adapters`);
            const data = await response.json();
            this._view?.webview.postMessage({ type: 'adapterList', ...(data as any) });
        } catch (_e) {}
    }

    // ─── Fine-tune ──────────────────────────────────────────────

    private async _startFineTune(modelId: string, epochs: number,
                                  strategies: string[], extraParams: any = {}) {
        const workspaceFolders = vscode.workspace.workspaceFolders;
        if (!workspaceFolders) {
            this._view?.webview.postMessage({ type: 'error', content: 'Нет открытой папки проекта' });
            return;
        }
        try {
            const body: any = {
                project_path: workspaceFolders[0].uri.fsPath,
                model_id: modelId,
                epochs,
                strategies,
            };

            if (extraParams.learning_rate) body.learning_rate = extraParams.learning_rate;
            if (extraParams.batch_size) body.batch_size = extraParams.batch_size;
            if (extraParams.gradient_accumulation_steps) body.gradient_accumulation_steps = extraParams.gradient_accumulation_steps;
            if (extraParams.lora_r) body.lora_r = extraParams.lora_r;
            if (extraParams.lora_alpha) body.lora_alpha = extraParams.lora_alpha;
            if (extraParams.max_seq_length) body.max_seq_length = extraParams.max_seq_length;

            const response = await fetch(`${this._serverUrl}/fine-tune`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body),
            });
            if (!response.ok) throw new Error(await response.text());
        } catch (error: any) {
            this._view?.webview.postMessage({ type: 'error', content: `Ошибка запуска дообучения: ${error.message}` });
        }
    }

    private async _sendFtStatus() {
        try {
            const response = await fetch(`${this._serverUrl}/fine-tune/status`);
            const data = await response.json();
            this._view?.webview.postMessage({ type: 'ftStatus', status: data as any });
        } catch (_e) {}
    }

    // ─── Progress ──────────────────────────────────────────────

    private async _sendDownloadProgress(modelId: string) {
        try {
            const response = await fetch(`${this._serverUrl}/models/download-progress/${modelId}`);
            const data = await response.json();
            this._view?.webview.postMessage({ type: 'downloadProgress', modelId, ...(data as any) });
        } catch (_e) {}
    }

    // ─── Smart Code Insertion ───────────────────────────────────

    private async _insertCode(code: string, targetFile?: string, lineStart?: number, lineEnd?: number) {
        // Если указан целевой файл — открываем его и вставляем/заменяем
        if (targetFile) {
            const workspaceFolders = vscode.workspace.workspaceFolders;
            if (workspaceFolders) {
                // Normalize path separators
                const normalizedTarget = targetFile.replace(/\\/g, '/');

                // Пробуем разные варианты пути
                const candidates = [
                    vscode.Uri.joinPath(workspaceFolders[0].uri, normalizedTarget),
                    vscode.Uri.file(targetFile),
                ];

                // Also try finding the file in workspace by name
                const fileName = normalizedTarget.split('/').pop() || '';
                if (fileName) {
                    try {
                        const found = await vscode.workspace.findFiles(`**/${fileName}`, '**/node_modules/**', 5);
                        for (const f of found) {
                            if (f.fsPath.replace(/\\/g, '/').endsWith(normalizedTarget)) {
                                candidates.unshift(f); // prioritize exact path match
                            }
                        }
                        // Add all found files as fallback
                        candidates.push(...found);
                    } catch {}
                }

                for (const fullPath of candidates) {
                    try {
                        const doc = await vscode.workspace.openTextDocument(fullPath);
                        const editor = await vscode.window.showTextDocument(doc, {
                            viewColumn: vscode.ViewColumn.One,
                            preserveFocus: false,
                        });

                        if (lineStart && lineStart > 0) {
                            const startLine = Math.min(lineStart - 1, doc.lineCount - 1);

                            // Calculate end line for REPLACE
                            const codeLines = code.split('\n').length;
                            let endLine: number;
                            if (lineEnd && lineEnd > lineStart) {
                                // Explicit range given — replace those lines
                                endLine = Math.min(lineEnd - 1, doc.lineCount - 1);
                            } else {
                                // No explicit end — replace same number of lines as new code
                                endLine = Math.min(startLine + codeLines - 1, doc.lineCount - 1);
                            }

                            const range = new vscode.Range(
                                new vscode.Position(startLine, 0),
                                doc.lineAt(endLine).range.end,
                            );

                            await editor.edit(eb => {
                                eb.replace(range, code);
                            });

                            // Scroll to the replaced code
                            const revealPos = new vscode.Position(startLine, 0);
                            editor.revealRange(
                                new vscode.Range(revealPos, revealPos),
                                vscode.TextEditorRevealType.InCenter,
                            );
                        } else {
                            // No line info — insert at end
                            const lastLine = doc.lineCount - 1;
                            const lastChar = doc.lineAt(lastLine).text.length;
                            await editor.edit(eb => {
                                eb.insert(new vscode.Position(lastLine, lastChar), '\n\n' + code);
                            });
                        }
                        vscode.window.showInformationMessage(
                            `Code inserted into ${targetFile}${lineStart ? ` at line ${lineStart}` : ''}`,
                        );
                        return;
                    } catch {
                        continue;
                    }
                }

                // File not found — inform user
                vscode.window.showWarningMessage(
                    `File not found: ${targetFile}. Inserting in active editor.`,
                );
            }
        }

        // Fallback: вставка в активный редактор
        const editor = vscode.window.activeTextEditor;
        if (!editor) {
            const doc = await vscode.workspace.openTextDocument({ content: code });
            await vscode.window.showTextDocument(doc);
            return;
        }

        await editor.edit(eb => {
            if (editor.selection.isEmpty) {
                eb.insert(editor.selection.active, code);
            } else {
                eb.replace(editor.selection, code);
            }
        });
    }

    // ─── Smart Code Actions ─────────────────────────────────────

    /**
     * Compute modified file content by applying action+code to original.
     * Falls back to whole-file replacement when lineStart is absent.
     */
    private _computeModified(
        original: string,
        action: string,
        code: string,
        lineStart?: number,
        lineEnd?: number,
    ): string {
        if (action === 'add') {
            if (lineStart && lineStart > 0) {
                const lines = original.split('\n');
                lines.splice(Math.min(lineStart, lines.length), 0, code);
                return lines.join('\n');
            }
            return original + '\n\n' + code;
        }
        if (action === 'delete') {
            const lines = original.split('\n');
            const start = Math.max(0, (lineStart || 1) - 1);
            const end = Math.min((lineEnd || lineStart || 1), lines.length);
            lines.splice(start, end - start);
            return lines.join('\n');
        }
        // replace / insert / create — use lineStart..lineEnd range or whole file
        if (lineStart && lineStart > 0) {
            const lines = original.split('\n');
            const start = Math.max(0, lineStart - 1);
            const end = lineEnd != null ? Math.min(lineEnd, lines.length) : lines.length;
            lines.splice(start, end - start, ...code.split('\n'));
            return lines.join('\n');
        }
        return code; // whole-file replacement
    }

    /**
     * Show a virtual split-diff (icf-orig: vs icf-mod:) then immediately
     * prompt the user with Approve / Reject.
     * If approved, writes changes to disk via WorkspaceEdit and saves.
     * Returns true when changes were applied.
     */
    private async _showDiffAndApply(
        doc: vscode.TextDocument,
        action: string,
        code: string,
        lineStart?: number,
        lineEnd?: number,
    ): Promise<boolean> {
        const originalContent = doc.getText();
        const modifiedContent = this._computeModified(originalContent, action, code, lineStart, lineEnd);

        const scheme = `icf-${Date.now()}`;
        const d1 = vscode.workspace.registerTextDocumentContentProvider(
            `${scheme}-orig`,
            { provideTextDocumentContent: () => originalContent },
        );
        const d2 = vscode.workspace.registerTextDocumentContentProvider(
            `${scheme}-mod`,
            { provideTextDocumentContent: () => modifiedContent },
        );

        const fileName = doc.fileName.replace(/\\/g, '/').split('/').pop() || 'file';
        await vscode.commands.executeCommand(
            'vscode.diff',
            vscode.Uri.parse(`${scheme}-orig:${fileName}`),
            vscode.Uri.parse(`${scheme}-mod:${fileName}`),
            `IntelliCode: ${fileName} (Original ↔ Proposed)`,
        );

        const choice = await vscode.window.showWarningMessage(
            `Применить изменения в ${fileName}?`, 'Применить', 'Отклонить',
        );

        d1.dispose();
        d2.dispose();
        await vscode.commands.executeCommand('workbench.action.closeActiveEditor');

        if (choice !== 'Применить') {
            return false;
        }

        const edit = new vscode.WorkspaceEdit();
        edit.replace(
            doc.uri,
            new vscode.Range(new vscode.Position(0, 0), doc.lineAt(doc.lineCount - 1).range.end),
            modifiedContent,
        );
        await vscode.workspace.applyEdit(edit);
        await doc.save();
        vscode.window.showInformationMessage(`Изменения применены: ${fileName}`);
        return true;
    }

    private async _handleCodeAction(msg: any) {
        const { action, code, targetFile, lineStart, lineEnd } = msg;

        // No target file — work with the active editor
        if (!targetFile) {
            const editor = vscode.window.activeTextEditor;
            if (!editor) {
                const newDoc = await vscode.workspace.openTextDocument({ content: code });
                await vscode.window.showTextDocument(newDoc);
                return;
            }
            if (action === 'insert') {
                await editor.edit(eb => {
                    if (editor.selection.isEmpty) {
                        eb.insert(editor.selection.active, code);
                    } else {
                        eb.replace(editor.selection, code);
                    }
                });
            } else {
                await this._showDiffAndApply(editor.document, action, code, lineStart, lineEnd);
            }
            return;
        }

        if (action === 'create') {
            await this._createFile(targetFile, code);
            return;
        }

        const found = await this._findAndOpenFile(targetFile);
        if (!found) {
            vscode.window.showWarningMessage(
                `Файл "${targetFile}" не найден в проекте. Убедитесь, что файл существует.`,
            );
            return;
        }

        await this._showDiffAndApply(found.doc, action, code, lineStart, lineEnd);
    }
    /**
     * Find a file in workspace by path and return the opened document.
     */
    private async _findAndOpenFile(targetFile: string): Promise<{ doc: vscode.TextDocument } | null> {
        if (!targetFile) return null;
        const workspaceFolders = vscode.workspace.workspaceFolders;
        if (!workspaceFolders) return null;

        const normalizedTarget = targetFile.replace(/\\/g, '/');
        const candidates: vscode.Uri[] = [
            vscode.Uri.joinPath(workspaceFolders[0].uri, normalizedTarget),
            vscode.Uri.file(targetFile),
        ];

        // Search by filename
        const fileName = normalizedTarget.split('/').pop() || '';
        if (fileName) {
            try {
                const found = await vscode.workspace.findFiles(`**/${fileName}`, '**/node_modules/**', 5);
                for (const f of found) {
                    if (f.fsPath.replace(/\\/g, '/').endsWith(normalizedTarget)) {
                        candidates.unshift(f);
                    }
                }
                candidates.push(...found);
            } catch {}
        }

        for (const uri of candidates) {
            try {
                const doc = await vscode.workspace.openTextDocument(uri);
                return { doc };
            } catch { continue; }
        }

        vscode.window.showWarningMessage(`File not found: ${targetFile}`);
        return null;
    }

    // ─── Run Command in Terminal ────────────────────────────────

    private _runCommand(command: string) {
        const terminal = vscode.window.createTerminal({
            name: 'IntelliCode',
            cwd: vscode.workspace.workspaceFolders?.[0]?.uri?.fsPath,
        });
        terminal.show();
        // Send each line as a separate command
        const lines = command.split('\n').filter(l => l.trim());
        for (const line of lines) {
            terminal.sendText(line);
        }
    }

    // ─── Apply All Changes (batch file operations) ──────────────

    private async _applyAllChanges(changes: Array<{file: string, code: string, action: string}>) {
        if (!changes || !changes.length) return;

        const workspaceFolders = vscode.workspace.workspaceFolders;
        if (!workspaceFolders) return;

        let applied = 0;
        for (const change of changes) {
            try {
                const fullPath = path.join(workspaceFolders[0].uri.fsPath, change.file);

                if (change.action === 'create' || change.action === 'write') {
                    // Создаём директории если нужно
                    const dir = path.dirname(fullPath);
                    if (!fs.existsSync(dir)) {
                        fs.mkdirSync(dir, { recursive: true });
                    }
                    fs.writeFileSync(fullPath, change.code, 'utf-8');
                    applied++;
                } else if (change.action === 'edit') {
                    const uri = vscode.Uri.file(fullPath);
                    const doc = await vscode.workspace.openTextDocument(uri);
                    const editor = await vscode.window.showTextDocument(doc);
                    // Replace entire content
                    const fullRange = new vscode.Range(
                        new vscode.Position(0, 0),
                        doc.lineAt(doc.lineCount - 1).range.end,
                    );
                    await editor.edit(eb => eb.replace(fullRange, change.code));
                    applied++;
                }
            } catch (err: any) {
                vscode.window.showWarningMessage(`Failed to apply change to ${change.file}: ${err.message}`);
            }
        }

        if (applied > 0) {
            vscode.window.showInformationMessage(`Applied ${applied} file change(s)`);
        }
    }

    // ─── Create File ────────────────────────────────────────────

    private async _createFile(filePath: string, content: string) {
        const workspaceFolders = vscode.workspace.workspaceFolders;
        if (!workspaceFolders) return;

        try {
            const fullPath = path.join(workspaceFolders[0].uri.fsPath, filePath);
            const dir = path.dirname(fullPath);

            if (!fs.existsSync(dir)) {
                fs.mkdirSync(dir, { recursive: true });
            }

            fs.writeFileSync(fullPath, content, 'utf-8');

            // Open the created file
            const doc = await vscode.workspace.openTextDocument(vscode.Uri.file(fullPath));
            await vscode.window.showTextDocument(doc);

            vscode.window.showInformationMessage(`Created: ${filePath}`);
        } catch (err: any) {
            vscode.window.showErrorMessage(`Failed to create ${filePath}: ${err.message}`);
        }
    }

    // ─── Open File ──────────────────────────────────────────────

    private async _openFile(filePath: string, lineStart?: number) {
        const workspaceFolders = vscode.workspace.workspaceFolders;
        if (!workspaceFolders) return;

        try {
            const fullPath = path.join(workspaceFolders[0].uri.fsPath, filePath);
            const doc = await vscode.workspace.openTextDocument(vscode.Uri.file(fullPath));
            const editor = await vscode.window.showTextDocument(doc, { viewColumn: vscode.ViewColumn.One });

            if (lineStart && lineStart > 0) {
                const pos = new vscode.Position(lineStart - 1, 0);
                editor.revealRange(new vscode.Range(pos, pos), vscode.TextEditorRevealType.InCenter);
                editor.selection = new vscode.Selection(pos, pos);
            }
        } catch (err: any) {
            vscode.window.showWarningMessage(`Cannot open: ${filePath}`);
        }
    }

    // ─── Proposed Changes: Diff Preview & Apply ─────────────────

    /**
     * Show diff preview for a proposed change and prompt Approve/Reject.
     */
    private async _showProposedDiff(msg: any) {
        const { file: targetFile, code, action, lineStart, lineEnd } = msg;

        if (!targetFile) {
            const editor = vscode.window.activeTextEditor;
            if (!editor) {
                const newDoc = await vscode.workspace.openTextDocument({ content: code });
                await vscode.window.showTextDocument(newDoc, { viewColumn: vscode.ViewColumn.Beside });
                return;
            }
            await this._showDiffAndApply(editor.document, action || 'replace', code, lineStart, lineEnd);
            return;
        }

        const found = await this._findAndOpenFile(targetFile);
        if (!found) {
            const newDoc = await vscode.workspace.openTextDocument({
                content: code,
                language: this._langFromPath(targetFile),
            });
            await vscode.window.showTextDocument(newDoc, { viewColumn: vscode.ViewColumn.Beside });
            return;
        }

        await this._showDiffAndApply(found.doc, action || 'replace', code, lineStart, lineEnd);
    }

    /**
     * Apply a single proposed change — shows diff + Approve/Reject first.
     */
    private async _applyProposedChange(msg: any) {
        const { file: targetFile, code, action, lineStart, lineEnd } = msg;
        if (!targetFile) return;

        if (action === 'create') {
            await this._createFile(targetFile, code);
            this._notifyChangeApplied(msg, true);
            return;
        }

        const found = await this._findAndOpenFile(targetFile);
        if (!found) {
            vscode.window.showWarningMessage(`Файл "${targetFile}" не найден в проекте.`);
            this._notifyChangeApplied(msg, false);
            return;
        }

        const applied = await this._showDiffAndApply(found.doc, action, code, lineStart, lineEnd);
        this._notifyChangeApplied(msg, applied);
    }

    /**
     * Apply all proposed changes at once.
     */
    private async _applyAllProposed(changes: any[]) {
        if (!changes || !changes.length) return;

        let applied = 0;
        for (const change of changes) {
            try {
                await this._applyProposedChange(change);
                applied++;
            } catch (err: any) {
                vscode.window.showWarningMessage(`Failed to apply change to ${change.file}: ${err.message}`);
            }
        }

        if (applied > 0) {
            vscode.window.showInformationMessage(`Applied ${applied} of ${changes.length} proposed changes`);
        }
    }

    private _notifyChangeApplied(change: any, success: boolean) {
        this._view?.webview.postMessage({
            type: 'proposedChangeApplied',
            file: change.file,
            success,
        });
    }

    private _langFromPath(filePath: string): string {
        const ext = filePath.split('.').pop()?.toLowerCase() || '';
        const map: Record<string, string> = {
            ts: 'typescript', tsx: 'typescriptreact', js: 'javascript', jsx: 'javascriptreact',
            py: 'python', java: 'java', go: 'go', rs: 'rust', rb: 'ruby', php: 'php',
            html: 'html', css: 'css', scss: 'scss', json: 'json', yaml: 'yaml', yml: 'yaml',
            sql: 'sql', sh: 'shellscript', md: 'markdown', xml: 'xml',
        };
        return map[ext] || 'plaintext';
    }

    // ─── HTML ──────────────────────────────────────────────────

    private _getHtml(webview: vscode.Webview): string {
        const styleUri = webview.asWebviewUri(vscode.Uri.joinPath(this._extensionUri, 'media', 'sidebar.css'));
        const scriptUri = webview.asWebviewUri(vscode.Uri.joinPath(this._extensionUri, 'media', 'sidebar.js'));
        const nonce = this._nonce();

        return require('fs').readFileSync(
            require('path').join(__dirname, '..', 'media', 'sidebar.html'), 'utf8'
        )
            .replace('{{styleUri}}', styleUri.toString())
            .replace('{{scriptUri}}', scriptUri.toString())
            .replace('<script src="{{scriptUri}}"></script>',
                `<script nonce="${nonce}" src="${scriptUri}"></script>`);
    }

    private _nonce(): string {
        const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
        return Array.from({ length: 32 }, () => chars[Math.floor(Math.random() * chars.length)]).join('');
    }
}
