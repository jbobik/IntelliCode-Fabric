import * as vscode from 'vscode';
import * as path from 'path';

export class SidebarProvider implements vscode.WebviewViewProvider {
    private _view?: vscode.WebviewView;
    private _serverUrl: string;
    private _pendingMessages: any[] = [];

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
                case 'insertCode': this._insertCode(msg.code, msg.targetFile); break;
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

    // ─── Chat ─────────────────────────────────────────────────────────────────

    private async _handleChat(message: any) {
        try {
            const editor = vscode.window.activeTextEditor;
            const selectedCode = editor?.selection.isEmpty ? undefined : editor?.document.getText(editor.selection);
            const contextFile = editor?.document.fileName;

            // Показываем статус "агент думает..."
            this._view?.webview.postMessage({
                type: 'status',
                content: '🔍 Анализирую запрос и ищу контекст в проекте...',
            });

            const response = await fetch(`${this._serverUrl}/chat`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    message: message.content,
                    selected_code: selectedCode,
                    context_file: contextFile,
                    conversation_history: message.history || [],
                }),
            });

            if (!response.ok) throw new Error(await response.text());
            const result = (await response.json()) as any;

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
            });
        } catch (error: any) {
            this._view?.webview.postMessage({
                type: 'error',
                content: `${error.message}. Запущен ли бэкенд? (cd backend && python server.py)`,
            });
        }
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

    // ─── Custom Models (FIX: properly update status) ──────────

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

            // FIX: Send modelLoaded with the correct model ID
            this._view?.webview.postMessage({
                type: 'modelLoaded',
                modelId: result.model_id || name.toLowerCase().replace(/ /g, '-'),
            });

            // Refresh model list so custom model appears in picker
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

            // FIX: Send modelLoaded with correct model ID
            this._view?.webview.postMessage({
                type: 'modelLoaded',
                modelId: result.model_id || name.toLowerCase().replace(/ /g, '-'),
            });

            // Refresh model list
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

    // ─── Fine-tune (with extended params) ──────────────────────

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

            // Add extended params if provided
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
            // No error = background task started successfully
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

    // ─── Code (improved: insert at selection or cursor) ───────

    private async _insertCode(code: string, targetFile?: string) {
        // Если указан целевой файл — открываем его
        if (targetFile) {
            const workspaceFolders = vscode.workspace.workspaceFolders;
            if (workspaceFolders) {
                const fullPath = vscode.Uri.joinPath(workspaceFolders[0].uri, targetFile);
                try {
                    const doc = await vscode.workspace.openTextDocument(fullPath);
                    const editor = await vscode.window.showTextDocument(doc, { 
                        viewColumn: vscode.ViewColumn.One 
                    });
                    // Вставляем в конец файла
                    const lastLine = doc.lineCount - 1;
                    const lastChar = doc.lineAt(lastLine).text.length;
                    editor.edit(eb => {
                        eb.insert(new vscode.Position(lastLine, lastChar), '\n\n' + code);
                    });
                    return;
                } catch {
                    // Файл не найден — fallback к обычной вставке
                }
            }
        }

        // Fallback: вставка в активный редактор
        const editor = vscode.window.activeTextEditor;
        if (!editor) {
            // Нет открытого редактора — открываем новый документ
            const doc = await vscode.workspace.openTextDocument({ content: code });
            await vscode.window.showTextDocument(doc);
            return;
        }
        
        editor.edit(eb => {
            if (editor.selection.isEmpty) {
                eb.insert(editor.selection.active, code);
            } else {
                eb.replace(editor.selection, code);
            }
        });
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