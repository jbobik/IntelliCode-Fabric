/**
 * Retriever — извлекает релевантные фрагменты кода из RAG-базы.
 * Обёртка над бэкендовым retrieval endpoint-ом.
 */

export interface RetrievedChunk {
    content: string;
    metadata: {
        file_path: string;
        line_start: number;
        line_end: number;
        chunk_type: string;
    };
    relevance_score: number;
}

export interface RetrievalOptions {
    topK?: number;
    minScore?: number;
    fileFilter?: string[];
    excludeFiles?: string[];
}

export class Retriever {
    private serverUrl: string;
    private defaultTopK = 5;

    constructor(serverUrl: string) {
        this.serverUrl = serverUrl;
    }

    /**
     * Извлекает наиболее релевантные фрагменты кода для запроса.
     * Используется через /chat endpoint, который внутри вызывает RAG.
     */
    async retrieve(query: string, options: RetrievalOptions = {}): Promise<RetrievedChunk[]> {
        const topK = options.topK || this.defaultTopK;

        // Формируем поисковый запрос через chat с пустым conversation
        // (Основная логика RAG на бэкенде)
        const response = await fetch(`${this.serverUrl}/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message: `[SEARCH] ${query}`,
                conversation_history: [],
            }),
        });

        if (!response.ok) {
            throw new Error(`Retrieval failed: ${response.statusText}`);
        }

        const result = (await response.json()) as any;

        // Парсим ответ и извлекаем контекстные файлы
        const chunks: RetrievedChunk[] = (result.references || []).map(
            (ref: string, index: number) => ({
                content: '',
                metadata: {
                    file_path: ref,
                    line_start: 0,
                    line_end: 0,
                    chunk_type: 'reference',
                },
                relevance_score: 1 - index * 0.1,
            })
        );

        // Фильтрация по минимальному скору
        if (options.minScore) {
            return chunks.filter(c => c.relevance_score >= options.minScore!);
        }

        // Фильтрация по файлам
        if (options.fileFilter && options.fileFilter.length > 0) {
            return chunks.filter(c =>
                options.fileFilter!.some(f => c.metadata.file_path.includes(f))
            );
        }

        if (options.excludeFiles && options.excludeFiles.length > 0) {
            return chunks.filter(c =>
                !options.excludeFiles!.some(f => c.metadata.file_path.includes(f))
            );
        }

        return chunks;
    }

    /**
     * Быстрый поиск: возвращает только пути файлов, содержащих релевантный код.
     */
    async findRelevantFiles(query: string, maxFiles = 10): Promise<string[]> {
        const chunks = await this.retrieve(query, { topK: maxFiles });
        const files = [...new Set(chunks.map(c => c.metadata.file_path))];
        return files.slice(0, maxFiles);
    }

    /**
     * Получает контекст для конкретного файла.
     */
    async getFileContext(filePath: string): Promise<RetrievedChunk[]> {
        return this.retrieve(`code in file ${filePath}`, {
            fileFilter: [filePath],
            topK: 20,
        });
    }

    /**
     * Строит контекстную строку из извлечённых чанков (для промпта).
     */
    static buildContextString(chunks: RetrievedChunk[], maxLength = 4000): string {
        let context = '';
        for (const chunk of chunks) {
            const entry = `// File: ${chunk.metadata.file_path} (lines ${chunk.metadata.line_start}-${chunk.metadata.line_end})\n${chunk.content}\n\n`;
            if (context.length + entry.length > maxLength) { break; }
            context += entry;
        }
        return context;
    }
}