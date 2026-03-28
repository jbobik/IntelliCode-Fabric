<div align="center">

# ⬡ IntelliCode Fabric

**Полностью локальный AI-ассистент для разработки в VS Code**

RAG · Мультиагенты · Локальный инференс · Fine-Tuning · Нулевая утечка данных

[![VS Code](https://img.shields.io/badge/VS%20Code-1.85+-007ACC?logo=visual-studio-code&logoColor=white)](https://code.visualstudio.com/)
[![Python](https://img.shields.io/badge/Python-3.9+-3776AB?logo=python&logoColor=white)](https://python.org)
[![License](https://img.shields.io/badge/License-Apache-green.svg)](LICENSE)
[![Local](https://img.shields.io/badge/Инференс-100%25_Локальный-brightgreen)](#)
[![Fine-tune](https://img.shields.io/badge/Fine--tune-QLoRA-blueviolet)](#-дообучение-fine-tuning)

<br>

<img src="https://img.shields.io/badge/Без_API_ключей-✓-success?style=for-the-badge" alt="No API Keys">
<img src="https://img.shields.io/badge/Без_подписок-✓-success?style=for-the-badge" alt="No Subscriptions">
<img src="https://img.shields.io/badge/Код_остаётся_локальным-✓-success?style=for-the-badge" alt="Local">

</div>

---

## Что такое IntelliCode Fabric?

IntelliCode Fabric — это расширение для VS Code, которое выступает **полноценным AI-партнёром по разработке**, а не просто автодополнением. Оно индексирует всю вашу кодовую базу через RAG, маршрутизирует запросы к специализированным агентам, запускает модели локально на вашем железе и может быть дообучено на стиле вашего проекта.

**Ключевое отличие от Cursor / Copilot / Cody:** ваш код **никогда не покидает вашу машину**. Никаких API-вызовов. Никакого облака. Никаких подписок. Всё работает локально.

---

## ✨ Возможности

| Функция | Описание |
|---------|----------|
| **📚 RAG** | Индексирует все файлы проекта в векторное хранилище ChromaDB. Каждый вопрос получает ответ с полным контекстом проекта. |
| **🤝 Мультиагентная система v4** | 4 специализированных агента с паттерном ReAct: Analyst, Coder, Refactor, Tester. Реальные инструменты (read_file, write_file, run_command, search_code). Автомаршрутизация по интенту. |
| **🏠 Локальный инференс** | Модели запускаются на вашей машине через HuggingFace Transformers. API-ключи не нужны. |
| **⚡ 4-bit квантование** | NF4 квантование через bitsandbytes — запуск 7B моделей на 8GB VRAM или даже на CPU. |
| **🎯 Дообучение** | QLoRA fine-tuning на вашей кодовой базе. Модель учит ваши конвенции именования, архитектурные паттерны, внутренние API. |
| **✏️ Virtual Diff + Approve/Reject** | AI предлагает изменения — открывается split-diff с точными правками. Нажмите «Применить» или «Отклонить». Изменения применяются через `WorkspaceEdit` и сохраняются на диск. |
| **📡 SSE Streaming** | Ответы агентов стримятся в реальном времени (статус, thinking-блоки, tool calls, результаты). Поддержка отмены запроса. |
| **💻 Терминальные команды** | Автоматическое определение команд в ответе AI + кнопка запуска в терминале VS Code. |
| **📥 Хаб моделей** | Скачивание/переключение между 12+ моделями из UI. Загрузка любой модели с HuggingFace или локального чекпоинта. |
| **🔌 Кастомные модели** | Введите любой HuggingFace repo ID или локальный путь для загрузки совместимой модели. Настройки сохраняются между сессиями. |

---

## 🏗️ Архитектура
```
┌─────────────────────────────────────────────────────────────────┐
│ 		      VS Code Extension 		           	              │
│ 				   				                                  │
│ ┌───────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐	      │
│ │ Sidebar   │ │ Inline   │ │ Context  │ │ Model  	     │ 	      │
│ │ Chat UI   │ │ Editor   │ │ Menu 	│ │ Manager 	 │    	  │
│ └─────┬─────┘ └────┬─────┘ └────┬─────┘ └──────┬───────┘ 	      │
│ 	    └────────────┴────────────┴──────────────┘ 		          │
│ 			       HTTP / WebSocket 		                      │
└────────────────────────────┼────────────────────────────────────┘
			                 │
┌────────────────────────────┼────────────────────────────────────┐
│                     Python Backend (FastAPI)		           	  │
│ 			                │ 					                  │	
│ ┌─────────────────────────┴──────────────────────────────────┐  │
│ │ 			Agent Orchestrator 		                       │  │
│ │ ┌──────────┐ ┌────────┐ ┌──────────┐ ┌────────────────┐    │  │
│ │ │ Analyst  │ │  Coder │ │ Refactor │ │  Tester        │    │  │
│ │ └──────────┘ └────────┘ └──────────┘ └────────────────┘    │  │
│ └────────────────────────────────────────────────────────────┘  │
│                                                                 │
│ ┌─────────────┐ ┌──────────────┐ ┌───────────────────────┐      │
│ │ RAG Engine  │ │ LLM Engine   │ │ Fine-Tuning Engine    │	  │
│ │ ChromaDB    │ │ 4/8-bit quant│ │ QLoRA adapters        │	  │
│ │ Embeddings  │ │ Streaming    │ │ 5 стратегий данных    │	  │
│ └─────────────┘ └──────────────┘ └───────────────────────┘	  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🚀 Быстрый старт

### Требования

| Компонент | Минимум | Рекомендуется |
|-----------|---------|---------------|
| Python | 3.9 | 3.10-3.11 |
| Node.js | 18 | 20+ |
| VS Code | 1.85 | Последняя |
| RAM | 4GB | 16GB |
| GPU | Не обязательно | NVIDIA 8GB+ VRAM |

### Установка

```bash
git clone https://github.com/your-repo/intellicode-fabric.git
cd intellicode-fabric

# Linux / macOS
chmod +x scripts/setup.sh && ./scripts/setup.sh

# Windows
scripts\setup.bat
```

## Запуск
```bash
# Терминал 1: Бэкенд
source .venv/bin/activate          # Windows: .venv\Scripts\activate
cd backend && python server.py

# Терминал 2: VS Code
code .
# Нажмите F5 для запуска в режиме отладки
```
---
## Первые шаги
1. Выберите модель из выпадающего списка в боковой панели
2. Нажмите ⬇ Download (только первый раз) → затем ▶ Load
3. Нажмите 📁 Index для сканирования проекта
4. Начните общение! Попробуйте: «Где реализована аутентификация?»

---

## 📦 Доступные модели

### Предустановленные модели

| Тир | Модель | Параметры | RAM | Для чего |
|-----|--------|-----------|-----|----------|
| ⚡ Ультралёгкий | Qwen2.5 Coder 0.5B | 0.5B | ~2GB | Только CPU, мгновенные ответы |
| 🟢 Лёгкий | **Qwen2.5 Coder 1.5B** ⭐ | 1.5B | ~3GB | **Рекомендуется для большинства** |
| 🟢 Лёгкий | DeepSeek Coder 1.3B | 1.3B | ~4GB | Быстрые дополнения |
| 🟢 Лёгкий | StarCoder2 3B | 3B | ~4GB | 600+ языков, FIM |
| 🔵 Средний | Qwen2.5 Coder 7B | 7B | ~8GB | Высочайшее качество |
| 🔵 Средний | DeepSeek Coder 6.7B | 6.7B | ~8GB | Алгоритмы и структуры данных |
| 🔵 Средний | CodeLlama 7B | 7B | ~8GB | Модель Meta |
| 🔵 Средний | StarCoder2 7B | 7B | ~8GB | Fill-in-middle |
| 🔥 Мощный | Qwen2.5 Coder 14B | 14B | ~16GB | Качество уровня GPT-4 локально |
| 🔥 Мощный | DeepSeek Coder V2 16B | 16B | ~16GB | MoE, сложные рассуждения |
| 🏗️ Fine-tune | Qwen2.5 Coder 7B Base | 7B | ~8GB | Базовая модель для дообучения |
| 🏗️ Fine-tune | DeepSeek Coder 6.7B Base | 6.7B | ~8GB | Базовая модель для дообучения |

### Кастомные модели

Введите **любой HuggingFace репозиторий** или **локальный путь** в секции Custom Model:
#### HuggingFace модели
- microsoft/phi-2
- google/codegemma-2b
- meta-llama/Llama-3.2-3B-Instruct

#### Локальные пути
C:\models\my-finetuned-model
/home/user/models/custom-coder


---
## 🤝 Мультиагентная система v4 (ReAct)

Запросы автоматически классифицируются и маршрутизируются к специализированным агентам. Каждый агент работает по паттерну **ReAct** — итеративный цикл: Reason → Act (вызов инструмента) → Observe → повтор (до 4 шагов).

| Агент | Когда выбирается | Инструменты |
|-------|-----------------|-------------|
| 🔍 **Analyst** | Поиск, объяснение кода | `search_code`, `read_file` |
| 💻 **Coder** | Генерация, написание кода | `write_file`, `read_file` |
| 🔄 **Refactor** | Паттерны, SOLID, оптимизация | `read_file`, `edit_file` |
| 🧪 **Tester** | Юнит-тесты, edge cases | `read_file`, `write_file` |

**Pipeline-режим** для сложных запросов:
- Генерация кода: Analyst анализирует требования → Coder генерирует
- Тестирование: Analyst определяет что тестировать → Tester генерирует тесты

**Поддерживаемые языки классификации**: русский и английский.

---
## 🎯 Дообучение (Fine-tuning)

Обучите модель на **вашей** кодовой базе, чтобы она выучила:
- Конвенции именования вашей команды
- Архитектурные паттерны проекта
- Внутренние API и библиотеки
- Стиль обработки ошибок
- Формат документации

### Как это работает
```
	Код вашего проекта
		│
		▼
┌────────────────────────────────┐
│ 5 стратегий извлечения данных  │
│				                 │
│ 📝 Docstring → Реализация 	 │
│ 💬 Комментарий → Блок кода 	 │
│ 📄 Начало файла → Продолжение  │
│ ✍️ Сигнатура → Тело функции    │
│ 🧪 Тест → Реализация 		     │
└────────────┬───────────────────┘
	         │
	         ▼
┌────────────────────────────────┐
│ QLoRA обучение 		         │
│				                 │
│ Базовая модель (4-bit)	     │
│ + LoRA адаптеры (r=16, α=32)   │
│ Обучается ~2% параметров 	     │
│ Размер адаптера: ~50-100MB 	 │
└────────────┬───────────────────┘
	         │
	         ▼
┌────────────────────────────────┐
│ Адаптер для проекта		     │
│ 				                 │
│ models/adapters/ 		         │
│ qwen2.5__myproject__a1b2c3/ 	 │
│ adapter_config.json 	   	     │
│ adapter_model.safetensors 	 │
│ training_meta.json 	  	     │
└────────────────────────────────┘
```
---

### Использование

1. Нажмите **🎯 Fine-tune** в боковой панели
2. Выберите базовую модель, количество эпох (1-100) и стратегии обучения
3. Нажмите **🚀 Начать дообучение**
4. Наблюдайте за прогрессом в реальном времени
5. Загрузите модель с новым адаптером из пикера моделей

### Альтернатива через CLI

```bash
# Подготовка данных вручную
python scripts/prepare_finetune_data.py /путь/к/проекту

# Или через API
curl -X POST http://127.0.0.1:8765/fine-tune \
  -H "Content-Type: application/json" \
  -d '{"project_path": "/путь/к/проекту", "model_id": "qwen2.5-coder-1.5b", "epochs": 3}'
```
---
## 📚 RAG (Retrieval-Augmented Generation)
### Как работает
1. Индексация: Сканирует все файлы проекта (30+ расширений)
2. Чанкинг: Разбивает код на семантические фрагменты (по функциям/классам) или построчно с перекрытием
3. Эмбеддинги: Генерирует векторные представления через sentence-transformers/all-MiniLM-L6-v2
4. Хранение: Сохраняет в ChromaDB с метаданными (путь к файлу, номера строк, тип чанка)
5. Поиск: При каждом запросе находит top-5 наиболее релевантных чанков через cosine similarity
6. Аугментация: Внедряет найденный код в промпт LLM для контекстно-зависимых ответов

### Поддерживаемые языки
Python, JavaScript, TypeScript, Java, C/C++, C#, Go, Rust, Ruby, PHP, Swift, Kotlin, Scala, Vue, Svelte, SQL, YAML, JSON, Markdown, Shell и другие.

### Автоматически игнорируются

- node_modules, .git, __pycache__, venv, dist, build, *.min.js, *.lock и т.д.
---


## ⌨️ Горячие клавиши

| Комбинация | macOS | Действие |
|------------|-------|----------|
| `Ctrl+Shift+A` | `⌘+Shift+A` | Открыть чат |
| `Ctrl+Shift+E` | `⌘+Shift+E` | Inline Edit (с выделением) |
| `Ctrl+Shift+G` | `⌘+Shift+G` | Генерация кода |

### Контекстное меню (правый клик по выделенному коду)

- 🔍 Объяснить выбранный код
- 🔄 Рефакторинг выбранного кода
- 🧪 Генерация тестов
- ✏️ Inline-редактирование

---

## ⚙️ Конфигурация

### Настройки VS Code

```json
{
    "intelliCodeFabric.serverUrl": "http://127.0.0.1:8765",
    "intelliCodeFabric.autoIndex": true,
    "intelliCodeFabric.pythonPath": "python"
}
```
### Конфигурация бэкенда (backend/config.yaml)
```YAML
generation:
  max_new_tokens: 2048
  temperature: 0.2          # 0 = детерминированный, 1 = креативный
  top_p: 0.95
  repetition_penalty: 1.1

rag:
  chunk_size: 512
  chunk_overlap: 50
  top_k: 5                  # количество контекстных чанков на запрос

fine_tuning:
  lora_r: 16                # ранг LoRA
  lora_alpha: 32
  learning_rate: 2.0e-4
  batch_size: 4
  max_seq_length: 1024
```
---

## 📊 Сравнение с аналогами

| Критерий | **IntelliCode Fabric** | Cursor | GitHub Copilot | Cody | Continue.dev |
|----------|------------------------|--------|----------------|------|--------------|
| **Локальный инференс** | ✅ 100% | ❌ Облако | ❌ Облако | ❌ Облако | ✅ Ollama |
| **Приватность данных** | ✅ Полная | ❌ | ❌ | ⚠️ Частично | ✅ |
| **RAG по кодобазе** | ✅ ChromaDB | ✅ | ⚠️ Ограничено | ✅  | ✅ |
| **Мультиагенты** | ✅ 4 агента | ❌ | ❌ | ❌ | ❌ |
| **Дообучение (Fine-tuning)** | ✅ QLoRA | ❌ | ❌ | ❌ | ❌ |
| **Кастомные модели** | ✅ Любая HF модель | ❌ | ❌ | ❌ | ✅ |
| **Inline edit + diff** | ✅ | ✅ | ✅ | ❌ | ❌ |
| **Стоимость** | 🆓 Бесплатно | $20/мес | $10–19/мес | Freemium | 🆓 |
| **Open source** | ✅ Apache 2.0 | ❌ | ❌ | ⚠️ Частично | ✅ |

> 💡 **Итог:** IntelliCode Fabric — единственное решение, сочетающее **полную локальность**, **мультиагентную архитектуру** и **возможность дообучения** на вашем коде, при этом оставаясь полностью бесплатным и открытым.

### Почему IntelliCode Fabric?

1. Приватность: Код никогда не покидает вашу машину. Идеально для банков, финтеха, медицины, NDA-проектов.
2. Дообучение: Ни один конкурент не позволяет обучить модель на вашей кодовой базе. После fine-tuning модель знает ваши конвенции.
3. Мультиагенты: Специализированные агенты вместо one-size-fits-all. Каждый оптимизирован под свою задачу.
4. Нулевая стоимость: Нет подписок, нет лимитов токенов. Одна мощная машина может обслуживать всю команду.
5. Слабое железо: NF4 квантование запускает 7B модели на ноутбуках с 8GB RAM.
---
### 🔧 API-справочник

| Метод | Endpoint | Описание |
|-------|----------|----------|
| GET | `/health` | Статус сервера и модели |
| GET | `/models` | Список доступных моделей |
| POST | `/models/select` | Загрузить модель |
| POST | `/models/download` | Скачать с HuggingFace |
| POST | `/models/load-custom` | Загрузить любую модель по repo/path |
| POST | `/models/download-custom` | Скачать и загрузить кастомную модель |
| POST | `/models/unload` | Освободить GPU-память |
| GET | `/adapters` | Список дообученных адаптеров |
| POST | `/index` | Индексировать проект для RAG |
| POST | `/chat` | Чат с RAG + мультиагенты (JSON ответ) |
| POST | `/chat/stream` | Чат с SSE-стримингом (реальное время) |
| POST | `/chat/cancel` | Отменить текущий запрос |
| POST | `/fine-tune` | Запустить дообучение |
| GET | `/fine-tune/status` | Прогресс обучения |
---

## 🔍 Решение проблем

<details> <summary><strong>Бэкенд не запускается</strong></summary>

```bash
python --version   # Нужен 3.9+
pip install -r backend/requirements.txt
cd backend && python server.py
```

</details><details> <summary><strong>CUDA не обнаружена</strong></summary>

```bash
python -c "import torch; print(torch.cuda.is_available())"
# False → модель работает на CPU (медленнее, но работает)
# Установите CUDA toolkit + правильную версию PyTorch
```

</details><details> <summary><strong>Out of Memory</strong></summary>

- Используйте модель меньшего размера (Qwen2.5 Coder 0.5B — всего 2GB)
- Убедитесь, что 4-bit квантование работает (нужны bitsandbytes + CUDA)
- Увеличьте swap системы


</details><details> <summary><strong>Расширение не подключается к бэкенду</strong></summary>

1. Проверьте что бэкенд запущен: curl http://127.0.0.1:8765/health
2. Проверьте порт в настройках: intelliCodeFabric.serverUrl
3. Перезагрузите расширение: Ctrl+Shift+P → Developer: Reload Window


</details><details> <summary><strong>Дообучение падает</strong></summary>

```bash
pip install peft trl datasets
# При проблемах с версией trl:
pip install trl==0.24.0
```
---
## 🛠 Технологический стек

**Бэкенд:** FastAPI, HuggingFace Transformers, bitsandbytes, PEFT, TRL, sentence-transformers, ChromaDB, SSE (StreamingResponse)

**Расширение:** TypeScript, VS Code Extension API, Webview API, WorkspaceEdit, TextDocumentContentProvider

**Модели:** Qwen2.5-Coder, DeepSeek Coder, CodeLlama, StarCoder2 + любая HuggingFace модель

## 📄 Лицензия

Распространяется под лицензией **Apache License 2.0**.

📜 [Полный текст лицензии](LICENSE)


---
<div align="center"> <br>

Создано для разработчиков, которым важны приватность, кастомизация и контроль над инструментами.

⬡ IntelliCode Fabric

