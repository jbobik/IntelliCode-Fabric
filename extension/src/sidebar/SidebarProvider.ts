import * as vscode from 'vscode';
import * as path from 'path';

export class SidebarProvider implements vscode.WebviewViewProvider {
    private _view?: vscode.WebviewView;
    private _serverUrl: string;
    private _pendingMessages: any[] = [];
    private _ftStatusInterval?: NodeJS.Timeout;

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
                case 'indexProject': vscode.commands.executeCommand('aiCodePartner.indexProject'); break;
                case 'fineTune': await this._startFineTune(msg.modelId, msg.epochs, msg.strategies); break;
                case 'getFtStatus':
                    await this._sendFtStatus();
                    break;
                case 'insertCode': this._insertCode(msg.code); break;
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

    // ─── Chat ─────────────────────────────────────────────────

    private async _handleChat(message: any) {
        try {
            const editor = vscode.window.activeTextEditor;
            const selectedCode = editor?.selection.isEmpty ? undefined : editor?.document.getText(editor.selection);
            const contextFile = editor?.document.fileName;

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
            });
        } catch (error: any) {
            this._view?.webview.postMessage({
                type: 'error',
                content: `${error.message}. Is the backend running? (cd backend && python server.py)`,
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
                content: 'Cannot connect to backend. Run : cd backend && python server.py',
            });
        }
    }

    private async _loadModel(modelId: string, adapterId?: string) {
        try {
            this._view?.webview.postMessage({ type: 'status', content: `Loading ${modelId}…` });

            const response = await fetch(`${this._serverUrl}/models/select`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ model_id: modelId, adapter_id: adapterId || null }),
            });

            if (!response.ok) throw new Error(await response.text());

            this._view?.webview.postMessage({ type: 'modelLoaded', modelId, adapterId });
            vscode.window.showInformationMessage(
                `AI Code Partner: ${modelId} loaded${adapterId ? ' + adapter' : ''}!`
            );
        } catch (error: any) {
            this._view?.webview.postMessage({ type: 'error', content: `Load failed: ${error.message}` });
        }
    }

    private async _downloadModel(modelId: string) {
        try {
            this._view?.webview.postMessage({ type: 'status', content: `Downloading ${modelId}… this may take a while.` });

            const response = await fetch(`${this._serverUrl}/models/download`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ model_id: modelId }),
            });

            if (!response.ok) throw new Error(await response.text());
            this._view?.webview.postMessage({ type: 'modelDownloaded', modelId });
            vscode.window.showInformationMessage(`Model ${modelId} downloaded!`);
            await this._sendModelList();
        } catch (error: any) {
            this._view?.webview.postMessage({ type: 'error', content: `Download failed: ${error.message}` });
        }
    }

    // ─── Custom Models ─────────────────────────────────────────

    private async _loadCustomModel(repo: string, name: string, quantization: string) {
        try {
            this._view?.webview.postMessage({
                type: 'status',
                content: `Loading ${name}...`,
            });

            const response = await fetch(`${this._serverUrl}/models/load-custom`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ repo, name, quantization }),
            });

            if (!response.ok) {
                throw new Error(await response.text());
            }

            const result = (await response.json()) as any;

            this._view?.webview.postMessage({
                type: 'modelLoaded',
                modelId: result.model_id || name,
            });

            vscode.window.showInformationMessage(`Custom model ${name} loaded!`);
        } catch (error: any) {
            this._view?.webview.postMessage({
                type: 'error',
                content: `Failed to load custom model: ${error.message}`,
            });
        }
    }

    private async _downloadCustomModel(repo: string, name: string, quantization: string) {
        try {
            this._view?.webview.postMessage({
                type: 'status',
                content: `Downloading ${repo}...`,
            });

            const response = await fetch(`${this._serverUrl}/models/download-custom`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ repo, name, quantization }),
            });

            if (!response.ok) {
                throw new Error(await response.text());
            }

            this._view?.webview.postMessage({
                type: 'modelLoaded',
                modelId: name,
            });

            vscode.window.showInformationMessage(`Custom model ${name} downloaded and loaded!`);
            await this._sendModelList();
        } catch (error: any) {
            this._view?.webview.postMessage({
                type: 'error',
                content: `Failed: ${error.message}`,
            });
        }
    }

    // ─── Adapters ──────────────────────────────────────────────

    private async _sendAdapterList() {
        try {
            const response = await fetch(`${this._serverUrl}/adapters`);
            const data = await response.json();
            this._view?.webview.postMessage({
                type: 'adapterList',
                ...(data as any),
            });
        } catch (_e) {}
    }

    // ─── Fine-tune ─────────────────────────────────────────────

    private async _startFineTune(modelId: string, epochs: number, strategies: string[]) {
        const workspaceFolders = vscode.workspace.workspaceFolders;
        if (!workspaceFolders) {
            this._view?.webview.postMessage({ type: 'error', content: 'No workspace folder open' });
            return;
        }

        try {
            const response = await fetch(`${this._serverUrl}/fine-tune`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    project_path: workspaceFolders[0].uri.fsPath,
                    model_id: modelId,
                    epochs,
                    strategies,
                }),
            });

            if (!response.ok) throw new Error(await response.text());
        } catch (error: any) {
            this._view?.webview.postMessage({ type: 'error', content: `Fine-tune start failed: ${error.message}` });
        }
    }

    private async _sendFtStatus() {
        try {
            const response = await fetch(`${this._serverUrl}/fine-tune/status`);
            const data = await response.json();
            this._view?.webview.postMessage({
                type: 'ftStatus',
                status: data as any,
            });
        } catch (_e) {}
    }

    // ─── Progress ──────────────────────────────────────────────

    private async _sendDownloadProgress(modelId: string) {
        try {
            const response = await fetch(`${this._serverUrl}/models/download-progress/${modelId}`);
            const data = await response.json();
            this._view?.webview.postMessage({
                type: 'downloadProgress',
                modelId,
                ...(data as any),
            });
        } catch (_e) {}
    }

    // ─── Code ──────────────────────────────────────────────────

    private _insertCode(code: string) {
        const editor = vscode.window.activeTextEditor;
        if (!editor) return;
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

        // Read template and replace placeholders
        return require('fs').readFileSync(
            require('path').join(__dirname, '..', 'media', 'sidebar.html'), 'utf8'
        )
            .replace('{{styleUri}}', styleUri.toString())
            .replace('{{scriptUri}}', scriptUri.toString())
            // Add nonce to script tag
            .replace('<script src="{{scriptUri}}"></script>',
                `<script nonce="${nonce}" src="${scriptUri}"></script>`);
    }

    private _nonce(): string {
        const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
        return Array.from({ length: 32 }, () => chars[Math.floor(Math.random() * chars.length)]).join('');
    }
}