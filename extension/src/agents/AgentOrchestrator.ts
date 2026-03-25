import { AnalystAgent } from './AnalystAgent';
import { CoderAgent } from './CoderAgent';
import { RefactorAgent } from './RefactorAgent';
import { TesterAgent } from './TesterAgent';

export interface AgentResponse {
    response: string;
    code?: string;
    agent: string;
    intent: string;
    references?: string[];
    analysis_summary?: string;
    test_code?: string;
    refactored_code?: string;
}

export interface ConversationMessage {
    role: 'user' | 'assistant' | 'system';
    content: string;
    agent?: string;
    timestamp?: number;
}

export type Intent = 'analyze' | 'generate' | 'refactor' | 'test' | 'explain' | 'general';

export class AgentOrchestrator {
    private serverUrl: string;
    private conversationHistory: ConversationMessage[] = [];
    private maxHistoryLength = 20;

    public analyst: AnalystAgent;
    public coder: CoderAgent;
    public refactor: RefactorAgent;
    public tester: TesterAgent;

    constructor(serverUrl: string) {
        this.serverUrl = serverUrl;
        this.analyst = new AnalystAgent(serverUrl);
        this.coder = new CoderAgent(serverUrl);
        this.refactor = new RefactorAgent(serverUrl);
        this.tester = new TesterAgent(serverUrl);
    }

    async chat(
        message: string,
        options: {
            contextFile?: string;
            selectedCode?: string;
        } = {}
    ): Promise<AgentResponse> {
        this.addToHistory({ role: 'user', content: message });

        const body = {
            message,
            context_file: options.contextFile,
            selected_code: options.selectedCode,
            conversation_history: this.getRecentHistory(10),
        };

        const response = await fetch(`${this.serverUrl}/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        });

        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(`Chat request failed (${response.status}): ${errorText}`);
        }

        const result = (await response.json()) as AgentResponse;

        this.addToHistory({
            role: 'assistant',
            content: result.response,
            agent: result.agent,
        });

        return result;
    }

    classifyIntent(message: string, hasSelectedCode: boolean): Intent {
        const msg = message.toLowerCase();

        const patterns: Record<Intent, string[]> = {
            refactor: ['refactor', 'rewrite', 'pattern', 'optimize', 'clean up', 'simplify', 'extract', 'restructure', 'rename'],
            test: ['test', 'unit test', 'spec', 'coverage', 'mock', 'assert', 'pytest', 'jest'],
            generate: ['generate', 'create', 'implement', 'write', 'add', 'build', 'make'],
            analyze: ['where', 'find', 'how does', 'what is', 'analyze', 'show', 'why', 'describe'],
            explain: ['explain', 'what does'],
            general: [],
        };

        for (const [intent, keywords] of Object.entries(patterns)) {
            if (keywords.some(kw => msg.includes(kw))) {
                return intent as Intent;
            }
        }

        if (hasSelectedCode && message.split(/\s+/).length < 10) {
            return 'explain';
        }

        return 'general';
    }

    async directCall(
        agent: 'analyst' | 'coder' | 'refactor' | 'tester',
        params: Record<string, any>
    ): Promise<AgentResponse> {
        switch (agent) {
            case 'analyst':
                return this.analyst.analyze(params.message, params.contextFile);
            case 'coder':
                return this.coder.generate(params.message, params.selectedCode, params.contextFile);
            case 'refactor': {
                const refResult = await this.refactor.refactorCode(
                    params.code, params.instruction, params.filePath, params.pattern
                );
                return {
                    response: refResult.response,
                    code: refResult.refactored_code,
                    refactored_code: refResult.refactored_code,
                    agent: 'refactor',
                    intent: 'refactor',
                };
            }
            case 'tester':
                return this.tester.generateTests(params.code, params.instruction, params.contextFile);
            default:
                throw new Error(`Unknown agent: ${agent}`);
        }
    }

    getRecentHistory(n: number): ConversationMessage[] {
        return this.conversationHistory.slice(-n);
    }

    getFullHistory(): ConversationMessage[] {
        return [...this.conversationHistory];
    }

    clearHistory(): void {
        this.conversationHistory = [];
    }

    private addToHistory(message: ConversationMessage): void {
        this.conversationHistory.push({
            ...message,
            timestamp: Date.now(),
        });

        if (this.conversationHistory.length > this.maxHistoryLength) {
            this.conversationHistory = this.conversationHistory.slice(-this.maxHistoryLength);
        }
    }
}