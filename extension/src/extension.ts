import * as vscode from 'vscode';
import { SidebarProvider } from './sidebar/SidebarProvider';
import { InlineEditProvider } from './inline/InlineEditProvider';
import { ModelManager } from './models/ModelManager';
import * as child_process from 'child_process';
import * as path from 'path';

let serverProcess: child_process.ChildProcess | null = null;

export function activate(context: vscode.ExtensionContext) {
    console.log('AI Code Partner is activating...');

    const serverUrl = vscode.workspace.getConfiguration('intelliCodeFabric').get<string>('serverUrl') || 'http://127.0.0.1:8765';

    // Initialize providers
    const sidebarProvider = new SidebarProvider(context.extensionUri, serverUrl);
    const inlineEditProvider = new InlineEditProvider(serverUrl);
    const modelManager = new ModelManager(serverUrl);

    // Register sidebar
    context.subscriptions.push(
        vscode.window.registerWebviewViewProvider('intelliCodeFabric.sidebar', sidebarProvider)
    );

    // Register commands
    context.subscriptions.push(
        vscode.commands.registerCommand('intelliCodeFabric.startServer', () => startServer(context)),
        vscode.commands.registerCommand('intelliCodeFabric.indexProject', () => indexProject(serverUrl)),
        vscode.commands.registerCommand('intelliCodeFabric.chat', () => {
            vscode.commands.executeCommand('intelliCodeFabric.sidebar.focus');
        }),
        vscode.commands.registerCommand('intelliCodeFabric.generateCode', () => handleGenerateCode(serverUrl)),
        vscode.commands.registerCommand('intelliCodeFabric.refactorCode', () => handleRefactorCode(serverUrl)),
        vscode.commands.registerCommand('intelliCodeFabric.generateTests', () => handleGenerateTests(serverUrl)),
        vscode.commands.registerCommand('intelliCodeFabric.explainCode', () => handleExplainCode(serverUrl, sidebarProvider)),
        vscode.commands.registerCommand('intelliCodeFabric.inlineEdit', () => inlineEditProvider.triggerInlineEdit()),
        vscode.commands.registerCommand('intelliCodeFabric.selectModel', () => modelManager.showModelPicker()),
        vscode.commands.registerCommand('intelliCodeFabric.downloadModel', () => modelManager.showDownloadPicker()),
        vscode.commands.registerCommand('intelliCodeFabric.fineTune', () => handleFineTune(serverUrl)),
    );

    // Auto-index on startup
    const autoIndex = vscode.workspace.getConfiguration('intelliCodeFabric').get<boolean>('autoIndex');
    if (autoIndex) {
        // Delay to let server start
        setTimeout(() => {
            indexProject(serverUrl).catch(() => { /* server might not be running yet */ });
        }, 5000);
    }

    // Status bar
    const statusBar = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 100);
    statusBar.text = '$(hubot) AI Partner';
    statusBar.command = 'intelliCodeFabric.chat';
    statusBar.tooltip = 'Open AI Code Partner';
    statusBar.show();
    context.subscriptions.push(statusBar);

    vscode.window.showInformationMessage('AI Code Partner activated! Use Ctrl+Shift+A to open chat.');
}

async function startServer(context: vscode.ExtensionContext) {
    const pythonPath = vscode.workspace.getConfiguration('intelliCodeFabric').get<string>('pythonPath') || 'python';
    const serverScript = path.join(context.extensionPath, '..', 'backend', 'server.py');

    if (serverProcess) {
        serverProcess.kill();
        serverProcess = null;
    }

    const terminal = vscode.window.createTerminal({
        name: 'AI Code Partner Server',
        shellPath: pythonPath,
        shellArgs: [serverScript],
        cwd: path.join(context.extensionPath, '..', 'backend'),
    });
    terminal.show();

    vscode.window.showInformationMessage('AI Code Partner server starting...');
}

async function indexProject(serverUrl: string) {
    const workspaceFolders = vscode.workspace.workspaceFolders;
    if (!workspaceFolders) {
        vscode.window.showWarningMessage('No workspace folder open');
        return;
    }

    const projectPath = workspaceFolders[0].uri.fsPath;

    try {
        vscode.window.withProgress(
            {
                location: vscode.ProgressLocation.Notification,
                title: 'AI Code Partner: Indexing project...',
                cancellable: false,
            },
            async (progress) => {
                progress.report({ increment: 0, message: 'Scanning files...' });

                const response = await fetch(`${serverUrl}/index`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ project_path: projectPath }),
                });

                if (!response.ok) {
                    throw new Error(`Indexing failed: ${response.statusText}`);
                }

                const result = await response.json() as any;
                progress.report({ increment: 100, message: 'Done!' });

                vscode.window.showInformationMessage(
                    `Indexed ${result.stats.total_files} files (${result.stats.total_chunks} chunks)`
                );
            }
        );
    } catch (error: any) {
        vscode.window.showErrorMessage(`Indexing failed: ${error.message}. Is the backend server running?`);
    }
}

async function handleGenerateCode(serverUrl: string) {
    const editor = vscode.window.activeTextEditor;
    const selectedCode = editor?.document.getText(editor.selection) || '';

    const prompt = await vscode.window.showInputBox({
        prompt: 'What code should I generate?',
        placeHolder: 'e.g., "Add error handling and retry logic to this function"',
    });

    if (!prompt) { return; }

    try {
        vscode.window.withProgress(
            {
                location: vscode.ProgressLocation.Notification,
                title: 'AI Code Partner: Generating code...',
                cancellable: false,
            },
            async () => {
                const response = await fetch(`${serverUrl}/generate`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        prompt: prompt,
                        selected_code: selectedCode,
                        file_path: editor?.document.fileName,
                    }),
                });

                const result = await response.json() as any;

                // Show in new editor
                const doc = await vscode.workspace.openTextDocument({
                    content: result.generated_code || result.response || 'No code generated',
                    language: editor?.document.languageId || 'plaintext',
                });
                await vscode.window.showTextDocument(doc, { viewColumn: vscode.ViewColumn.Beside });
            }
        );
    } catch (error: any) {
        vscode.window.showErrorMessage(`Generation failed: ${error.message}`);
    }
}

