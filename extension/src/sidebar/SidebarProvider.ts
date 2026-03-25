import * as vscode from 'vscode';
import * as path from 'path';
import * as fs from 'fs';

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

    public resolveWebviewView(
        webviewView: vscode.WebviewView,
        _context: vscode.WebviewViewResolveContext,
        _token: vscode.CancellationToken
    ) {
        this._view = webviewView;

        webviewView.webview.options = {
            enableScripts: true,
            localResourceRoots: [
                vscode.Uri.joinPath(this._extensionUri, 'media'),
            ],
        };

        webviewView.webview.html = this._getHtml(webviewView.webview);

        webviewView.webview.onDidReceiveMessage(async (message) => {
            switch (message.type) {
                case 'chat':
                    await this._handleChat(message);
                    break;
                case 'selectModel':
                    vscode.commands.executeCommand('aiCodePartner.selectModel');
                    break;
                case 'downloadModel':
                    vscode.commands.executeCommand('aiCodePartner.downloadModel');
                    break;
                case 'indexProject':
                    vscode.commands.executeCommand('aiCodePartner.indexProject');
                    break;
                case 'getModels':
                    await this._sendModelList();
                    break;
                case 'loadModel':
                    await this._loadModel(message.modelId);
                    break;
                case 'startDownload':
                    await this._downloadModel(message.modelId);
                    break;
                case 'insertCode':
                    this._insertCode(message.code);
                    break;
                case 'applyEdit':
                    await this._applyEdit(message);
                    break;
                case 'fineTune':
                    vscode.commands.executeCommand('aiCodePartner.fineTune');
                    break;
            }
        });

        for (const msg of this._pendingMessages) {
            webviewView.webview.postMessage(msg);
        }
        this._pendingMessages = [];
    }

    public sendMessage(message: any) {
        if (this._view) {
            this._view.webview.postMessage(message);
        } else {
            this._pendingMessages.push(message);
        }
    }

    private async _handleChat(message: any) {
        try {
            const editor = vscode.window.activeTextEditor;
            const selectedCode = editor?.selection.isEmpty
                ? undefined
                : editor?.document.getText(editor.selection);
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

            if (!response.ok) {
                const errorText = await response.text();
                throw new Error(errorText);
            }

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
                content: `Error: ${error.message}. Make sure the backend server is running.`,
            });
        }
    }

    private async _sendModelList() {
        try {
            const response = await fetch(`${this._serverUrl}/models`);
            const data = await response.json();
            this._view?.webview.postMessage({
                type: 'modelList',
                ...(data as any),
            });
        } catch (_error: any) {
            this._view?.webview.postMessage({
                type: 'error',
                content: 'Cannot connect to backend server. Please start it first.',
            });
        }
    }

    private async _loadModel(modelId: string) {
        try {
            this._view?.webview.postMessage({
                type: 'status',
                content: `Loading model ${modelId}...`,
            });

            const response = await fetch(`${this._serverUrl}/models/select`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ model_id: modelId }),
            });

            if (!response.ok) {
                throw new Error(await response.text());
            }

            this._view?.webview.postMessage({
                type: 'modelLoaded',
                modelId: modelId,
            });

            vscode.window.showInformationMessage(`Model ${modelId} loaded successfully!`);
        } catch (error: any) {
            this._view?.webview.postMessage({
                type: 'error',
                content: `Failed to load model: ${error.message}`,
            });
        }
    }

    private async _downloadModel(modelId: string) {
        try {
            this._view?.webview.postMessage({
                type: 'status',
                content: `Downloading model ${modelId}... This may take a while.`,
            });

            const response = await fetch(`${this._serverUrl}/models/download`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ model_id: modelId }),
            });

            if (!response.ok) {
                throw new Error(await response.text());
            }

            this._view?.webview.postMessage({
                type: 'modelDownloaded',
                modelId: modelId,
            });

            vscode.window.showInformationMessage(`Model ${modelId} downloaded!`);
            await this._sendModelList();
        } catch (error: any) {
            this._view?.webview.postMessage({
                type: 'error',
                content: `Download failed: ${error.message}`,
            });
        }
    }

    private _insertCode(code: string) {
        const editor = vscode.window.activeTextEditor;
        if (editor) {
            editor.edit((editBuilder) => {
                if (editor.selection.isEmpty) {
                    editBuilder.insert(editor.selection.active, code);
                } else {
                    editBuilder.replace(editor.selection, code);
                }
            });
        }
    }

    private async _applyEdit(message: any) {
        const editor = vscode.window.activeTextEditor;
        if (!editor) { return; }

        const { code, lineStart, lineEnd } = message;
        const range = new vscode.Range(
            new vscode.Position(lineStart - 1, 0),
            new vscode.Position(lineEnd, 0)
        );

        await editor.edit((editBuilder) => {
            editBuilder.replace(range, code + '\n');
        });

        vscode.window.showInformationMessage('Edit applied!');
    }

    private _getHtml(webview: vscode.Webview): string {
        const styleUri = webview.asWebviewUri(
            vscode.Uri.joinPath(this._extensionUri, 'media', 'sidebar.css')
        );
        const scriptUri = webview.asWebviewUri(
            vscode.Uri.joinPath(this._extensionUri, 'media', 'sidebar.js')
        );
        const nonce = getNonce();

        return `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="Content-Security-Policy"
          content="default-src 'none';
                   style-src ${webview.cspSource} 'unsafe-inline';
                   script-src 'nonce-${nonce}';
                   connect-src *;">
    <link rel="stylesheet" href="${styleUri}">
    <title>AI Code Partner</title>
</head>
<body>
    <div class="header">
        <div class="header-row">
            <h3>AI Code Partner</h3>
        </div>
        <div class="model-selector">
            <label class="label-small">Model:</label>
            <select class="model-select" id="modelSelect">
                <option value="">Loading models...</option>
            </select>
        </div>
        <div class="header-buttons">
            <button class="btn-small btn-primary" id="loadModelBtn">Load</button>
            <button class="btn-small" id="downloadModelBtn">Download</button>
            <button class="btn-small" id="indexBtn">Index</button>
            <button class="btn-small" id="finetuneBtn">Fine-tune</button>
            <button class="btn-small" id="clearBtn">Clear</button>
        </div>
    </div>

    <div class="status-bar">
        <div class="status-dot" id="statusDot"></div>
        <span id="statusText">Connecting...</span>
    </div>

    <div class="chat-container" id="chatContainer">
        <div class="welcome" id="welcome">
            <h2>Welcome to AI Code Partner</h2>
            <p>Your local AI coding assistant with RAG and multi-agent system.</p>
            <ol class="steps">
                <li>Start the backend server</li>
                <li>Select and load a model above</li>
                <li>Click Index to scan your project</li>
                <li>Start chatting about your code!</li>
            </ol>
        </div>
    </div>

    <div class="input-container">
        <div class="input-wrapper">
            <textarea class="chat-input" id="chatInput"
                placeholder="Ask about your code... (Enter to send)"
                rows="1"></textarea>
            <button class="send-btn" id="sendBtn">Send</button>
        </div>
        <div class="quick-actions">
            <button class="quick-action" data-prompt="Where is authentication implemented?">Find auth</button>
            <button class="quick-action" data-prompt="Explain the architecture of this project">Architecture</button>
            <button class="quick-action" data-prompt="Find potential bugs or issues">Find bugs</button>
            <button class="quick-action" data-prompt="Suggest improvements for code quality">Improve</button>
        </div>
    </div>

    <script nonce="${nonce}" src="${scriptUri}"></script>
</body>
</html>`;
    }
}

function getNonce(): string {
    let text = '';
    const possible = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
    for (let i = 0; i < 32; i++) {
        text += possible.charAt(Math.floor(Math.random() * possible.length));
    }
    return text;
}