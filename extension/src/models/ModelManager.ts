import * as vscode from 'vscode';

interface ModelInfo {
    id: string;
    name: string;
    repo: string;
    type: string;
    quantization: string;
    ram_required: string;
    description: string;
    downloaded: boolean;
    active: boolean;
}

export class ModelManager {
    private _serverUrl: string;

    constructor(serverUrl: string) {
        this._serverUrl = serverUrl;
    }

    async showModelPicker() {
        try {
            const response = await fetch(`${this._serverUrl}/models`);
            const data = await response.json() as { models: ModelInfo[] };

            const items: vscode.QuickPickItem[] = data.models.map((m) => ({
                label: `${m.active ? '✅ ' : ''}${m.downloaded ? '📦 ' : '☁️ '}${m.name}`,
                description: m.ram_required,
                detail: m.description,
                picked: m.active,
            }));

            const selected = await vscode.window.showQuickPick(items, {
                placeHolder: 'Select a model to load',
                title: 'AI Code Partner — Model Selection',
            });

            if (selected) {
                const model = data.models.find(
                    (m) => selected.label.includes(m.name)
                );
                if (model) {
                    if (!model.downloaded) {
                        const download = await vscode.window.showInformationMessage(
                            `Model ${model.name} needs to be downloaded first. Download now?`,
                            'Download & Load',
                            'Cancel'
                        );
                        if (download === 'Download & Load') {
                            await this._downloadAndLoad(model.id);
                        }
                    } else {
                        await this._loadModel(model.id);
                    }
                }
            }
        } catch (error: any) {
            vscode.window.showErrorMessage(`Failed to get model list: ${error.message}`);
        }
    }

    async showDownloadPicker() {
        try {
            const response = await fetch(`${this._serverUrl}/models`);
            const data = await response.json() as { models: ModelInfo[] };

            const notDownloaded = data.models.filter((m) => !m.downloaded);

            if (notDownloaded.length === 0) {
                vscode.window.showInformationMessage('All models are already downloaded!');
                return;
            }

            const items: vscode.QuickPickItem[] = notDownloaded.map((m) => ({
                label: m.name,
                description: `${m.ram_required} | ${m.quantization}`,
                detail: m.description,
            }));

            const selected = await vscode.window.showQuickPick(items, {
                placeHolder: 'Select a model to download',
                title: 'Download Model',
            });

            if (selected) {
                const model = notDownloaded.find((m) => m.name === selected.label);
                if (model) {
                    await this._downloadModel(model.id);
                }
            }
        } catch (error: any) {
            vscode.window.showErrorMessage(`Failed to get model list: ${error.message}`);
        }
    }

    private async _loadModel(modelId: string) {
        await vscode.window.withProgress(
            {
                location: vscode.ProgressLocation.Notification,
                title: `Loading model ${modelId}...`,
                cancellable: false,
            },
            async () => {
                const response = await fetch(`${this._serverUrl}/models/select`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ model_id: modelId }),
                });

                if (!response.ok) {
                    throw new Error(await response.text());
                }

                vscode.window.showInformationMessage(`Model ${modelId} loaded!`);
            }
        );
    }

    private async _downloadModel(modelId: string) {
        await vscode.window.withProgress(
            {
                location: vscode.ProgressLocation.Notification,
                title: `Downloading model ${modelId}...`,
                cancellable: false,
            },
            async () => {
                const response = await fetch(`${this._serverUrl}/models/download`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ model_id: modelId }),
                });

                if (!response.ok) {
                    throw new Error(await response.text());
                }

                vscode.window.showInformationMessage(`Model ${modelId} downloaded!`);
            }
        );
    }

    private async _downloadAndLoad(modelId: string) {
        await this._downloadModel(modelId);
        await this._loadModel(modelId);
    }
}