/**
 * VectorStore — обёртка над взаимодействием с ChromaDB через бэкенд.
 * Управляет коллекциями, метаданными, статистикой хранилища.
 */

export interface VectorStoreStats {
    total_chunks: number;
    total_files: number;
    collection_name: string;
    last_updated: string;
}

export interface StoredChunk {
    id: string;
    content: string;
    metadata: {
        file_path: string;
        line_start: number;
        line_end: number;
        chunk_type: string;
    };
    relevance_score?: number;
}

export class VectorStore {
    private serverUrl: string;

    constructor(serverUrl: string) {
        this.serverUrl = serverUrl;
    }

    /**
     * Получает статистику текущего хранилища (если реализован endpoint).
     * Фоллбэк — через /health.
     */
    async getStats(): Promise<VectorStoreStats | null> {
        try {
            const response = await fetch(`${this.serverUrl}/health`);
            if (!response.ok) { return null; }

            const health = (await response.json()) as any;
            return {
                total_chunks: health.total_chunks || 0,
                total_files: health.total_files || 0,
                collection_name: health.collection || 'default',
                last_updated: health.last_indexed || 'unknown',
            };
        } catch {
            return null;
        }
    }

    /**
     * Проверяет, есть ли проиндексированные данные.
     */
    async hasData(): Promise<boolean> {
        const stats = await this.getStats();
        return stats !== null && stats.total_chunks > 0;
    }

    /**
     * Очищает хранилище (полная переиндексация).
     */
    async clear(projectPath: string): Promise<void> {
        const response = await fetch(`${this.serverUrl}/index`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                project_path: projectPath,
                force_reindex: true,
            }),
        });

        if (!response.ok) {
            throw new Error(`Failed to clear vector store: ${response.statusText}`);
        }
    }
}