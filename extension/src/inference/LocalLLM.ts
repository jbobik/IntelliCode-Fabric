/**
 * LocalLLM — клиентский интерфейс для взаимодействия с локальной LLM.
 * Управляет подключением к бэкенду, стриминг через WebSocket,
 * health checks, модели.
 */

export interface ModelInfo {
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

export interface ModelListResponse {
    models: ModelInfo[];
    default: string;
}

export interface HealthStatus {
    status: string;
    model_loaded: boolean;
    current_model: string | null;
}

export interface GenerationOptions {
    maxNewTokens?: number;
    temperature?: number;
    topP?: number;
    topK?: number;
    repetitionPenalty?: number;
}

export class LocalLLM {
    private serverUrl: string;
    private wsUrl: string;
    private ws: WebSocket | null = null;
    private reconnectAttempts = 0;
    private maxReconnectAttempts = 5;
    private reconnectDelay = 2000;

    constructor(serverUrl: string) {
        this.serverUrl = serverUrl;
        // Конвертируем http URL в ws URL
        this.wsUrl = serverUrl.replace('http://', 'ws://').replace('https://', 'wss://') + '/ws';
    }

    // ─── Health & Status ───

    /** Проверяет доступность бэкенда */
    async isAvailable(): Promise<boolean> {
        try {
            const response = await fetch(`${this.serverUrl}/health`, {
                signal: AbortSignal.timeout(3000),
            });
            return response.ok;
        } catch {
            return false;
        }
    }

    /** Получает текущий статус */
    async getHealth(): Promise<HealthStatus> {
        const response = await fetch(`${this.serverUrl}/health`);
        if (!response.ok) {
            throw new Error('Backend unavailable');
        }
        return (await response.json()) as HealthStatus;
    }

    /** Проверяет, загружена ли модель */
    async isModelLoaded(): Promise<boolean> {
        try {
            const health = await this.getHealth();
            return health.model_loaded;
        } catch {
            return false;
        }
    }

    // ─── Model Management ───

    /** Получает список доступных моделей */
    async getModels(): Promise<ModelListResponse> {
        const response = await fetch(`${this.serverUrl}/models`);
        if (!response.ok) {
            throw new Error('Failed to get model list');
        }
        return (await response.json()) as ModelListResponse;
    }

    /** Загружает модель для инференса */
    async loadModel(modelId: string): Promise<void> {
        const response = await fetch(`${this.serverUrl}/models/select`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ model_id: modelId }),
        });

        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(`Failed to load model: ${errorText}`);
        }
    }

    /** Скачивает модель с HuggingFace */
    async downloadModel(modelId: string): Promise<string> {
        const response = await fetch(`${this.serverUrl}/models/download`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ model_id: modelId }),
        });

        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(`Download failed: ${errorText}`);
        }

        const result = (await response.json()) as { status: string; path: string };
        return result.path;
    }

    /** Выгружает модель из памяти */
    async unloadModel(): Promise<void> {
        await fetch(`${this.serverUrl}/models/unload`, { method: 'POST' });
    }

    // ─── Text Generation ───

    /** Генерирует текст (без стриминга) */
    async generate(prompt: string, options: GenerationOptions = {}): Promise<string> {
        const response = await fetch(`${this.serverUrl}/generate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ prompt, ...options }),
        });

        if (!response.ok) {
            throw new Error(`Generation failed: ${response.statusText}`);
        }

        const result = (await response.json()) as any;
        return result.generated_code || result.response || '';
    }

    // ─── WebSocket Streaming ───

    /** Подключается к WebSocket для стриминга */
    connectWebSocket(
        onToken: (token: string) => void,
        onComplete: (contextFiles: string[]) => void,
        onError: (error: string) => void,
        onStatus?: (status: string) => void
    ): void {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            return;
        }

        try {
            this.ws = new WebSocket(this.wsUrl);

            this.ws.onopen = () => {
                this.reconnectAttempts = 0;
                console.log('WebSocket connected');
            };

            this.ws.onmessage = (event) => {
                const message = JSON.parse(event.data);

                switch (message.type) {
                    case 'token':
                        onToken(message.content);
                        break;
                    case 'stream_end':
                        onComplete(message.context_files || []);
                        break;
                    case 'error':
                        onError(message.content);
                        break;
                    case 'status':
                        if (onStatus) { onStatus(message.content); }
                        break;
                    case 'pong':
                        break;
                }
            };

            this.ws.onerror = (event) => {
                console.error('WebSocket error:', event);
                onError('WebSocket connection error');
            };

            this.ws.onclose = () => {
                console.log('WebSocket closed');
                this.attemptReconnect(onToken, onComplete, onError, onStatus);
            };

        } catch (error: any) {
            onError(`WebSocket connection failed: ${error.message}`);
        }
    }

    /** Отправляет сообщение для стриминга через WebSocket */
    streamChat(
        content: string,
        selectedCode?: string,
        conversationHistory: any[] = []
    ): void {
        if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
            throw new Error('WebSocket not connected');
        }

        this.ws.send(JSON.stringify({
            type: 'chat_stream',
            content,
            selected_code: selectedCode,
            conversation_history: conversationHistory,
        }));
    }

    /** Отключает WebSocket */
    disconnectWebSocket(): void {
        if (this.ws) {
            this.ws.close();
            this.ws = null;
        }
    }

    private attemptReconnect(
        onToken: (token: string) => void,
        onComplete: (contextFiles: string[]) => void,
        onError: (error: string) => void,
        onStatus?: (status: string) => void
    ): void {
        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            onError('Max reconnection attempts reached');
            return;
        }

        this.reconnectAttempts++;
        const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1);

        setTimeout(() => {
            console.log(`Reconnecting WebSocket (attempt ${this.reconnectAttempts})...`);
            this.connectWebSocket(onToken, onComplete, onError, onStatus);
        }, delay);
    }

    /** Очистка ресурсов */
    dispose(): void {
        this.disconnectWebSocket();
    }
}