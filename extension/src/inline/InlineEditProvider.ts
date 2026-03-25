import * as vscode from 'vscode';

export class InlineEditProvider {
    private _serverUrl: string;

    constructor(serverUrl: string) {
        this._serverUrl = serverUrl;
    }

    async triggerInlineEdit() {
        const editor = vscode.window.activeTextEditor;
        if (!editor || editor.selection.isEmpty) {
            vscode.window.showWarningMessage('Please select code for inline editing');
            return;
        }

        const instruction = await vscode.window.showInputBox({
            prompt: 'What change should I make to this code?',
            placeHolder: 'e.g., "Add error handling" or "Optimize this loop"',
        });

        if (!instruction) { return; }

        const selectedCode = editor.document.getText(editor.selection);
        const lineStart = editor.selection.start.line + 1;
        const lineEnd = editor.selection.end.line + 1;

        try {
            const response = await vscode.window.withProgress(
                {
                    location: vscode.ProgressLocation.Notification,
                    title: 'AI Code Partner: Editing...',
                    cancellable: false,
                },
                async () => {
                    const resp = await fetch(`${this._serverUrl}/inline-edit`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            file_path: editor.document.fileName,
                            code: selectedCode,
                            instruction: instruction,
                            line_start: lineStart,
                            line_end: lineEnd,
                        }),
                    });

                    if (!resp.ok) {
                        throw new Error(await resp.text());
                    }

                    return await resp.json() as any;
                }
            );

            if (response.edited_code) {
                // Show inline diff using decorations
                await this._showInlineDiff(editor, response);
            }
        } catch (error: any) {
            vscode.window.showErrorMessage(`Inline edit failed: ${error.message}`);
        }
    }

    private async _showInlineDiff(editor: vscode.TextEditor, response: any) {
        const { edited_code, original_code, explanation } = response;

        // Show diff view
        const originalDoc = await vscode.workspace.openTextDocument({
            content: original_code,
            language: editor.document.languageId,
        });

        const editedDoc = await vscode.workspace.openTextDocument({
            content: edited_code,
            language: editor.document.languageId,
        });

        await vscode.commands.executeCommand(
            'vscode.diff',
            originalDoc.uri,
            editedDoc.uri,
            `Inline Edit: ${explanation || 'Review changes'}`
        );

        // Offer to apply
        const action = await vscode.window.showInformationMessage(
            `${explanation || 'Review the changes'}`,
            'Apply Changes',
            'Cancel'
        );

        if (action === 'Apply Changes') {
            await editor.edit((editBuilder) => {
                editBuilder.replace(editor.selection, edited_code);
            });
            vscode.window.showInformationMessage('Changes applied!');
        }
    }
}