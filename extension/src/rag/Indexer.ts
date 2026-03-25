/**
 * Indexer — управляет индексацией проекта для RAG.
 * Отправляет запросы на бэкенд для сканирования и индексации файлов,
 * отслеживает изменения файлов для инкрементальной переиндексации.
 */

import * as vscode from 'vscode';

export interface IndexStats {
    total_files: number;
    total_chunks: number;
    errors: number;
    project_path: string;
}

export interface IndexingProgress {
    current: number;
    total: number;
    currentFile?: string;
    phase: 'scanning' | 'chunking' | 'embedding' | 'storing' | 'complete';
}

export class Indexer {
    private serverUrl: string;
    private fileWatcher: vscode.FileSystemWatcher | null = null;
    private isIndexing = false;
    private lastIndexTime: number = 0;
    private debounceTimer: NodeJS.Timeout | null = null;

    // Паттерны файлов для индексации (синхронизировано с бэкендом)
    private static readonly SUPPORTED_EXTENSIONS = new Set([
        '.py', '.js', '.ts', '.tsx', '.jsx', '.java', '.cpp', '.c', '.h', '.hpp',
        '.cs', '.go', '.rs', '.rb', '.php', '.swift', '.kt', '.scala',
        '.vue', '.svelte', '.html', '.css', '.scss',
        '.sql', '.yaml', '.yml', '.json', '.toml', '.md', '.txt',
        '.sh', '.bat', '.dockerfile', '.xml',
    ]);

    private static readonly IGNORE_PATTERNS = [
        'node_modules', '.git', '__pycache__', '.venv', 'venv',
        'dist', 'build', '.next', 'target',
    ];

    constructor(serverUrl: string) {
        this.serverUrl = serverUrl;
    }

    /**
     * Индексирует весь проект. Отправляет запрос на бэкенд.
     */
    async indexProject(
        projectPath: string,
        forceReindex = false,
        progressCallback?: (progress: IndexingProgress) => void
    ): Promise<IndexStats> {
        if (this.isIndexing) {
            throw new Error('Indexing is already in progress');
        }

        this.isIndexing = true;

        try {
            if (progressCallback) {
                progressCallback({
                    current: 0,
                    total: 0,
                    phase: 'scanning',
                });
            }

            const response = await fetch(`${this.serverUrl}/index`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    project_path: projectPath,
                    force_reindex: forceReindex,
                }),
            });

            if (!response.ok) {
                const errorText = await response.text();
                throw new Error(`Indexing failed: ${errorText}`);
            }

            const result = (await response.json()) as { status: string; stats: IndexStats };

            this.lastIndexTime = Date.now();

            if (progressCallback) {
                progressCallback({
                    current: result.stats.total_files,
                    total: result.stats.total_files,
                    phase: 'complete',
                });
            }

            return result.stats;
        } finally {
            this.isIndexing = false;
        }
    }

    /**
     * Запускает наблюдение за изменениями файлов.
     * При изменении файлов автоматически переиндексирует с задержкой (debounce).
     */
    startWatching(projectPath: string): void {
        this.stopWatching();

        // Наблюдаем за всеми поддерживаемыми файлами
        const pattern = new vscode.RelativePattern(
            projectPath,
            '**/*.{py,js,ts,tsx,jsx,java,cpp,c,go,rs,rb,php,vue,svelte}'
        );

        this.fileWatcher = vscode.workspace.createFileSystemWatcher(pattern);

        const handleChange = (uri: vscode.Uri) => {
            // Проверяем, что файл не в игнорируемой директории
            const relativePath = vscode.workspace.asRelativePath(uri);
            const shouldIgnore = Indexer.IGNORE_PATTERNS.some(
                p => relativePath.includes(p)
            );

            if (shouldIgnore) { return; }

            // Debounce: ждём 5 секунд после последнего изменения
            if (this.debounceTimer) {
                clearTimeout(this.debounceTimer);
            }

            this.debounceTimer = setTimeout(() => {
                this.indexProject(projectPath, false).catch(err => {
                    console.error('Auto-reindex failed:', err);
                });
            }, 5000);
        };

        this.fileWatcher.onDidChange(handleChange);
        this.fileWatcher.onDidCreate(handleChange);
        this.fileWatcher.onDidDelete(handleChange);
    }

    /** Останавливает наблюдение за файлами */
    stopWatching(): void {
        if (this.fileWatcher) {
            this.fileWatcher.dispose();
            this.fileWatcher = null;
        }
        if (this.debounceTimer) {
            clearTimeout(this.debounceTimer);
            this.debounceTimer = null;
        }
    }

    /** Проверяет, нужно ли переиндексировать */
    needsReindex(maxAgeMs: number = 30 * 60 * 1000): boolean {
        return Date.now() - this.lastIndexTime > maxAgeMs;
    }

    /** Проверяет, поддерживается ли расширение файла */
    static isSupported(filePath: string): boolean {
        const ext = '.' + filePath.split('.').pop()?.toLowerCase();
        return Indexer.SUPPORTED_EXTENSIONS.has(ext);
    }

    /** Очищает ресурсы */
    dispose(): void {
        this.stopWatching();
    }
}