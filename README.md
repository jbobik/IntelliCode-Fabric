<div align="center">

# ⬡ IntelliCode Fabric

**Fully-local AI code assistant for VS Code**

RAG · Multi-Agent · Local LLM · Fine-Tuning · Zero Data Leakage

[![VS Code](https://img.shields.io/badge/VS%20Code-1.85+-007ACC?logo=visual-studio-code&logoColor=white)](https://code.visualstudio.com/)
[![Python](https://img.shields.io/badge/Python-3.9+-3776AB?logo=python&logoColor=white)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Local](https://img.shields.io/badge/Inference-100%25_Local-brightgreen)](#)
[![Fine-tune](https://img.shields.io/badge/Fine--tune-QLoRA-blueviolet)](#fine-tuning)

<br>

<img src="https://img.shields.io/badge/No_API_Keys-✓-success?style=for-the-badge" alt="No API Keys">
<img src="https://img.shields.io/badge/No_Subscriptions-✓-success?style=for-the-badge" alt="No Subscriptions">
<img src="https://img.shields.io/badge/Your_Code_Stays_Local-✓-success?style=for-the-badge" alt="Local">

</div>

---

## What is IntelliCode Fabric?

IntelliCode Fabric is a VS Code extension that acts as a **full AI development partner** — not just autocomplete. It indexes your entire codebase via RAG, routes requests to specialized agents, runs models locally on your hardware, and can even be fine-tuned on your project's coding style.

**Key difference from Cursor / Copilot / Cody:** your code **never leaves your machine**. No API calls. No cloud. No subscriptions. Everything runs locally.

---

## ✨ Feature Overview

| Feature | Description |
|---------|-------------|
| **📚 RAG** | Indexes all project files into ChromaDB vector store. Every question gets answered with full project context. |
| **🤝 Multi-Agent System** | 4 specialized agents: Analyst (search/explain), Coder (generate), Refactor (patterns/SOLID), Tester (unit tests). Auto-routing by intent. |
| **🏠 Local Inference** | Models run on your machine via HuggingFace Transformers. No API keys needed. |
| **⚡ 4-bit Quantization** | NF4 quantization via bitsandbytes — run 7B models on 8GB VRAM or even CPU. |
| **🎯 Fine-Tuning** | QLoRA fine-tuning on your codebase. Model learns your naming conventions, architecture patterns, internal APIs. |
| **✏️ Inline Editing** | AI edits code directly in editor with diff preview — accept or reject. |
| **📥 Model Hub** | Download/switch between 12+ models from the UI. Load any HuggingFace model or local checkpoint. |
| **🔌 Custom Models** | Enter any HuggingFace repo ID or local path to load any compatible model. |

---

## 🏗️ Architecture

```text
┌─────────────────────────────────────────┐
│  VS Code Extension (TypeScript)         │
│  ┌─────────────────────────────────┐    │
│  │ • Sidebar Chat UI               │    │
│  │ • Inline Editor                 │    │
│  │ • Command Palette               │    │
│  │ • Model Manager                 │    │
│  └────────┬────────────────────────┘    │
│           │                             │
│  ┌────────▼────────┐                    │
│  │ Agent Orchestrator │                 │
│  │ ┌────┬────┬────┬────┐               │
│  │ │Anal│Coder│Refa│Test│               │
│  │ └────┴────┴────┴────┘               │
│  └────────┬────────┘                    │
└───────────┼─────────────────────────────┘
            │ HTTP / WebSocket
┌───────────▼─────────────────────────────┐
│  Python Backend (FastAPI)               │
│  ┌─────────────────────────────────┐    │
│  │ Agent Orchestrator (Python)     │    │
│  │ ┌────┬────┬────┬────┐           │    │
│  │ │Anal│Coder│Refa│Test│           │    │
│  │ └────┴────┴────┴────┘           │    │
│  └────────┬────────────────────────┘    │
│           │                             │
│  ┌────────▼────────┬────────┐           │
│  │ RAG Engine      │ LLM    │           │
│  │ • Chunker       │ Inference        │
│  │ • Embedder      │ • 4-bit quant    │
│  │ • Retriever     │ • Streaming      │
│  └────────┬────────┴────────┘           │
│           │                             │
│  ┌────────▼────────┐                    │
│  │ ChromaDB        │ HuggingFace        │
│  │ (Vectors)       │ (Models)           │
│  └─────────────────┘                    │
└─────────────────────────────────────────┘
```

## 🔹 Как работает RAG
```text
Вопрос: "Где реализована аутентификация?"
│
▼
┌──────────────────┐
│ 1. Embed вопрос  │ sentence-transformers/all-MiniLM-L6-v2
└────────┬─────────┘
         ▼
┌──────────────────┐
│ 2. Поиск в       │ ChromaDB: cosine similarity, top-5 chunks
│    ChromaDB      │
└────────┬─────────┘
         ▼
┌──────────────────┐
│ 3. Формируем     │ System prompt + найденные фрагменты кода
│    промпт        │ + вопрос пользователя
└────────┬─────────┘
         ▼
┌──────────────────┐
│ 4. LLM генерирует│ Qwen2.5-Coder / DeepSeek / CodeLlama
│    ответ         │ с конкретными ссылками на файлы
└──────────────────┘
```

## 🔹 Как работает мультиагентная система
```text
Запрос пользователя
│
▼
┌──────────────────────────┐
│ Intent Classification    │
│ • Rule-based (быстро)    │
│ • LLM (сложные случаи)   │
│                          │
│ "рефактор" → refactor    │
│ "тесты"    → test        │
│ "где?"     → analyze     │
│ "создай"   → generate    │
└──────────┬───────────────┘
           │
     ┌─────┴─────┐
     ▼           ▼
┌────────┐ ┌────────┐
│Analyst │→│ Coder  │  Pipeline: Analyst анализирует → Coder пишет
└────────┘ └────────┘
           │
           ▼
     ┌──────────┐
     │ Response │  Код + объяснение + ссылки на файлы
     └──────────┘
```

---

## 📦 Часть 4/10: Быстрый старт

---

## 🚀 Быстрый старт

### 🔹 Требования

| Компонент | Минимум | Рекомендуется |
|-----------|---------|---------------|
| **Python** | 3.9 | 3.10–3.11 |
| **Node.js** | 18 | 20+ |
| **VS Code** | 1.85 | Последняя версия |
| **RAM** | 4 GB | 16 GB |
| **GPU** | Не обязательно | NVIDIA с 8GB+ VRAM |
| **Диск** | 5 GB | 20 GB (для моделей) |

### 🔹 Установка

```bash
# 1. Клонируйте репозиторий
git clone https://github.com/jbobik/IntelliCode-Fabric.git
cd IntelliCode-Fabric

# 2. Запустите установку
# Linux / macOS:
chmod +x scripts/setup.sh
./scripts/setup.sh

# Windows:
scripts\setup.bat
```
```
📦 Скрипт установки автоматически:
Создаёт Python virtual environment
Устанавливает все зависимости (PyTorch, Transformers, ChromaDB, etc.)
Устанавливает npm-зависимости расширения
Компилирует TypeScript
Скачивает embedding-модель
```

# Терминал 1: Запуск бэкенда
```bash
# Linux/macOS:
source .venv/bin/activate
# Windows:
.venv\Scripts\activate
```

```bash
cd backend
python server.py
# ✅ Server running at http://127.0.0.1:8765
```
# Терминал 2: Открыть VS Code
```bash
cd ..
code .
# Нажмите F5 для запуска расширения в режиме отладки
```

# 🔹 Первые шаги
1. Откройте боковую панель — кликните на иконку 🤖 в Activity Bar
2. Выберите модель из выпадающего списка:
3. 🐌 Слабое железо → Qwen2.5 Coder 1.5B (~3GB RAM)
4. ⚡ Среднее → DeepSeek Coder 6.7B (~8GB RAM)
5. Нажмите "⬇ Download" для скачивания модели (первый раз)
6. Нажмите "▶ Load" для загрузки модели в память
7. Нажмите "📁 Index" для индексации вашего проекта
8. Начните общение! Попробуйте: "Где в проекте реализована аутентификация?"
---

## 📦 Доступные модели

| Модель | Параметры | RAM (4-bit) | Скорость | Качество | Лучше для |
|--------|-----------|-------------|----------|----------|-----------|
| **Qwen2.5 Coder 1.5B** ⭐ | 1.5B | ~3 GB | ⚡⚡⚡ | ★★★ | Слабое железо, быстрые ответы |
| DeepSeek Coder 1.3B | 1.3B | ~4 GB | ⚡⚡⚡ | ★★★ | Лёгкие задачи |
| StarCoder2 3B | 3B | ~4 GB | ⚡⚡ | ★★★★ | Баланс скорость/качество |
| CodeLlama 7B | 7B | ~8 GB | ⚡ | ★★★★ | Сложные задачи (Meta) |
| DeepSeek Coder 6.7B | 6.7B | ~8 GB | ⚡ | ★★★★★ | Лучшее качество |
| Qwen2.5 Coder 7B | 7B | ~8 GB | ⚡ | ★★★★★ | Лучшее общее качество |

### 🔹 Скачивание через CLI

```bash
# Посмотреть список доступных моделей
python scripts/download_model.py --list

# Скачать конкретную модель
python scripts/download_model.py --model qwen2.5-coder-1.5b
python scripts/download_model.py --model deepseek-coder-6.7b
```
---
# 🔹 Скачивание через UI
Нажмите "⬇ Download" в боковой панели расширения — модель скачается с HuggingFace Hub автоматически.

---

## 📦 Часть 6/10: Подробное описание функций (часть 1)

## 📖 Подробное описание функций

### 1️⃣ RAG (Retrieval-Augmented Generation)

При нажатии **"📁 Index"** плагин:

1. 🔍 Рекурсивно сканирует все файлы проекта (30+ расширений)
2. 🚫 Игнорирует `node_modules`, `.git`, `__pycache__`, `dist`, `build`
3. ✂️ Разбивает файлы на семантические чанки:
   - **Структурный чанкинг**: по функциям, классам, методам (regex по языку)
   - **Линейный чанкинг**: fallback на разбивку по строкам с overlap
4. 🧮 Генерирует эмбеддинги через `sentence-transformers/all-MiniLM-L6-v2`
5. 💾 Сохраняет в ChromaDB с метаданными (файл, строки, тип чанка)

**При каждом запросе:**

```text
Вопрос → эмбеддинг → поиск top-5 чанков (cosine similarity) → 
контекст в промпт → генерация ответа LLM
```

### 2️⃣ Мультиагентная система

**Автоматическая классификация** — система определяет намерение по ключевым словам:

| Запрос | Агент |
|--------|-------|
| *"Where is auth?"* | 🕵️ Analyst Agent |
| *"Создай endpoint"* | 💻 Coder Agent |
| *"Рефактор с Strategy"* | 🔄 Refactor Agent |
| *"Напиши тесты"* | 🧪 Tester Agent |

**Pipeline для сложных запросов:**
- Запрос генерации кода: `Analyst` анализирует → `Coder` генерирует
- Запрос рефакторинга: `Analyst` анализирует контекст → `Refactor` применяет паттерн
- Запрос тестов: `Analyst` определяет что тестировать → `Tester` генерирует тесты

### 3️⃣ Inline-редактирование

1. Выделите код в редакторе
2. `Ctrl+Shift+E` или правый клик → **"AI Code Partner: Inline Edit"**
3. Введите инструкцию: *"Добавь обработку ошибок"*
4. Откроется **diff-view**: `Original` ↔ `Modified`
5. Нажмите **"Apply Changes"** или **"Cancel"**

