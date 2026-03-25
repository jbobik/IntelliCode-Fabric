export interface RefactorResult {
    response: string;
    refactored_code?: string;
    file_path: string;
    changes_summary?: string;
}

export type DesignPattern =
    | 'strategy' | 'observer' | 'factory' | 'decorator'
    | 'singleton' | 'adapter' | 'facade' | 'command' | 'template_method';

export type RefactorPrinciple =
    | 'solid' | 'dry' | 'kiss' | 'clean' | 'separation_of_concerns';

export class RefactorAgent {
    private serverUrl: string;

    constructor(serverUrl: string) {
        this.serverUrl = serverUrl;
    }

    async refactorCode(
        code: string,
        instruction: string,
        filePath: string,
        pattern?: string
    ): Promise<RefactorResult> {
        const response = await fetch(`${this.serverUrl}/refactor`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                code,
                instruction,
                file_path: filePath,
                pattern: pattern || null,
            }),
        });

        if (!response.ok) {
            throw new Error(`Refactor failed: ${response.statusText}`);
        }

        return (await response.json()) as RefactorResult;
    }

    async applyPattern(
        code: string,
        pattern: DesignPattern,
        filePath: string
    ): Promise<RefactorResult> {
        const patternDescriptions: Record<DesignPattern, string> = {
            strategy: 'Refactor using the Strategy pattern. Extract behaviors into strategy classes.',
            observer: 'Refactor using the Observer pattern. Create Subject and Observer interfaces.',
            factory: 'Apply the Factory pattern. Extract object creation into a factory.',
            decorator: 'Apply the Decorator pattern. Create wrapper classes.',
            singleton: 'Implement the Singleton pattern.',
            adapter: 'Apply the Adapter pattern for incompatible interfaces.',
            facade: 'Apply the Facade pattern for a simplified interface.',
            command: 'Apply the Command pattern. Encapsulate requests as objects.',
            template_method: 'Apply the Template Method pattern.',
        };

        return this.refactorCode(code, patternDescriptions[pattern], filePath, pattern);
    }

    async applyPrinciple(
        code: string,
        principle: RefactorPrinciple,
        filePath: string
    ): Promise<RefactorResult> {
        const principleDescriptions: Record<RefactorPrinciple, string> = {
            solid: 'Refactor to follow SOLID principles.',
            dry: 'Apply DRY. Extract duplicated code into reusable parts.',
            kiss: 'Apply KISS. Simplify complex logic.',
            clean: 'Apply Clean Code principles.',
            separation_of_concerns: 'Separate concerns into distinct modules.',
        };

        return this.refactorCode(code, principleDescriptions[principle], filePath, principle);
    }

    async extractFunction(code: string, functionName: string, filePath: string): Promise<RefactorResult> {
        return this.refactorCode(
            code,
            `Extract the selected code into a new function called "${functionName}".`,
            filePath
        );
    }

    async improveNaming(code: string, filePath: string): Promise<RefactorResult> {
        return this.refactorCode(code, 'Improve all variable and function names for clarity.', filePath);
    }

    async optimizePerformance(code: string, filePath: string): Promise<RefactorResult> {
        return this.refactorCode(code, 'Optimize this code for performance.', filePath);
    }

    async modernize(code: string, filePath: string): Promise<RefactorResult> {
        return this.refactorCode(code, 'Modernize this code using current best practices.', filePath);
    }
}