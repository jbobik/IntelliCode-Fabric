/**
 * AnalystAgent — агент-аналитик.
 * Отвечает на вопросы о кодовой базе, находит реализации,
 * объясняет архитектуру и взаимосвязи между компонентами.
 */

import { AgentResponse } from './AgentOrchestrator';

export class AnalystAgent {
    private serverUrl: string;

    constructor(serverUrl: string) {
        this.serverUrl = serverUrl;
    }

    /**
     * Анализирует кодовую базу и отвечает на вопрос.
     * Использует RAG для поиска релевантного контекста.
     */
    async analyze(message: string, contextFile?: string): Promise<AgentResponse> {
        const response = await fetch(`${this.serverUrl}/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message: `[ANALYST] ${message}`,
                context_file: contextFile,
                conversation_history: [],
            }),
        });

        if (!response.ok) {
            throw new Error(`Analyst request failed: ${response.statusText}`);
        }

        return (await response.json()) as AgentResponse;
    }

    /**
     * Объясняет выбранный фрагмент кода.
     */
    async explainCode(
        code: string,
        question: string = 'Explain this code in detail',
        contextFile?: string
    ): Promise<AgentResponse> {
        const response = await fetch(`${this.serverUrl}/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message: question,
                selected_code: code,
                context_file: contextFile,
                conversation_history: [],
            }),
        });

        if (!response.ok) {
            throw new Error(`Explain request failed: ${response.statusText}`);
        }

        return (await response.json()) as AgentResponse;
    }

    /**
     * Ищет конкретную реализацию в проекте.
     * Примеры: "Где реализована аутентификация?", "Найди обработку ошибок"
     */
    async findImplementation(query: string): Promise<AgentResponse> {
        return this.analyze(`Find the implementation of: ${query}`);
    }

    /**
     * Анализирует зависимости и взаимосвязи файла/модуля.
     */
    async analyzeDependencies(filePath: string): Promise<AgentResponse> {
        return this.analyze(
            `Analyze the dependencies and relationships of the file: ${filePath}. ` +
            `What does it import? What depends on it? How does it fit into the architecture?`,
            filePath
        );
    }

    /**
     * Ищет потенциальные проблемы и code smells.
     */
    async findIssues(code?: string, contextFile?: string): Promise<AgentResponse> {
        const message = code
            ? 'Find potential bugs, code smells, and improvement opportunities in the selected code'
            : 'Scan the project for potential issues, code smells, and areas that need improvement';

        const response = await fetch(`${this.serverUrl}/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message,
                selected_code: code,
                context_file: contextFile,
                conversation_history: [],
            }),
        });

        if (!response.ok) {
            throw new Error(`Issue scan failed: ${response.statusText}`);
        }

        return (await response.json()) as AgentResponse;
    }
}