async function handleRefactorCode(serverUrl: string) {
    const editor = vscode.window.activeTextEditor;
    if (!editor || editor.selection.isEmpty) {
        vscode.window.showWarningMessage('Please select code to refactor');
        return;
    }

    const selectedCode = editor.document.getText(editor.selection);

    const instruction = await vscode.window.showInputBox({
        prompt: 'How should I refactor this code?',
        placeHolder: 'e.g., "Apply Strategy pattern" or "Add error handling"',
    });

    if (!instruction) { return; }

    try {
        vscode.window.withProgress(
            {
                location: vscode.ProgressLocation.Notification,
                title: 'AI Code Partner: Refactoring...',
                cancellable: false,
            },
            async () => {
                const response = await fetch(`${serverUrl}/refactor`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        code: selectedCode,
                        file_path: editor.document.fileName,
                        instruction: instruction,
                    }),
                });

                const result = await response.json() as any;

                if (result.refactored_code) {
                    // Show diff
                    const original = await vscode.workspace.openTextDocument({
                        content: selectedCode,
                        language: editor.document.languageId,
                    });
                    const refactored = await vscode.workspace.openTextDocument({
                        content: result.refactored_code,
                        language: editor.document.languageId,
                    });

                    await vscode.commands.executeCommand(
                        'vscode.diff',
                        original.uri,
                        refactored.uri,
                        'Original ↔ Refactored'
                    );

                    // Offer to apply
                    const apply = await vscode.window.showInformationMessage(
                        'Apply refactored code?',
                        'Apply',
                        'Cancel'
                    );

                    if (apply === 'Apply') {
                        await editor.edit((editBuilder) => {
                            editBuilder.replace(editor.selection, result.refactored_code);
                        });
                        vscode.window.showInformationMessage('Refactored code applied!');
                    }
                }
            }
        );
    } catch (error: any) {
        vscode.window.showErrorMessage(`Refactoring failed: ${error.message}`);
    }
}

async function handleGenerateTests(serverUrl: string) {
    const editor = vscode.window.activeTextEditor;
    if (!editor || editor.selection.isEmpty) {
        vscode.window.showWarningMessage('Please select code to generate tests for');
        return;
    }

    const selectedCode = editor.document.getText(editor.selection);

    try {
        vscode.window.withProgress(
            {
                location: vscode.ProgressLocation.Notification,
                title: 'AI Code Partner: Generating tests...',
                cancellable: false,
            },
            async () => {
                const response = await fetch(`${serverUrl}/chat`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        message: 'Generate comprehensive unit tests for this code',
                        selected_code: selectedCode,
                        context_file: editor.document.fileName,
                    }),
                });

                const result = await response.json() as any;

                const doc = await vscode.workspace.openTextDocument({
                    content: result.code || result.response,
                    language: editor.document.languageId,
                });
                await vscode.window.showTextDocument(doc, { viewColumn: vscode.ViewColumn.Beside });
            }
        );
    } catch (error: any) {
        vscode.window.showErrorMessage(`Test generation failed: ${error.message}`);
    }
}

async function handleExplainCode(serverUrl: string, sidebarProvider: SidebarProvider) {
    const editor = vscode.window.activeTextEditor;
    if (!editor || editor.selection.isEmpty) {
        vscode.window.showWarningMessage('Please select code to explain');
        return;
    }

    const selectedCode = editor.document.getText(editor.selection);

    // Send to sidebar chat
    sidebarProvider.sendMessage({
        type: 'explain',
        code: selectedCode,
        file: editor.document.fileName,
    });

    vscode.commands.executeCommand('intelliCodeFabric.sidebar.focus');
}

async function handleFineTune(serverUrl: string) {
    const workspaceFolders = vscode.workspace.workspaceFolders;
    if (!workspaceFolders) {
        vscode.window.showWarningMessage('No workspace folder open');
        return;
    }

    const confirm = await vscode.window.showWarningMessage(
        'Fine-tuning will train the model on your project code. This may take a while. Continue?',
        'Start Fine-tuning',
        'Cancel'
    );

    if (confirm !== 'Start Fine-tuning') { return; }

    try {
        vscode.window.withProgress(
            {
                location: vscode.ProgressLocation.Notification,
                title: 'AI Code Partner: Fine-tuning...',
                cancellable: false,
            },
            async (progress) => {
                progress.report({ message: 'Starting fine-tuning...' });

                const response = await fetch(`${serverUrl}/fine-tune`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        project_path: workspaceFolders[0].uri.fsPath,
                    }),
                });

                const result = await response.json() as any;

                if (result.status === 'ok') {
                    vscode.window.showInformationMessage(
                        `Fine-tuning complete! Trained on ${result.num_examples} examples.`
                    );
                } else {
                    vscode.window.showErrorMessage(`Fine-tuning failed: ${result.message}`);
                }
            }
        );
    } catch (error: any) {
        vscode.window.showErrorMessage(`Fine-tuning failed: ${error.message}`);
    }
}

export function deactivate() {
    if (serverProcess) {
        serverProcess.kill();
    }
}