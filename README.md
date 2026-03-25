# 🤖 AI Code Partner

**Полноценный AI-ассистент для разработки, встроенный в VS Code.**

Локальный инференс, RAG по кодовой базе, мультиагентная система, fine-tuning — всё без внешних API. Ваш код остаётся на вашей машине.

---

![VS Code](https://img.shields.io/badge/VS%20Code-1.85+-blue?logo=visual-studio-code)
![Python](https://img.shields.io/badge/Python-3.9+-green?logo=python)
![License](https://img.shields.io/badge/License-MIT-yellow)
![Local](https://img.shields.io/badge/Inference-100%25%20Local-brightgreen)

---

## 📋 Содержание

- [Что это?](#-что-это)
- [Возможности](#-возможности)
- [Архитектура](#-архитектура)
- [Быстрый старт](#-быстрый-старт)
- [Модели](#-доступные-модели)
- [Подробное описание функций](#-подробное-описание-функций)
- [Конфигурация](#-конфигурация)
- [Горячие клавиши](#-горячие-клавиши)
- [Сравнение с аналогами](#-сравнение-с-аналогами)
- [Техническая документация](#-техническая-документация)
- [Troubleshooting](#-troubleshooting)

---

## 🎯 Что это?

AI Code Partner — это расширение для VS Code, которое работает как полноценный AI-партнёр по разработке. В отличие от простых автодополнений:

- **Индексирует всю кодовую базу** через RAG (Retrieval-Augmented Generation)
- **Понимает взаимосвязи** между файлами, модулями и компонентами
- **Специализированные агенты** для разных задач: анализ, кодинг, рефакторинг, тестирование
- **Работает полностью локально** — ваш код никогда не покидает вашу машину
- **Адаптируется к вашему стилю** через fine-tuning на вашем проекте

---

## ✨ Возможности

### Ядро

| Функция | Описание |
|---------|----------|
| 📚 **RAG по кодовой базе** | Индексирует все файлы проекта в векторное хранилище (ChromaDB). При вопросе находит наиболее релевантные фрагменты кода и передаёт их модели как контекст |
| 🤝 **Мультиагентная система** | 4 специализированных агента: Analyst (анализ и поиск), Coder (генерация кода), Refactor (рефакторинг по паттернам), Tester (генерация тестов) |
| 🏠 **Локальный инференс** | Модели запускаются на вашей машине через HuggingFace Transformers. Никаких API-ключей и подписок |
| ⚡ **4-bit квантование** | Используем bitsandbytes NF4 для запуска 7B-моделей на GPU с 8GB VRAM или даже на CPU |
| 🎯 **Fine-tuning** | Дообучение через QLoRA на кодовой базе вашего проекта. Модель перенимает ваш стиль кодирования |
| ✏️ **Inline-редактирование** | AI редактирует код прямо в редакторе с предпросмотром diff и кнопками Accept/Reject |
| 📥 **Управление моделями** | Скачивание, переключение и управление моделями прямо из интерфейса расширения |

### Контекстные операции

| Операция | Что делает |
|----------|-----------|
| 🔍 **"Где реализована аутентификация?"** | Analyst находит релевантные файлы через RAG и показывает конкретные участки кода |
| 💻 **"Создай REST endpoint для пользователей"** | Coder генерирует код, следуя конвенциям вашего проекта |
| 🔄 **"Перепиши используя паттерн Strategy"** | Refactor применяет паттерн с объяснением всех изменений |
| 🧪 **"Напиши тесты для этого класса"** | Tester определяет фреймворк (pytest/jest/junit) и генерирует тесты с edge cases |
| ✏️ **"Добавь обработку ошибок"** | Inline Edit модифицирует выделенный код с показом diff |

---

## 🏗️ Архитектура
┌─────────────────────────────────────────────────────────────────┐
│ VS Code Extension │
│ │
│ ┌──────────┐ ┌──────────┐ ┌───────────┐ ┌──────────────┐ │
│ │ Sidebar │ │ Inline │ │ Command │ │ Model │ │
│ │ Chat UI │ │ Editor │ │ Palette │ │ Manager │ │
│ └────┬─────┘ └────┬─────┘ └─────┬─────┘ └──────┬───────┘ │
│ │ │ │ │ │
│ ┌────┴──────────────┴──────────────┴────────────────┴───────┐ │
│ │ Agent Orchestrator (TypeScript) │ │
│ │ ┌──────────┐ ┌────────┐ ┌──────────┐ ┌────────────────┐ │ │
│ │ │ Analyst │ │ Coder │ │ Refactor │ │ Tester │ │ │
│ │ └──────────┘ └────────┘ └──────────┘ └────────────────┘ │ │
│ └─────────────────────────┬─────────────────────────────────┘ │
└────────────────────────────┼────────────────────────────────────┘
│ HTTP / WebSocket
┌────────────────────────────┼────────────────────────────────────┐
│ Python Backend (FastAPI) │
│ │ │
│ ┌─────────────────────────┴──────────────────────────────────┐ │
│ │ Agent Orchestrator (Python) │ │
│ │ ┌──────────┐ ┌────────┐ ┌──────────┐ ┌────────────────┐ │ │
│ │ │ Analyst │ │ Coder │ │ Refactor │ │ Tester │ │ │
│ │ └──────────┘ └────────┘ └──────────┘ └────────────────┘ │ │
│ └────────────────────────────────────────────────────────────┘ │
│ │
│ ┌─────────────┐ ┌──────────────┐ ┌───────────────────────┐ │
│ │ RAG Engine │ │ LLM Inference│ │ Fine-Tuning │ │
│ │ │ │ │ │ │ │
│ │ • Chunker │ │ • 4-bit quant│ │ • QLoRA │ │
│ │ • Embedder │ │ • Streaming │ │ • Dataset prep │ │
│ │ • Retriever │ │ • Multi-model│ │ • PEFT/TRL │ │
│ └──────┬──────┘ └──────┬───────┘ └───────────────────────┘ │
│ │ │ │
│ ┌──────┴──────┐ ┌──────┴───────┐ │
│ │ ChromaDB │ │ HuggingFace │ │
│ │ (Vectors) │ │ (Models) │ │
│ └─────────────┘ └──────────────┘ │
└─────────────────────────────────────────────────────────────────┘

 


### Как работает RAG
Вопрос: "Где реализована аутентификация?"
│
▼
┌──────────────────┐
│ 1. Embed вопрос │ sentence-transformers/all-MiniLM-L6-v2
└────────┬─────────┘
▼
┌──────────────────┐
│ 2. Поиск в │ ChromaDB: cosine similarity, top-5 chunks
│ ChromaDB │
└────────┬─────────┘
▼
┌──────────────────┐
│ 3. Формируем │ System prompt + найденные фрагменты кода
│ промпт │ + вопрос пользователя
└────────┬─────────┘
▼
┌──────────────────┐
│ 4. LLM генерирует│ Qwen2.5-Coder / DeepSeek / CodeLlama
│ ответ │ с конкретными ссылками на файлы
└──────────────────┘

 


### Как работает мультиагентная система
Запрос пользователя
│
▼
┌──────────────────────────┐
│ Intent Classification │ Rule-based (быстро) + LLM (сложные случаи)
│ │
│ "рефактор" → refactor │
│ "тесты" → test │
│ "где?" → analyze │
│ "создай" → generate │
└──────────┬───────────────┘
│
┌──────┴──────┐
▼ ▼
┌────────┐ ┌────────┐
│Analyst │→ │ Coder │ Pipeline: Analyst анализирует → Coder пишет
└────────┘ └────────┘
│
▼
┌──────────┐
│ Response │ Код + объяснение + ссылки на файлы
└──────────┘

 


---

## 🚀 Быстрый старт

### Требования

| Компонент | Минимум | Рекомендуется |
|-----------|---------|---------------|
| **Python** | 3.9 | 3.10-3.11 |
| **Node.js** | 18 | 20+ |
| **VS Code** | 1.85 | Последняя |
| **RAM** | 4GB | 16GB |
| **GPU** | Не обязательно | NVIDIA с 8GB+ VRAM |
| **Диск** | 5GB | 20GB (для моделей) |

### Установка

```bash
# 1. Клонируйте репозиторий
git clone https://github.com/your-repo/ai-code-partner.git
cd ai-code-partner

# 2. Запустите установку
# Linux / macOS:
chmod +x scripts/setup.sh
./scripts/setup.sh

# Windows:
scripts\setup.bat
Скрипт установки автоматически:

Создаёт Python virtual environment
Устанавливает все зависимости (PyTorch, Transformers, ChromaDB, etc.)
Устанавливает npm-зависимости расширения
Компилирует TypeScript
Скачивает embedding-модель
Запуск
Bash

# Терминал 1: Запуск бэкенда
source .venv/bin/activate        # Windows: .venv\Scripts\activate
cd backend
python server.py
# ✅ Server running at http://127.0.0.1:8765

# Терминал 2: Открыть VS Code
cd ..
code .
# Нажмите F5 для запуска расширения в режиме отладки
Первые шаги
Откройте боковую панель — кликните на иконку 🤖 в Activity Bar
Выберите модель из выпадающего списка:
Слабое железо → Qwen2.5 Coder 1.5B (3GB RAM)
Среднее → DeepSeek Coder 6.7B (8GB RAM)
Нажмите "⬇ Download" для скачивания модели (первый раз)
Нажмите "▶ Load" для загрузки модели в память
Нажмите "📁 Index" для индексации вашего проекта
Начните общение! Попробуйте: "Где в проекте реализована аутентификация?"
📦 Доступные модели
Модель	Параметры	RAM (4-bit)	Скорость	Качество	Лучше для
Qwen2.5 Coder 1.5B ⭐	1.5B	~3GB	⚡⚡⚡	★★★	Слабое железо, быстрые ответы
DeepSeek Coder 1.3B	1.3B	~4GB	⚡⚡⚡	★★★	Лёгкие задачи
StarCoder2 3B	3B	~4GB	⚡⚡	★★★★	Баланс скорость/качество
CodeLlama 7B	7B	~8GB	⚡	★★★★	Сложные задачи (Meta)
DeepSeek Coder 6.7B	6.7B	~8GB	⚡	★★★★★	Лучшее качество
Qwen2.5 Coder 7B	7B	~8GB	⚡	★★★★★	Лучшее общее качество
Скачивание через CLI
Bash

# Посмотреть список
python scripts/download_model.py --list

# Скачать конкретную модель
python scripts/download_model.py --model qwen2.5-coder-1.5b
python scripts/download_model.py --model deepseek-coder-6.7b
Скачивание через UI
Нажмите "⬇ Download" в боковой панели расширения — модель скачается с HuggingFace Hub.

📖 Подробное описание функций
1. RAG (Retrieval-Augmented Generation)
При нажатии "📁 Index" плагин:

Рекурсивно сканирует все файлы проекта (30+ расширений)
Игнорирует node_modules, .git, __pycache__, dist, build
Разбивает файлы на семантические чанки:
Структурный чанкинг: по функциям, классам, методам (regex по языку)
Линейный чанкинг: fallback на разбивку по строкам с overlap
Генерирует эмбеддинги через sentence-transformers/all-MiniLM-L6-v2
Сохраняет в ChromaDB с метаданными (файл, строки, тип чанка)
При каждом запросе:

Вопрос преобразуется в эмбеддинг
Находятся top-5 наиболее похожих чанков (cosine similarity)
Контекст добавляется в промпт для LLM
2. Мультиагентная система
Автоматическая классификация — система определяет намерение по ключевым словам:

 

"Where is auth?" → Analyst Agent
"Создай endpoint" → Coder Agent
"Рефактор с Strategy" → Refactor Agent
"Напиши тесты" → Tester Agent
Pipeline для сложных запросов:

Запрос генерации кода: Analyst анализирует → Coder генерирует
Запрос рефакторинга: Analyst анализирует контекст → Refactor применяет паттерн
Запрос тестов: Analyst определяет что тестировать → Tester генерирует тесты
3. Inline-редактирование
Выделите код в редакторе
Ctrl+Shift+E или правый клик → "AI Code Partner: Inline Edit"
Введите инструкцию: "Добавь обработку ошибок"
Откроется diff-view: Original ↔ Modified
Нажмите "Apply Changes" или "Cancel"
4. Fine-tuning
Дообучение на вашем проекте через QLoRA:

Bash

# Через VS Code: Ctrl+Shift+P → "AI Code Partner: Fine-tune on Project"

# Или через CLI:
python scripts/prepare_finetune_data.py /path/to/project --output data/finetune.jsonl
Что происходит:

Извлекаются пары docstring → implementation из кода
Создаются примеры file_prefix → continuation
Базовая модель загружается с 4-bit квантованием
Применяется LoRA (r=16, alpha=32) к attention-слоям
Обучение с gradient accumulation и cosine scheduler
Сохраняется только LoRA-адаптер (~50-100MB)
5. Квантование
По умолчанию используется NF4 квантование через bitsandbytes:

4-bit NF4 — модель занимает ~4x меньше памяти
Double quantization — дополнительная экономия ~0.4 бит/параметр
FP16 compute — вычисления в полуточности для скорости
Для ручного квантования (GPTQ):

Bash

python backend/quantize_model.py \
    --model deepseek-ai/deepseek-coder-6.7b-instruct \
    --output models/deepseek-coder-6.7b-gptq \
    --bits 4 \
    --method gptq
⚙️ Конфигурация
VS Code Settings (settings.json)
JSON

{
    "aiCodePartner.serverUrl": "http://127.0.0.1:8765",
    "aiCodePartner.autoIndex": true,
    "aiCodePartner.pythonPath": "python"
}
Backend Config (backend/config.yaml)
YAML

# Основные параметры
server:
  host: "127.0.0.1"
  port: 8765

# Параметры генерации
generation:
  max_new_tokens: 2048      # Максимум токенов в ответе
  temperature: 0.2          # Креативность (0.0-1.0)
  top_p: 0.95               # Nucleus sampling
  repetition_penalty: 1.1   # Штраф за повторения

# RAG
rag:
  chunk_size: 512            # Размер чанка в символах
  chunk_overlap: 50          # Перекрытие между чанками
  top_k: 5                  # Количество релевантных чанков

# Fine-tuning
fine_tuning:
  lora_r: 16                # Ранг LoRA
  lora_alpha: 32            # Альфа-множитель LoRA
  learning_rate: 2.0e-4     # Скорость обучения
  num_epochs: 3             # Количество эпох
⌨️ Горячие клавиши
Комбинация	macOS	Действие
Ctrl+Shift+A	⌘+Shift+A	Открыть чат AI
Ctrl+Shift+E	⌘+Shift+E	Inline Edit (с выделением)
Ctrl+Shift+G	⌘+Shift+G	Генерация кода
Контекстное меню (правый клик по выделенному коду)
🔍 Explain Selected Code — объяснить выбранный код
🔄 Refactor Selected Code — рефакторинг
🧪 Generate Tests — сгенерировать тесты
✏️ Inline Edit — редактировать с AI
Палитра команд (Ctrl+Shift+P)
AI Code Partner: Start Backend Server
AI Code Partner: Index Current Project
AI Code Partner: Select Model
AI Code Partner: Download Model
AI Code Partner: Fine-tune on Project
📊 Сравнение с аналогами
Критерий	AI Code Partner	Cursor	GitHub Copilot	Cody	Continue.dev
Локальный инференс	✅ Полностью	❌ API	❌ API	❌ API	✅ Ollama
Приватность данных	✅ 100%	❌	❌	Частично	✅
RAG по кодобазе	✅ ChromaDB	✅	Ограничено	✅	✅
Мультиагенты	✅ 4 агента	❌	❌	❌	❌
Fine-tuning	✅ QLoRA	❌	❌	❌	❌
Inline Edit с diff	✅	✅	✅	❌	❌
Выбор моделей	✅ 6+ моделей	❌ Фиксированы	❌	❌	✅
Квантование	✅ 4/8-bit	N/A	N/A	N/A	Depends
Стоимость	🆓 Бесплатно	$20/мес	$10-19/мес	Freemium	🆓
Open Source	✅ MIT	❌	❌	Частично	✅
Наши уникальные преимущества
Абсолютная приватность — код никогда не покидает вашу машину. Идеально для банков, финтеха, госсектора, NDA-проектов.

Fine-tuning на вашем проекте — ни один конкурент не позволяет дообучить модель на вашем coding style. После fine-tuning модель знает ваши конвенции именования, архитектурные паттерны, внутренние API.

Мультиагентная система — автоматическая маршрутизация к специализированным агентам вместо одного универсального. Каждый агент оптимизирован под свою задачу.

Нулевая стоимость — нет подписок, нет лимитов токенов. Одна мощная машина может обслуживать всю команду.

Поддержка слабого железа — NF4 квантование позволяет запускать 7B-модели на обычных ноутбуках с 8GB RAM.

🔧 Техническая документация
Структура проекта
 

ai-code-partner/
├── extension/                    # VS Code расширение (TypeScript)
│   ├── src/
│   │   ├── extension.ts         # Точка входа, регистрация команд
│   │   ├── sidebar/
│   │   │   └── SidebarProvider.ts  # Webview-провайдер чата
│   │   ├── agents/              # Клиентские обёртки агентов
│   │   │   ├── AgentOrchestrator.ts
│   │   │   ├── AnalystAgent.ts
│   │   │   ├── CoderAgent.ts
│   │   │   ├── RefactorAgent.ts
│   │   │   └── TesterAgent.ts
│   │   ├── rag/                 # RAG-интерфейсы
│   │   │   ├── Indexer.ts       # Управление индексацией
│   │   │   ├── VectorStore.ts   # Обёртка ChromaDB
│   │   │   └── Retriever.ts    # Извлечение контекста
│   │   ├── inference/
│   │   │   └── LocalLLM.ts     # Управление моделями, WebSocket
│   │   ├── inline/
│   │   │   └── InlineEditProvider.ts  # Inline-редактирование
│   │   └── models/
│   │       └── ModelManager.ts  # UI выбора моделей
│   └── media/                   # HTML/CSS/JS для webview
│       ├── sidebar.html
│       ├── sidebar.css
│       └── sidebar.js
│
├── backend/                     # Python бэкенд (FastAPI)
│   ├── server.py               # FastAPI сервер, endpoints
│   ├── rag_engine.py           # RAG: чанкинг, индексация, retrieval
│   ├── embeddings.py           # Sentence-transformers эмбеддинги
│   ├── llm_inference.py        # Загрузка моделей, генерация, стриминг
│   ├── fine_tuning.py          # QLoRA fine-tuning
│   ├── quantize_model.py       # Квантование моделей
│   ├── config.yaml             # Конфигурация
│   └── agents/                 # Серверные агенты
│       ├── orchestrator.py     # Маршрутизация и пайплайны
│       ├── analyst.py          # Анализ кода
│       ├── coder.py            # Генерация кода
│       ├── refactor.py         # Рефакторинг
│       └── tester.py           # Генерация тестов
│
├── models/                     # Скачанные модели (gitignored)
├── data/                       # ChromaDB и данные (gitignored)
├── scripts/                    # Скрипты установки
└── docs/                       # Документация
API Endpoints
Method	Endpoint	Описание
GET	/health	Статус сервера и модели
GET	/models	Список доступных моделей
POST	/models/select	Загрузить модель
POST	/models/download	Скачать модель с HF
POST	/models/unload	Выгрузить модель из RAM
POST	/index	Индексировать проект
POST	/chat	Отправить сообщение (с RAG + мультиагенты)
POST	/generate	Генерация кода
POST	/refactor	Рефакторинг кода
POST	/inline-edit	Inline-редактирование
POST	/fine-tune	Запуск fine-tuning
GET	/fine-tune/status	Статус fine-tuning
WS	/ws	WebSocket для стриминга
Технологический стек
Backend:

FastAPI + Uvicorn — HTTP/WebSocket сервер
HuggingFace Transformers — инференс моделей
bitsandbytes — 4/8-bit квантование
PEFT + TRL — LoRA fine-tuning
sentence-transformers — эмбеддинги для RAG
ChromaDB — векторная база данных
auto-gptq — GPTQ квантование (опционально)
Extension:

TypeScript — типизированный клиент
VS Code Extension API — интеграция с IDE
Webview API — UI чата
WebSocket — стриминг ответов
🔍 Troubleshooting
Бэкенд не запускается
Bash

# Проверьте Python версию
python --version  # Нужен 3.9+

# Проверьте что venv активирован
which python  # Должен показывать путь внутри .venv

# Переустановите зависимости
pip install -r backend/requirements.txt
CUDA не обнаружена
Bash

# Проверьте CUDA
python -c "import torch; print(torch.cuda.is_available())"

# Если False, модель будет работать на CPU (медленнее, но работает)
# Для GPU нужен NVIDIA драйвер + CUDA toolkit
Модель не загружается (Out of Memory)
Bash

# Используйте модель меньшего размера
# Qwen2.5-Coder-1.5B требует ~3GB RAM
# На CPU без квантования нужно больше RAM

# Или увеличьте swap:
# Linux: sudo fallocate -l 8G /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile
Расширение не подключается к бэкенду
Убедитесь, что бэкенд запущен: curl http://127.0.0.1:8765/health
Проверьте порт в настройках: aiCodePartner.serverUrl
Проверьте, не блокирует ли firewall порт 8765
Индексация слишком медленная
Убедитесь, что node_modules, .git и т.д. игнорируются (настроено по умолчанию)
Для очень больших проектов (>10000 файлов) первая индексация может занять несколько минут
Последующие запуски используют кэш ChromaDB
