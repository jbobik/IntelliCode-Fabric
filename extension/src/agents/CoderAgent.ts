/**
 * CoderAgent — агент-кодер.
 * Генерирует код, реализует функции, выполняет inline-редактирование.
 * Учитывает контекст проекта и существующие конвенции.
 */

import { AgentResponse } from './AgentOrchestrator';

export interface InlineEditResult {
    original_code: string;
    edited_code: string;
    explanation: string;
    file_path: string;
    line_start: number;
    line_end: number;
}

export interface GenerationResult extends AgentResponse {
    generated_code?: string;
    context_files?: string[];
}

export class CoderAgent {
    private serverUrl: string;

    constructor(serverUrl: string) {
        this.serverUrl = serverUrl;
    }

    /**
     * Генерирует код на основе промпта с учётом контекста проекта.
     */
    async generate(
        prompt: string,
        selectedCode?: string,
        contextFile?: string
    ): Promise<GenerationResult> {
        const response = await fetch(`${this.serverUrl}/generate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                prompt,
                selected_code: selectedCode,
                file_path: contextFile,
                instruction: 'generate',
            }),
        });

        if (!response.ok) {
            throw new Error(`Generation failed: ${response.statusText}`);
        }

        const result = (await response.json()) as any;

        return {
            response: result.generated_code || result.response || '',
            code: result.generated_code,
            generated_code: result.generated_code,
            context_files: result.context_files,
            agent: 'coder',
            intent: 'generate',
        };
    }

    /**
     * Выполняет inline-редактирование: применяет инструкцию к выбранному коду.
     */
    async inlineEdit(
        filePath: string,
        code: string,
        instruction: string,
        lineStart: number,
        lineEnd: number
    ): Promise<InlineEditResult> {
        const response = await fetch(`${this.serverUrl}/inline-edit`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                file_path: filePath,
                code,
                instruction,
                line_start: lineStart,
                line_end: lineEnd,
            }),
        });

        if (!response.ok) {
            throw new Error(`Inline edit failed: ${response.statusText}`);
        }

        return (await response.json()) as InlineEditResult;
    }

    /**
     * Дополняет код — продолжает написание из текущей позиции курсора.
     */
    async completeCode(
        codePrefix: string,
        contextFile?: string,
        language?: string
    ): Promise<GenerationResult> {
        const prompt = language
            ? `Continue writing this ${language} code:\n\`\`\`${language}\n${codePrefix}\n\`\`\``
            : `Continue writing this code:\n\`\`\`\n${codePrefix}\n\`\`\``;

        return this.generate(prompt, codePrefix, contextFile);
    }

    /**
     * Реализует функцию/метод по сигнатуре и docstring.
     */
    async implementFromSignature(
        signature: string,
        contextFile?: string
    ): Promise<GenerationResult> {
        const prompt = `Implement the following function/method. Follow the project's coding conventions:\n\`\`\`\n${signature}\n\`\`\``;

        return this.generate(prompt, signature, contextFile);
    }

    /**
     * Генерирует код из комментария (comment-to-code).
     */
    async generateFromComment(
        comment: string,
        surroundingCode?: string,
        contextFile?: string
    ): Promise<GenerationResult> {
        const prompt = `Generate code that implements the following comment/requirement: "${comment}"`;

        return this.generate(prompt, surroundingCode, contextFile);
    }

    /**
     * Добавляет обработку ошибок к существующему коду.
     */
    async addErrorHandling(
        code: string,
        contextFile?: string
    ): Promise<GenerationResult> {
        const prompt = 'Add comprehensive error handling, input validation, and proper logging to this code. Preserve the original functionality.';

        return this.generate(prompt, code, contextFile);
    }

    /**
     * Добавляет документацию/docstrings к коду.
     */
    async addDocumentation(
        code: string,
        contextFile?: string
    ): Promise<GenerationResult> {
        const prompt = 'Add comprehensive documentation, docstrings, and inline comments to this code. Follow the project\'s documentation conventions.';

        return this.generate(prompt, code, contextFile);
    }
}