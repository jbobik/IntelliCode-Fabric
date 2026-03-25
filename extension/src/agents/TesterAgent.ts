/**
 * TesterAgent — агент-тестировщик.
 * Генерирует unit-тесты, integration-тесты,
 * определяет тестовый фреймворк автоматически.
 */

import { AgentResponse } from './AgentOrchestrator';

export interface TestResult extends AgentResponse {
    test_code?: string;
    framework?: string;
    language?: string;
    test_count?: number;
}

export type TestFramework =
    | 'pytest'
    | 'jest'
    | 'mocha'
    | 'junit'
    | 'go_test'
    | 'rust_test'
    | 'auto';

export type TestType =
    | 'unit'
    | 'integration'
    | 'e2e'
    | 'snapshot'
    | 'property';

export class TesterAgent {
    private serverUrl: string;

    constructor(serverUrl: string) {
        this.serverUrl = serverUrl;
    }

    /**
     * Генерирует тесты для данного кода.
     */
    async generateTests(
        code: string,
        instruction?: string,
        contextFile?: string,
        framework: TestFramework = 'auto',
        testType: TestType = 'unit'
    ): Promise<TestResult> {
        const frameworkHint = framework !== 'auto' ? ` Use ${framework} framework.` : '';
        const typeHint = testType !== 'unit' ? ` Generate ${testType} tests.` : '';

        const message = instruction
            ? `${instruction}${frameworkHint}${typeHint}`
            : `Generate comprehensive ${testType} tests for the selected code.${frameworkHint} Cover all edge cases, error conditions, and boundary values.`;

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
            throw new Error(`Test generation failed: ${response.statusText}`);
        }

        const result = (await response.json()) as any;

        return {
            response: result.response,
            code: result.code || result.test_code,
            test_code: result.code || result.test_code,
            agent: result.agent || 'tester',
            intent: 'test',
            framework: result.framework || this.detectFramework(contextFile),
            language: result.language,
        };
    }

    /**
     * Генерирует тесты для конкретной функции/метода.
     */
    async generateTestsForFunction(
        code: string,
        functionName: string,
        contextFile?: string
    ): Promise<TestResult> {
        return this.generateTests(
            code,
            `Generate thorough unit tests specifically for the function/method "${functionName}". ` +
            `Include: normal cases, edge cases, error cases, boundary values, and null/undefined inputs.`,
            contextFile
        );
    }

    /**
     * Генерирует тесты для API endpoint-а.
     */
    async generateApiTests(
        code: string,
        contextFile?: string
    ): Promise<TestResult> {
        return this.generateTests(
            code,
            'Generate API/integration tests for this endpoint/route handler. ' +
            'Test: valid requests, invalid inputs, authentication, error responses, edge cases. ' +
            'Use proper mocking for database and external services.',
            contextFile,
            'auto',
            'integration'
        );
    }

    /**
     * Генерирует тест-кейсы для edge cases.
     */
    async generateEdgeCaseTests(
        code: string,
        contextFile?: string
    ): Promise<TestResult> {
        return this.generateTests(
            code,
            'Focus specifically on edge cases and corner cases: ' +
            'empty inputs, null/undefined, very large values, negative numbers, ' +
            'concurrent access, unicode strings, boundary conditions, overflow, ' +
            'timeout scenarios, and malformed data.',
            contextFile
        );
    }

    /**
     * Генерирует моки и фикстуры для тестирования.
     */
    async generateMocksAndFixtures(
        code: string,
        contextFile?: string
    ): Promise<TestResult> {
        return this.generateTests(
            code,
            'Generate mock objects, test fixtures, and factory functions for testing this code. ' +
            'Create reusable test helpers that can be shared across test suites.',
            contextFile
        );
    }

    /**
     * Определяет тестовый фреймворк по расширению файла / структуре проекта.
     */
    private detectFramework(filePath?: string): string {
        if (!filePath) { return 'auto'; }

        const ext = filePath.split('.').pop()?.toLowerCase();
        const frameworkMap: Record<string, string> = {
            'py': 'pytest',
            'js': 'jest',
            'jsx': 'jest',
            'ts': 'jest',
            'tsx': 'jest',
            'java': 'junit5',
            'kt': 'junit5',
            'go': 'go test',
            'rs': 'rust #[test]',
            'rb': 'rspec',
            'cs': 'xunit',
            'swift': 'XCTest',
        };

        return frameworkMap[ext || ''] || 'auto';
    }
}